"""Autenticação do painel React com cookie HttpOnly."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user
from app.core.database import get_db
from app.models import Usuario
from app.services.auth_service import create_access_token, get_password_hash, verify_password

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


@router.post("/senha")
async def alterar_senha(request: Request, db: AsyncSession = Depends(get_db),
                       atual: UsuarioAtual = Depends(get_current_user)):
    dados = await form(request)
    usuario = await db.get(Usuario, atual.user_id)
    senha_nova = dados.get("senha_nova", "")
    if not verify_password(dados.get("senha_atual", ""), usuario.senha_hash):
        raise HTTPException(status_code=422, detail="Senha atual incorreta")
    if len(senha_nova) < 8 or senha_nova != dados.get("confirmacao", ""):
        raise HTTPException(status_code=422, detail="Nova senha inválida ou confirmação diferente")
    if verify_password(senha_nova, usuario.senha_hash):
        raise HTTPException(status_code=422, detail="Escolha uma senha diferente da atual")
    usuario.senha_hash = get_password_hash(senha_nova)
    await db.commit()
    return {"ok": True}
