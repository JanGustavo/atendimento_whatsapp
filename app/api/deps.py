from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Usuario
from app.services.auth_service import decode_token


@dataclass(frozen=True)
class UsuarioAtual:
    user_id: int
    role: str
    nome: str


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UsuarioAtual:
    token = request.cookies.get("acesso")
    decoded = decode_token(token) if token else None
    if not decoded:
        raise HTTPException(status_code=401, detail="Não autenticado")
    user = await db.get(Usuario, decoded[0])
    if user is None or not user.ativo or user.role != decoded[1]:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return UsuarioAtual(user_id=user.id, role=user.role, nome=user.nome)


def somente_gestor(user: UsuarioAtual = Depends(get_current_user)) -> UsuarioAtual:
    if user.role != "gestor":
        raise HTTPException(status_code=403, detail="Apenas gestor")
    return user
