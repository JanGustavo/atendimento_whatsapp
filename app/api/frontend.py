"""Leituras JSON para o painel React. As mutações reutilizam as rotas existentes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.api.painel import conversa_visivel
from app.providers import CLIENTES, provider_atual
from app.core.database import get_db
from app.models import Atribuicao, Conversa, Mensagem, Setor, Usuario

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
        "primeira_resposta_em": conversa.primeira_resposta_em.isoformat() if conversa.primeira_resposta_em else None,
    }


def mensagem_json(mensagem: Mensagem) -> dict:
    return {
        "id": mensagem.id,
        "origem": mensagem.origem,
        "envio_status": mensagem.envio_status,
        "texto": mensagem.texto,
        "autor_id": mensagem.autor_id,
        "criada_em": mensagem.criada_em.isoformat() if mensagem.criada_em else None,
    }


@router.get("/me")
async def me(user: UsuarioAtual = Depends(get_current_user)):
    return {"id": user.user_id, "nome": user.nome, "role": user.role}


@router.get("/conversas")
async def conversas(
    q: str = "", vendedor: int | None = None,
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user),
):
    stmt = select(Conversa).options(selectinload(Conversa.setor), selectinload(Conversa.atribuido)).order_by(Conversa.id.desc())
    if user.role != "gestor":
        stmt = stmt.where(Conversa.atribuido_id == user.user_id)
    elif vendedor is not None:
        stmt = stmt.where(Conversa.atribuido_id == vendedor)
    if q.strip():
        stmt = stmt.where(Conversa.numero.contains(q.strip()))
    return [conversa_json(conversa) for conversa in (await db.execute(stmt)).scalars()]


@router.get("/conversas/{conversa_id}")
async def detalhe_conversa(
    conversa_id: int, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    await db.refresh(conversa, attribute_names=["setor", "atribuido"])
    mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars().all()
    historico = (await db.execute(select(Atribuicao).where(Atribuicao.conversa_id == conversa.id).order_by(Atribuicao.id))).scalars().all()
    return {
        "conversa": conversa_json(conversa),
        "mensagens": [mensagem_json(item) for item in mensagens],
        "historico": [{
            "id": item.id,
            "de_usuario_id": item.de_usuario_id,
            "para_usuario_id": item.para_usuario_id,
            "motivo": item.motivo,
            "criada_em": item.criada_em.isoformat() if item.criada_em else None,
        } for item in historico],
    }


@router.get("/gestor/config")
async def configuracao_gestor(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    usuarios = (await db.execute(select(Usuario).order_by(Usuario.id))).scalars().all()
    setores = (await db.execute(select(Setor).order_by(Setor.ordem))).scalars().all()
    return {
        "usuarios": [{
            "id": item.id, "nome": item.nome, "email": item.email, "role": item.role,
            "ativo": item.ativo, "online": item.online,
        } for item in usuarios],
        "setores": [{
            "id": item.id, "ordem": item.ordem, "nome": item.nome,
            "responsavel_id": item.responsavel_id,
        } for item in setores],
    }


@router.get("/simulador")
async def dados_simulador(cliente: str = "cliente1", db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    if cliente not in CLIENTES:
        raise HTTPException(status_code=404, detail="Cliente fictício não encontrado")
    numero = CLIENTES[cliente][1]
    conversa = (await db.execute(select(Conversa).where(Conversa.numero == numero).order_by(Conversa.id.desc()).limit(1))).scalar_one_or_none()
    mensagens = [] if conversa is None else (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars().all()
    return {
        "clientes": [{"id": chave, "nome": valor[0], "numero": valor[1]} for chave, valor in CLIENTES.items()],
        "cliente": cliente,
        "conversa_id": conversa.id if conversa else None,
        "status": conversa.status if conversa else None,
        "etapa": conversa.etapa if conversa else None,
        "mensagens": [mensagem_json(item) for item in mensagens],
    }


@router.get("/gestor/whatsapp-status")
async def whatsapp_status(user: UsuarioAtual = Depends(somente_gestor)):
    return {"status": await provider_atual().status()}
