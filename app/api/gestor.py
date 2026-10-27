"""Rotas do painel do gestor: visão global, usuários, setores, transferências."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.atendimentos import conversa_visivel
from app.api.deps import UsuarioAtual, somente_gestor
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now
from app.models import Atribuicao, Conversa, Mensagem, Setor, Usuario
from app.providers import provider_para_numero
from app.services.auth_service import get_password_hash

router = APIRouter(prefix="/api/gestor")


@router.post("/usuarios")
async def criar_usuario(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    role = dados.get("role", "")
    if role not in {"vendedor", "responsavel", "gestor"} or len(dados.get("senha", "")) < 8:
        raise HTTPException(status_code=422, detail="Papel ou senha inválidos")
    email = dados.get("email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
        raise HTTPException(status_code=409, detail="Email já existe")
    db.add(Usuario(
        nome=dados.get("nome", "").strip(), email=email,
        senha_hash=get_password_hash(dados["senha"]), role=role, ativo=True, online=True,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/usuarios/{usuario_id}")
async def editar_usuario(
    usuario_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404)
    dados = await form(request)
    role = dados.get("role", usuario.role)
    if role not in {"vendedor", "responsavel", "gestor"}:
        raise HTTPException(status_code=422)
    email = dados.get("email", usuario.email).strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if email != usuario.email and (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
        raise HTTPException(status_code=409, detail="Email já existe")
    usuario.nome = dados.get("nome", usuario.nome).strip()
    usuario.email = email
    usuario.role = role
    usuario.ativo = dados.get("ativo") == "on"
    usuario.online = dados.get("online") == "on"
    if dados.get("senha"):
        if len(dados["senha"]) < 8:
            raise HTTPException(status_code=422)
        usuario.senha_hash = get_password_hash(dados["senha"])
    await db.commit()
    return {"ok": True}


@router.post("/setores/{setor_id}")
async def configurar_setor(
    setor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    setor = await db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status_code=404)
    dados = await form(request)
    nome = dados.get("nome", setor.nome).strip()
    if not nome or len(nome) > 80:
        raise HTTPException(status_code=422, detail="Nome do setor inválido")
    if nome != setor.nome and (await db.execute(select(Setor.id).where(Setor.nome == nome))).first():
        raise HTTPException(status_code=409, detail="Setor já existe")
    responsavel_id = dados.get("responsavel_id", "")
    responsavel = await db.get(Usuario, int(responsavel_id)) if responsavel_id.isdecimal() else None
    if setor.ordem != 1 and (responsavel is None or responsavel.role != "responsavel" or not responsavel.ativo):
        raise HTTPException(status_code=422, detail="Responsável inválido")
    setor.nome = nome
    setor.responsavel_id = responsavel.id if responsavel else None
    await db.commit()
    return {"ok": True}


@router.post("/conversas/{conversa_id}/transferir")
async def transferir(
    conversa_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    conversa = await conversa_visivel(db, conversa_id, user)
    dados = await form(request)
    alvo_id = dados.get("usuario_id", "")
    alvo = await db.get(Usuario, int(alvo_id)) if alvo_id.isdecimal() else None
    setor = await db.get(Setor, conversa.setor_id) if conversa.setor_id else None
    vendas = setor is not None and setor.ordem == 1
    papel_esperado = "vendedor" if vendas else "responsavel"
    if alvo is None or not alvo.ativo or alvo.role != papel_esperado:
        raise HTTPException(status_code=422, detail="Destino inválido")
    antigo = conversa.atribuido_id
    if antigo == alvo.id:
        raise HTTPException(status_code=409, detail="Conversa já atribuída a este usuário")
    instante = now()
    resultado = await db.execute(update(Conversa).where(
        Conversa.id == conversa_id, Conversa.atribuido_id == antigo, Conversa.status == "aberta",
    ).values(
        atribuido_id=alvo.id, etapa="atribuida", primeira_resposta_em=None,
        timer_inicio_em=instante if vendas else None,
        timer_prazo_em=instante + timedelta(seconds=get_settings().timer_espera_segundos) if vendas else None,
        timer_aviso_em=None, timer_extensoes=0,
    ))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa já transferida")
    db.add(Atribuicao(conversa_id=conversa_id, de_usuario_id=antigo, para_usuario_id=alvo.id, motivo="gestor", criada_em=instante))
    alvo.ultima_atribuicao_em = instante
    config = get_settings()
    if config.aviso_transferencia_ativo:
        texto = config.aviso_transferencia_texto.replace("{nome}", alvo.nome)
        mensagem = Mensagem(conversa_id=conversa.id, origem="bot", texto=texto,
                            envio_status="pendente", criada_em=now())
        db.add(mensagem)
        await db.flush()
        try:
            await provider_para_numero(conversa.numero).enviar_texto(conversa.numero, texto)
        except Exception:
            mensagem.envio_status = "falhou"
            await db.commit()
            raise HTTPException(status_code=502, detail="Transferência salva, mas o aviso ao cliente falhou.")
        mensagem.envio_status = "enviada"
    await db.commit()
    return {"ok": True}
