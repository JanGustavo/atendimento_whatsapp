"""Mutações de atendimentos com isolamento no servidor."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
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
from app.services.media import caminho_media, guardar_webp

router = APIRouter(prefix="/api/atendimentos")


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
    if content_type == "image/webp":
        chave, arquivo = await guardar_webp(request)
        texto = request.query_params.get("texto", "").strip()
        if len(texto) > 4000:
            arquivo.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Texto inválido")
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
        if chave:
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
        if mensagem.imagem_chave:
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
        .values(status="encerrada", etapa="encerrada", timer_prazo_em=None)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await db.commit()
    return {"status": "encerrada"}
