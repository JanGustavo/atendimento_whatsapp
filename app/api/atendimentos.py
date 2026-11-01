"""Mutações de atendimentos com isolamento no servidor."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now
from app.models import Atribuicao, Conversa, LeituraConversa, Mensagem, Setor, Usuario
from app.providers import provider_para_numero
from app.providers.meta import MetaEnvioRecusado, MetaTokenExpirado
from app.services.media import caminho_media, guardar_audio, guardar_webp

router = APIRouter(prefix="/api/atendimentos")


async def exigir_janela_texto(db: AsyncSession, conversa: Conversa) -> None:
    if get_settings().whatsapp_provider != "meta":
        return
    ultima = (await db.execute(select(func.max(Mensagem.criada_em)).where(
        Mensagem.conversa_id == conversa.id, Mensagem.origem == "cliente"
    ))).scalar()
    if ultima is None or now() - ultima > timedelta(hours=24):
        raise HTTPException(status_code=409, detail="A janela de 24 horas terminou. Use um template aprovado pela Meta para retomar a conversa.")


@router.post("/novo-contato")
async def novo_contato(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    dados = await form(request)
    numero = "".join(c for c in dados.get("numero", "") if c.isdigit())
    nome = " ".join(dados.get("nome", "").split())[:120]
    if not 10 <= len(numero) <= 15 or not nome:
        raise HTTPException(status_code=422, detail="Informe nome e número com DDI e DDD")
    if dados.get("optin") != "sim":
        raise HTTPException(status_code=422, detail="Confirme o consentimento do contato para receber mensagens")
    existente = (await db.execute(select(Conversa.id).where(
        Conversa.numero == numero, Conversa.status == "aberta"
    ))).scalar_one_or_none()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe atendimento aberto para esse número")
    config = get_settings()
    conversa = Conversa(numero=numero, nome_contato=nome, atribuido_id=user.user_id,
                       status="aberta", etapa="atribuida", contato_optin_em=now())
    db.add(conversa)
    await db.flush()
    db.add(Atribuicao(conversa_id=conversa.id, para_usuario_id=user.user_id,
                      motivo="contato iniciado pelo painel", criada_em=now()))
    if config.whatsapp_provider == "meta" and not config.meta_template_nome:
        await db.commit()
        return {"id": conversa.id, "template_enviado": False}
    mensagem = Mensagem(conversa_id=conversa.id, autor_id=user.user_id, origem="humano",
                       texto=f"Template: {config.meta_template_nome or 'simulado'}",
                       envio_status="pendente", criada_em=now())
    db.add(mensagem)
    await db.flush()
    try:
        mensagem.provider_id = await provider_para_numero(numero).enviar_template(
            numero, config.meta_template_nome or "simulado", config.meta_template_idioma
        )
        mensagem.envio_status = "enviada"
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail="Contato salvo, mas o template falhou. Verifique a conexão Meta antes de reenviar.")
    await db.commit()
    return {"id": conversa.id, "template_enviado": True, "envio_status": "enviada"}


@router.post("/{conversa_id}/template")
async def enviar_template_contato(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    config = get_settings()
    if conversa.status != "aberta" or not conversa.contato_optin_em:
        raise HTTPException(status_code=409, detail="Contato sem consentimento registrado ou conversa encerrada")
    if config.whatsapp_provider == "meta" and not config.meta_template_nome:
        raise HTTPException(status_code=409, detail="Configure META_TEMPLATE_NOME com um template aprovado")
    mensagem = Mensagem(conversa_id=conversa.id, autor_id=user.user_id, origem="humano",
                       texto=f"Template: {config.meta_template_nome or 'simulado'}",
                       envio_status="pendente", criada_em=now())
    db.add(mensagem)
    await db.flush()
    try:
        mensagem.provider_id = await provider_para_numero(conversa.numero).enviar_template(
            conversa.numero, config.meta_template_nome or "simulado", config.meta_template_idioma
        )
        mensagem.envio_status = "enviada"
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail="Template falhou. Verifique o token e a aprovação do template na Meta.")
    await db.commit()
    return {"id": mensagem.id, "envio_status": "enviada"}


def escopo(user: UsuarioAtual):
    if user.role == "gestor":
        return True
    return Conversa.atribuido_id == user.user_id


async def conversa_visivel(db: AsyncSession, conversa_id: int, user: UsuarioAtual) -> Conversa:
    stmt = select(Conversa).where(Conversa.id == conversa_id, escopo(user))
    conversa = (await db.execute(stmt)).scalar_one_or_none()
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return conversa


@router.post("/{conversa_id}/leitura")
async def marcar_leitura(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await conversa_visivel(db, conversa_id, user)
    ultimo_id = (
        await db.execute(
            select(func.max(Mensagem.id)).where(
                Mensagem.conversa_id == conversa_id, Mensagem.origem == "cliente"
            )
        )
    ).scalar() or 0
    if ultimo_id:
        insercao = sqlite_insert(LeituraConversa).values(
            conversa_id=conversa_id,
            usuario_id=user.user_id,
            ultima_mensagem_id=ultimo_id,
            lida_em=now(),
        )
        await db.execute(
            insercao.on_conflict_do_update(
                index_elements=[
                    LeituraConversa.conversa_id,
                    LeituraConversa.usuario_id,
                ],
                set_={"ultima_mensagem_id": ultimo_id, "lida_em": now()},
                where=LeituraConversa.ultima_mensagem_id < ultimo_id,
            )
        )
        await db.commit()
    return {"ultima_mensagem_id": ultimo_id}


@router.post("/{conversa_id}/mensagens")
async def enviar(
    conversa_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    content_type = request.headers.get("content-type", "").split(";")[0].lower()
    audio_chave = None
    if content_type == "image/webp":
        chave, arquivo = await guardar_webp(request)
        texto = request.query_params.get("texto", "").strip()
        if len(texto) > 4000:
            arquivo.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Texto inválido")
    elif content_type in {"audio/mpeg", "audio/ogg", "audio/webm"}:
        audio_chave, arquivo = await guardar_audio(request)
        texto = ""
        chave = None
    else:
        dados = await form(request)
        texto = dados.get("texto", "").strip()
        chave = None
        arquivo = None
        if not texto or len(texto) > 4000:
            raise HTTPException(status_code=422, detail="Texto inválido")
    if conversa.status != "aberta":
        if arquivo:
            arquivo.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    try:
        await exigir_janela_texto(db, conversa)
    except HTTPException:
        if arquivo:
            arquivo.unlink(missing_ok=True)
        raise
    condicoes = [Conversa.id == conversa.id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(update(Conversa).where(*condicoes).values(status="aberta"))
    if resultado.rowcount != 1:
        if arquivo:
            arquivo.unlink(missing_ok=True)
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    mensagem = Mensagem(
        conversa_id=conversa.id,
        autor_id=user.user_id,
        origem="humano",
        texto=texto,
        imagem_chave=chave,
        audio_chave=audio_chave,
        envio_status="pendente",
        criada_em=now(),
    )
    db.add(mensagem)
    await db.flush()
    papel = {
        "colaborador": "Atendente",
        "supervisor": "Supervisor",
        "gestor": "Gestor",
    }[user.role]
    texto_cliente = f"*{papel} {user.nome}*\n{texto}" if texto else f"*{papel} {user.nome}*"
    provider = provider_para_numero(conversa.numero)
    try:
        if audio_chave:
            mensagem.provider_id = await provider.enviar_audio(conversa.numero, audio_chave)
        elif chave:
            mensagem.provider_id = await provider.enviar_imagem(
                conversa.numero, chave, texto_cliente
            )
        else:
            mensagem.provider_id = await provider.enviar_texto(
                conversa.numero, texto_cliente
            )
    except MetaTokenExpirado:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail="O token da Meta expirou. Avise o gestor para atualizar a conexão antes de enviar novamente.",
        )
    except MetaEnvioRecusado as falha:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail=str(falha))
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail="Envio ao WhatsApp falhou. A mensagem ficou marcada como falhou; tente enviá-la novamente.",
        )
    mensagem.envio_status = "enviada"
    if user.role == "colaborador":
        await db.execute(
            update(Conversa)
            .where(*condicoes)
            .values(
                primeira_resposta_em=func.coalesce(Conversa.primeira_resposta_em, now()),
                timer_prazo_em=None,
                etapa="atribuida",
            )
        )
    await db.commit()
    return {"id": mensagem.id, "envio_status": mensagem.envio_status}


@router.post("/{conversa_id}/mensagens/{mensagem_id}/reenviar")
async def reenviar(
    conversa_id: int,
    mensagem_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    if conversa.status != "aberta":
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    mensagem = (
        await db.execute(
            select(Mensagem).where(
                Mensagem.id == mensagem_id,
                Mensagem.conversa_id == conversa_id,
                Mensagem.origem == "humano",
                Mensagem.autor_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if mensagem is None:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    if not mensagem.texto.startswith("Template: "):
        await exigir_janela_texto(db, conversa)
    condicoes = [Conversa.id == conversa_id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    bloqueio = await db.execute(update(Conversa).where(*condicoes).values(status="aberta"))
    if bloqueio.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    reserva = await db.execute(
        update(Mensagem)
        .where(
            Mensagem.id == mensagem_id,
            Mensagem.envio_status == "falhou",
        )
        .values(envio_status="pendente")
    )
    if reserva.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Esta mensagem não está pendente de reenvio")
    papel = {
        "colaborador": "Atendente",
        "supervisor": "Supervisor",
        "gestor": "Gestor",
    }[user.role]
    texto_cliente = (
        f"*{papel} {user.nome}*\n{mensagem.texto}"
        if mensagem.texto
        else f"*{papel} {user.nome}*"
    )
    provider = provider_para_numero(conversa.numero)
    try:
        if mensagem.texto.startswith("Template: "):
            mensagem.provider_id = await provider.enviar_template(
                conversa.numero, mensagem.texto.removeprefix("Template: "), get_settings().meta_template_idioma
            )
        elif mensagem.audio_chave:
            mensagem.provider_id = await provider.enviar_audio(conversa.numero, mensagem.audio_chave)
        elif mensagem.imagem_chave:
            mensagem.provider_id = await provider.enviar_imagem(
                conversa.numero, mensagem.imagem_chave, texto_cliente
            )
        else:
            mensagem.provider_id = await provider.enviar_texto(
                conversa.numero, texto_cliente
            )
    except MetaTokenExpirado:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail="O token da Meta expirou. Avise o gestor para atualizar a conexão antes de reenviar.",
        )
    except MetaEnvioRecusado as falha:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail=str(falha))
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail="Reenvio ao WhatsApp falhou. A mensagem continua marcada como falhou.",
        )
    mensagem.envio_status = "enviada"
    if user.role == "colaborador":
        await db.execute(
            update(Conversa)
            .where(*condicoes)
            .values(
                primeira_resposta_em=func.coalesce(Conversa.primeira_resposta_em, now()),
                timer_prazo_em=None,
                etapa="atribuida",
            )
        )
    await db.commit()
    return {"id": mensagem.id, "envio_status": mensagem.envio_status}


async def mensagem_falha_do_autor(
    db: AsyncSession, conversa_id: int, mensagem_id: int, user: UsuarioAtual
) -> Mensagem:
    conversa = await conversa_visivel(db, conversa_id, user)
    if conversa.status != "aberta":
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    mensagem = (
        await db.execute(
            select(Mensagem).where(
                Mensagem.id == mensagem_id,
                Mensagem.conversa_id == conversa_id,
                Mensagem.origem == "humano",
                Mensagem.autor_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if mensagem is None:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    if mensagem.envio_status != "falhou" or mensagem.provider_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Só mensagens que falharam antes do envio podem ser alteradas no painel",
        )
    condicoes = [Conversa.id == conversa_id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    bloqueio = await db.execute(update(Conversa).where(*condicoes).values(status="aberta"))
    if bloqueio.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return mensagem


@router.patch("/{conversa_id}/mensagens/{mensagem_id}")
async def editar_mensagem_falha(
    conversa_id: int,
    mensagem_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    mensagem = await mensagem_falha_do_autor(db, conversa_id, mensagem_id, user)
    if mensagem.audio_chave or mensagem.texto.startswith("Template: "):
        raise HTTPException(status_code=409, detail="Áudio ou template com falha pode ser reenviado ou descartado, mas não editado")
    texto = (await form(request)).get("texto", "").strip()
    if len(texto) > 4000 or (not texto and not mensagem.imagem_chave):
        raise HTTPException(status_code=422, detail="Texto inválido")
    resultado = await db.execute(
        update(Mensagem)
        .where(
            Mensagem.id == mensagem_id,
            Mensagem.envio_status == "falhou",
            Mensagem.provider_id.is_(None),
        )
        .values(texto=texto)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Mensagem já foi reenviada")
    await db.commit()
    return {"id": mensagem_id, "texto": texto, "envio_status": "falhou"}


@router.delete("/{conversa_id}/mensagens/{mensagem_id}")
async def descartar_mensagem_falha(
    conversa_id: int,
    mensagem_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    mensagem = await mensagem_falha_do_autor(db, conversa_id, mensagem_id, user)
    imagem_chave = mensagem.imagem_chave
    audio_chave = mensagem.audio_chave
    resultado = await db.execute(
        delete(Mensagem).where(
            Mensagem.id == mensagem_id,
            Mensagem.envio_status == "falhou",
            Mensagem.provider_id.is_(None),
        )
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Mensagem já foi reenviada")
    await db.commit()
    if imagem_chave:
        caminho_media(imagem_chave).unlink(missing_ok=True)
    if audio_chave:
        caminho_media(audio_chave).unlink(missing_ok=True)
    return {"id": mensagem_id, "descartada": True}


@router.get("/{conversa_id}/mensagens/{mensagem_id}/imagem")
async def imagem_mensagem(
    conversa_id: int,
    mensagem_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await conversa_visivel(db, conversa_id, user)
    mensagem = await db.get(Mensagem, mensagem_id)
    if (
        mensagem is None
        or mensagem.conversa_id != conversa_id
        or not mensagem.imagem_chave
    ):
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    arquivo = caminho_media(mensagem.imagem_chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(
        arquivo,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{conversa_id}/mensagens/{mensagem_id}/audio")
async def audio_mensagem(
    conversa_id: int,
    mensagem_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await conversa_visivel(db, conversa_id, user)
    mensagem = await db.get(Mensagem, mensagem_id)
    if mensagem is None or mensagem.conversa_id != conversa_id or not mensagem.audio_chave:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    arquivo = caminho_media(mensagem.audio_chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    dados = arquivo.read_bytes()
    tamanho = len(dados)
    tipo = "audio/mpeg" if arquivo.suffix == ".mp3" else "audio/ogg"
    headers = {"Cache-Control": "private, max-age=3600", "Accept-Ranges": "bytes"}
    intervalo = request.headers.get("range")
    if intervalo and intervalo.startswith("bytes="):
        try:
            inicio_texto, fim_texto = intervalo[6:].split("-", 1)
            if not inicio_texto:
                inicio = max(0, tamanho - int(fim_texto))
                fim = tamanho - 1
            else:
                inicio = int(inicio_texto)
                fim = min(int(fim_texto), tamanho - 1) if fim_texto else tamanho - 1
            if inicio < 0 or fim < inicio or inicio >= tamanho:
                raise ValueError
        except ValueError:
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{tamanho}"})
        return Response(
            content=dados[inicio : fim + 1], status_code=206, media_type=tipo,
            headers={**headers, "Content-Range": f"bytes {inicio}-{fim}/{tamanho}"},
        )
    return Response(content=dados, media_type=tipo, headers=headers)


@router.post("/{conversa_id}/transferir")
async def transferir_atendimento(
    conversa_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    if conversa.status != "aberta":
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    if user.role != "gestor" and (conversa.atribuido_id is None or conversa.atribuido_id != user.user_id):
        raise HTTPException(status_code=409, detail="Conversa sem atendente ativo")
    dados = await form(request)
    destino = dados.get("destino", "")
    setor = None
    if destino.startswith("vendedor:") and destino[9:].isdecimal():
        setor = (await db.execute(select(Setor).where(Setor.ordem == 1))).scalar_one_or_none()
        if setor is None:
            raise HTTPException(status_code=422, detail="Setor de vendas indisponível")
        alvo = await db.get(Usuario, int(destino[9:]))
        if (
            alvo is None
            or alvo.role != "colaborador"
            or alvo.setor_interno_id != 1
            or not alvo.ativo
        ):
            raise HTTPException(status_code=422, detail="Vendedor inválido")
    elif destino.startswith("setor:") and destino[6:].isdecimal():
        setor = await db.get(Setor, int(destino[6:]))
        if setor is None or setor.ordem == 1 or setor.responsavel_id is None:
            raise HTTPException(status_code=422, detail="Setor inválido")
        alvo = await db.get(Usuario, setor.responsavel_id)
        if alvo is None or alvo.role != "supervisor" or not alvo.ativo:
            raise HTTPException(status_code=422, detail="Responsável indisponível")
    else:
        raise HTTPException(status_code=422, detail="Destino inválido")
    if conversa.atribuido_id is not None and alvo.id == conversa.atribuido_id:
        raise HTTPException(status_code=409, detail="Conversa já atribuída a este atendente")
    instante = now()
    antigo_id = conversa.atribuido_id
    novo_setor_id = setor.id if setor else conversa.setor_id
    vendas = setor.ordem == 1
    prazo = instante + timedelta(seconds=get_settings().timer_espera_segundos) if vendas else None
    condicoes = [
        Conversa.id == conversa.id,
        Conversa.status == "aberta",
    ]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    elif antigo_id is not None:
        condicoes.append(Conversa.atribuido_id == antigo_id)
    else:
        condicoes.append(Conversa.atribuido_id.is_(None))
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes)
        .values(
            atribuido_id=alvo.id,
            setor_id=novo_setor_id,
            etapa="atribuida",
            primeira_resposta_em=None,
            timer_inicio_em=instante if vendas else None,
            timer_prazo_em=prazo,
            timer_aviso_em=None,
            timer_extensoes=0,
            tentativas_timer=1 if vendas else 0,
        )
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa já transferida")
    db.add(
        Atribuicao(
            conversa_id=conversa.id,
            de_usuario_id=antigo_id,
            para_usuario_id=alvo.id,
            motivo="atendente" if antigo_id is not None else "gestor",
            criada_em=instante,
        )
    )
    alvo.ultima_atribuicao_em = instante
    config = get_settings()
    if config.aviso_transferencia_ativo:
        aviso = config.aviso_transferencia_texto.replace("{nome}", alvo.nome)
        mensagem = Mensagem(
            conversa_id=conversa.id,
            origem="bot",
            texto=aviso,
            envio_status="pendente",
            criada_em=instante,
        )
        db.add(mensagem)
        await db.flush()
        try:
            mensagem.provider_id = await provider_para_numero(conversa.numero).enviar_texto(
                conversa.numero, aviso
            )
        except Exception:
            mensagem.envio_status = "falhou"
            await db.commit()
            raise HTTPException(
                status_code=502,
                detail="Transferência salva, mas o aviso ao cliente falhou.",
            )
        mensagem.envio_status = "enviada"
    await db.commit()
    return {"ok": True}


@router.post("/{conversa_id}/encerrar")
async def encerrar(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    condicoes = [Conversa.id == conversa.id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes)
        .values(status="encerrada", etapa="encerrada", encerrada_em=now(), timer_prazo_em=None)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await db.commit()
    return {"status": "encerrada"}


@router.post("/{conversa_id}/arquivar")
async def arquivar(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await conversa_visivel(db, conversa_id, user)
    condicoes = [Conversa.id == conversa_id]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes, Conversa.arquivada_em.is_(None))
        .values(arquivada_em=now(), arquivada_por_id=user.user_id)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa já arquivada ou indisponível")
    await db.commit()
    return {"arquivada": True}


@router.post("/{conversa_id}/desarquivar")
async def desarquivar(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    await conversa_visivel(db, conversa_id, user)
    condicoes = [Conversa.id == conversa_id]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes, Conversa.arquivada_em.is_not(None))
        .values(arquivada_em=None, arquivada_por_id=None)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa não está arquivada ou indisponível")
    await db.commit()
    return {"arquivada": False}
