"""Comunicação interna simples, restrita a usuários autenticados."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.database import get_db
from app.core.utils import now
from app.models import MensagemInterna, SetorInterno, Usuario

router = APIRouter(prefix="/api/interno")


@router.get("/setores")
async def setores(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    grupos = (await db.execute(select(SetorInterno).order_by(SetorInterno.nome))).scalars().all()
    pessoas = (await db.execute(select(Usuario).where(
        Usuario.id != user.user_id,
    ).order_by(Usuario.nome))).scalars().all()
    return [{"id": grupo.id, "nome": grupo.nome, "pessoas": [
        {"id": pessoa.id, "nome": pessoa.nome, "role": pessoa.role,
         "ativo": pessoa.ativo, "online": pessoa.online}
        for pessoa in pessoas if pessoa.setor_interno_id == grupo.id
    ]} for grupo in grupos]


@router.get("/mensagens/{colega_id}")
async def mensagens(colega_id: int, antes: int | None = Query(None, ge=1),
                    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(get_current_user)):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega não encontrado")
    consulta = select(MensagemInterna).where(or_(
        and_(MensagemInterna.remetente_id == user.user_id, MensagemInterna.destinatario_id == colega_id),
        and_(MensagemInterna.remetente_id == colega_id, MensagemInterna.destinatario_id == user.user_id),
    ))
    if antes is not None:
        consulta = consulta.where(MensagemInterna.id < antes)
    registros = (await db.execute(consulta.order_by(MensagemInterna.id.desc()).limit(50))).scalars().all()
    return [{"id": item.id, "remetente_id": item.remetente_id, "texto": item.texto,
             "criada_em": item.criada_em.isoformat()} for item in reversed(registros)]


@router.post("/mensagens/{colega_id}")
async def enviar(colega_id: int, request: Request, db: AsyncSession = Depends(get_db),
                 user: UsuarioAtual = Depends(get_current_user)):
    colega = await db.get(Usuario, colega_id)
    if colega is None or not colega.ativo or colega.id == user.user_id:
        raise HTTPException(status_code=404, detail="Colega indisponível")
    dados = await form(request)
    texto = dados.get("texto", "").strip()
    if not 1 <= len(texto) <= 4000:
        raise HTTPException(status_code=422, detail="Mensagem inválida")
    mensagem = MensagemInterna(remetente_id=user.user_id, destinatario_id=colega.id,
                               texto=texto, criada_em=now())
    db.add(mensagem)
    await db.commit()
    return {"id": mensagem.id}
