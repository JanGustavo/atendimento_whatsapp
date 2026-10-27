"""Autenticação do painel React com cookie HttpOnly."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.core.database import get_db
from app.models import Usuario
from app.services.auth_service import create_access_token, verify_password

router = APIRouter(prefix="/api/auth")


@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    dados = await form(request)
    email = dados.get("email", "").strip().lower()
    usuario = (await db.execute(select(Usuario).where(Usuario.email == email))).scalar_one_or_none()
    if usuario is None or not usuario.ativo or not verify_password(dados.get("senha", ""), usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    resposta = JSONResponse({"id": usuario.id, "nome": usuario.nome, "role": usuario.role})
    resposta.set_cookie(
        "acesso",
        create_access_token(usuario.id, usuario.role),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return resposta


@router.post("/logout")
async def sair():
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie("acesso")
    return resposta
