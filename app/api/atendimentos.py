"""Mutações de atendimentos com isolamento no servidor."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.database import get_db
from app.core.utils import now
from app.models import Conversa, Mensagem
from app.providers import provider_para_numero

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


@router.post("/{conversa_id}/mensagens")
async def enviar(
    conversa_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(get_current_user),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    dados = await form(request)
    texto = dados.get("texto", "").strip()
    if not texto or len(texto) > 4000:
        raise HTTPException(status_code=422, detail="Texto inválido")
    if conversa.status != "aberta":
        raise HTTPException(status_code=409, detail="Conversa encerrada")
    condicoes = [Conversa.id == conversa.id, Conversa.status == "aberta"]
    if user.role != "gestor":
        condicoes.append(Conversa.atribuido_id == user.user_id)
    resultado = await db.execute(update(Conversa).where(*condicoes).values(status="aberta"))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    mensagem = Mensagem(conversa_id=conversa.id, autor_id=user.user_id, origem="humano",
                        texto=texto, envio_status="pendente", criada_em=now())
    db.add(mensagem)
    await db.flush()
    try:
        await provider_para_numero(conversa.numero).enviar_texto(conversa.numero, texto)
    except Exception:
        mensagem.envio_status = "falhou"
        await db.commit()
        raise HTTPException(status_code=502, detail="Envio ao WhatsApp falhou. A mensagem ficou marcada como falhou; tente enviá-la novamente.")
    mensagem.envio_status = "enviada"
    if user.role == "vendedor":
        await db.execute(update(Conversa).where(*condicoes).values(
            primeira_resposta_em=func.coalesce(Conversa.primeira_resposta_em, now()),
            timer_prazo_em=None, etapa="atribuida"))
    await db.commit()
    return {"id": mensagem.id, "envio_status": mensagem.envio_status}


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
    resultado = await db.execute(update(Conversa).where(*condicoes).values(
        status="encerrada", etapa="encerrada", timer_prazo_em=None))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    await db.commit()
    return {"status": "encerrada"}
