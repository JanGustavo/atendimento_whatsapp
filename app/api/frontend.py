"""Leituras JSON para o painel React. As mutações reutilizam as rotas existentes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.atendimentos import conversa_visivel
from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now
from app.models import (
    Atribuicao,
    Conversa,
    LeituraConversa,
    Mensagem,
    Setor,
    SetorInterno,
    SimuladorEstado,
    Usuario,
)
from app.providers import CLIENTES, provider_atual
from app.services.media import caminho_media, foto_url, guardar_webp

router = APIRouter(prefix="/api")


def conversa_json(conversa: Conversa) -> dict:
    return {
        "id": conversa.id,
        "numero": conversa.numero,
        "nome_contato": conversa.nome_contato,
        "foto_url": f"/api/atendimentos/{conversa.id}/foto?v={conversa.foto_chave}" if conversa.foto_chave else None,
        "status": conversa.status,
        "arquivada": conversa.arquivada_em is not None,
        "contato_optin": conversa.contato_optin_em is not None,
        "etapa": conversa.etapa,
        "setor_id": conversa.setor_id,
        "setor_nome": conversa.setor.nome if conversa.setor else None,
        "setor_ordem": conversa.setor.ordem if conversa.setor else None,
        "atribuido_id": conversa.atribuido_id,
        "atribuido_nome": conversa.atribuido.nome if conversa.atribuido else None,
        "criada_em": conversa.criada_em.isoformat() if conversa.criada_em else None,
        "timer_prazo_em": conversa.timer_prazo_em.isoformat() if conversa.timer_prazo_em else None,
        "primeira_resposta_em": conversa.primeira_resposta_em.isoformat()
        if conversa.primeira_resposta_em
        else None,
    }


def mensagem_json(mensagem: Mensagem) -> dict:
    return {
        "id": mensagem.id,
        "origem": mensagem.origem,
        "envio_status": mensagem.envio_status,
        "lida_em": mensagem.lida_em.isoformat() if mensagem.lida_em else None,
        "texto": mensagem.texto,
        "imagem_url": (
            f"/api/atendimentos/{mensagem.conversa_id}/mensagens/{mensagem.id}/imagem"
            if mensagem.imagem_chave
            else None
        ),
        "audio_url": (
            f"/api/atendimentos/{mensagem.conversa_id}/mensagens/{mensagem.id}/audio"
            if mensagem.audio_chave else None
        ),
        "autor_id": mensagem.autor_id,
        "criada_em": mensagem.criada_em.isoformat() if mensagem.criada_em else None,
    }


@router.get("/me")
async def me(user: UsuarioAtual = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    usuario = await db.get(Usuario, user.user_id)
    return {
        "id": user.user_id,
        "nome": user.nome,
        "email": usuario.email,
        "role": user.role,
        "whatsapp_provider": get_settings().whatsapp_provider,
        "meta_template_disponivel": bool(get_settings().meta_template_nome),
        "foto_url": foto_url(usuario),
        "presenca_intervalo_segundos": get_settings().presenca_intervalo_segundos,
    }


@router.post("/presenca")
async def registrar_presenca(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    usuario = await db.get(Usuario, user.user_id)
    usuario.ultima_atividade_em = now()
    await db.commit()
    return {"online": True}


@router.post("/me/foto")
async def trocar_foto(request: Request, db: AsyncSession = Depends(get_db),
                     user: UsuarioAtual = Depends(get_current_user)):
    usuario = await db.get(Usuario, user.user_id)
    chave, arquivo = await guardar_webp(request)
    anterior = usuario.foto_chave
    try:
        usuario.foto_chave = chave
        await db.commit()
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise
    if anterior:
        caminho_media(anterior).unlink(missing_ok=True)
    return {"foto_url": foto_url(usuario)}


@router.get("/usuarios/{usuario_id}/foto")
async def foto_usuario(usuario_id: int, db: AsyncSession = Depends(get_db),
                      user: UsuarioAtual = Depends(get_current_user)):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo or not usuario.foto_chave:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    arquivo = caminho_media(usuario.foto_chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return FileResponse(arquivo, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/atendimentos")
async def conversas(
    q: str = "",
    vendedor: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    stmt = (
        select(Conversa)
        .options(selectinload(Conversa.setor), selectinload(Conversa.atribuido))
        .order_by(Conversa.id.desc())
    )
    if user.role != "gestor":
        stmt = stmt.where(Conversa.atribuido_id == user.user_id)
    elif vendedor is not None:
        stmt = stmt.where(Conversa.atribuido_id == vendedor)
    if q.strip():
        stmt = stmt.where(or_(Conversa.numero.contains(q.strip()), Conversa.nome_contato.contains(q.strip())))
    resultado = (await db.execute(stmt)).scalars().all()
    if not resultado:
        return []
    contagens = dict(
        (
            await db.execute(
                select(Mensagem.conversa_id, func.count(Mensagem.id))
                .join(Conversa, Conversa.id == Mensagem.conversa_id)
                .outerjoin(
                    LeituraConversa,
                    and_(
                        LeituraConversa.conversa_id == Conversa.id,
                        LeituraConversa.usuario_id == user.user_id,
                    ),
                )
                .where(
                    Conversa.id.in_([item.id for item in resultado]),
                    Mensagem.origem == "cliente",
                    Mensagem.id > func.coalesce(LeituraConversa.ultima_mensagem_id, 0),
                )
                .group_by(Mensagem.conversa_id)
            )
        ).all()
    )
    return [
        {**conversa_json(conversa), "nao_lidas": contagens.get(conversa.id, 0)}
        for conversa in resultado
    ]


@router.post("/atendimentos/{conversa_id}/foto")
async def foto_contato_enviar(
    conversa_id: int, request: Request, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    chave, arquivo = await guardar_webp(request)
    anterior = conversa.foto_chave
    try:
        conversa.foto_chave = chave
        await db.commit()
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise
    if anterior:
        caminho_media(anterior).unlink(missing_ok=True)
    return {"foto_url": f"/api/atendimentos/{conversa_id}/foto?v={chave}"}


@router.get("/atendimentos/{conversa_id}/foto")
async def foto_contato_ler(
    conversa_id: int, db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    if not conversa.foto_chave:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    arquivo = caminho_media(conversa.foto_chave)
    if not arquivo.is_file():
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return FileResponse(arquivo, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/atendimentos/{conversa_id}")
async def detalhe_conversa(
    conversa_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    await db.refresh(conversa, attribute_names=["setor", "atribuido"])
    mensagens = (
        (
            await db.execute(
                select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id)
            )
        )
        .scalars()
        .all()
    )
    historico = (
        (
            await db.execute(
                select(Atribuicao)
                .where(Atribuicao.conversa_id == conversa.id)
                .order_by(Atribuicao.id)
            )
        )
        .scalars()
        .all()
    )
    leitura_atendente = (
        (
            await db.execute(
                select(LeituraConversa).where(
                    LeituraConversa.conversa_id == conversa.id,
                    LeituraConversa.usuario_id == conversa.atribuido_id,
                )
            )
        ).scalar_one_or_none()
        if conversa.atribuido_id
        else None
    )
    ultima_cliente_id = max((item.id for item in mensagens if item.origem == "cliente"), default=0)
    ultima_cliente_em = max(
        (item.criada_em for item in mensagens if item.origem == "cliente"), default=None
    )
    vendedores = (
        (
            await db.execute(
                select(Usuario)
                .where(
                    Usuario.role == "colaborador",
                    Usuario.setor_interno_id == 1,
                    Usuario.ativo.is_(True),
                    Usuario.id != conversa.atribuido_id,
                )
                .order_by(Usuario.nome)
            )
        )
        .scalars()
        .all()
    )
    setores = (
        (await db.execute(select(Setor).where(Setor.ordem != 1).order_by(Setor.ordem)))
        .scalars()
        .all()
    )
    destinos = [
        {"valor": f"vendedor:{item.id}", "nome": f"Vendas · {item.nome}"} for item in vendedores
    ]
    for setor in setores:
        responsavel = await db.get(Usuario, setor.responsavel_id) if setor.responsavel_id else None
        if (
            responsavel
            and responsavel.ativo
            and responsavel.role == "supervisor"
            and responsavel.id != conversa.atribuido_id
        ):
            destinos.append(
                {
                    "valor": f"setor:{setor.id}",
                    "nome": f"{setor.nome} · {responsavel.nome}",
                }
            )
    return {
        "conversa": conversa_json(conversa),
        "destinos": destinos,
        "mensagens": [mensagem_json(item) for item in mensagens],
        "janela_texto_aberta": (
            get_settings().whatsapp_provider != "meta"
            or (ultima_cliente_em is not None and now() - ultima_cliente_em <= timedelta(hours=24))
        ),
        "visualizada_pelo_atendente_em": (
            leitura_atendente.lida_em.isoformat()
            if leitura_atendente and leitura_atendente.ultima_mensagem_id >= ultima_cliente_id
            else None
        ),
        "historico": [
            {
                "id": item.id,
                "de_usuario_id": item.de_usuario_id,
                "para_usuario_id": item.para_usuario_id,
                "motivo": item.motivo,
                "criada_em": item.criada_em.isoformat() if item.criada_em else None,
            }
            for item in historico
        ],
    }


@router.get("/gestor/config")
async def configuracao_gestor(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)
):
    usuarios = (await db.execute(select(Usuario).order_by(Usuario.id))).scalars().all()
    setores = (await db.execute(select(Setor).order_by(Setor.ordem))).scalars().all()
    setores_internos = (
        (await db.execute(select(SetorInterno).order_by(SetorInterno.nome))).scalars().all()
    )
    simulador = await db.get(SimuladorEstado, 1)
    return {
        "simulador_ativo": bool(get_settings().enable_simulator and simulador and simulador.ativo),
        "setores_internos": [{"id": item.id, "nome": item.nome, "icone": item.icone} for item in setores_internos],
        "usuarios": [
            {
                "id": item.id,
                "nome": item.nome,
                "foto_url": foto_url(item),
                "email": item.email,
                "role": item.role,
                "ativo": item.ativo,
                "online": item.online,
                "setor_interno_id": item.setor_interno_id,
            }
            for item in usuarios
        ],
        "setores": [
            {
                "id": item.id,
                "ordem": item.ordem,
                "nome": item.nome,
                "icone": item.icone,
                "responsavel_id": item.responsavel_id,
            }
            for item in setores
        ],
    }


@router.get("/simulador")
async def dados_simulador(
    cliente: str = "cliente1",
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    if not get_settings().enable_simulator:
        raise HTTPException(status_code=404, detail="Simulador desativado")
    simulador = await db.get(SimuladorEstado, 1)
    if simulador is None or not simulador.ativo:
        raise HTTPException(status_code=403, detail="Simulador desativado")
    if cliente not in CLIENTES:
        raise HTTPException(status_code=404, detail="Cliente fictício não encontrado")
    numero = CLIENTES[cliente][1]
    conversa = (
        await db.execute(
            select(Conversa).where(Conversa.numero == numero).order_by(Conversa.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    mensagens = (
        []
        if conversa is None
        else (
            await db.execute(
                select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "clientes": [
            {"id": chave, "nome": valor[0], "numero": valor[1]} for chave, valor in CLIENTES.items()
        ],
        "cliente": cliente,
        "conversa_id": conversa.id if conversa else None,
        "status": conversa.status if conversa else None,
        "etapa": conversa.etapa if conversa else None,
        "mensagens": [mensagem_json(item) for item in mensagens],
    }


@router.get("/gestor/whatsapp-status")
async def whatsapp_status(user: UsuarioAtual = Depends(somente_gestor)):
    config = get_settings()
    if config.whatsapp_provider == "meta" and not config.meta_app_secret:
        return {"status": "webhook sem chave"}
    return {"status": await provider_atual().status()}
