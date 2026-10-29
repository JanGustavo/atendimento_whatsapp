"""Leituras JSON para o painel React. As mutações reutilizam as rotas existentes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.atendimentos import conversa_visivel
from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.core.database import get_db
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

router = APIRouter(prefix="/api")


def conversa_json(conversa: Conversa) -> dict:
    return {
        "id": conversa.id,
        "numero": conversa.numero,
        "status": conversa.status,
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
    }


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
        stmt = stmt.where(Conversa.numero.contains(q.strip()))
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
        "simulador_ativo": bool(simulador and simulador.ativo),
        "setores_internos": [{"id": item.id, "nome": item.nome} for item in setores_internos],
        "usuarios": [
            {
                "id": item.id,
                "nome": item.nome,
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
    return {"status": await provider_atual().status()}
