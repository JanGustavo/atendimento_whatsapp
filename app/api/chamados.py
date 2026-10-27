"""Abertura de chamados e registro de pedidos de acesso remoto."""
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.api._shared import form
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now as agora
from app.models import AcessoRemoto, Chamado, Computador, Usuario
from app.services.remoto import remoto_provider

router = APIRouter()

def validar_token(token: str) -> None:
    esperado = get_settings().chamado_install_token
    if not esperado:
        raise HTTPException(status_code=503, detail="Token de instalação não configurado")
    if not hmac.compare_digest(token, esperado):
        raise HTTPException(status_code=403, detail="Token de instalação inválido")


def suporte(user: UsuarioAtual = Depends(get_current_user)) -> UsuarioAtual:
    if user.role not in {"gestor", "responsavel"}:
        raise HTTPException(status_code=403, detail="Apenas gestor ou responsável")
    return user


@router.get("/api/chamado/computadores")
async def computadores_publicos(response: Response, token: str = "", db: AsyncSession = Depends(get_db)):
    validar_token(token)
    response.headers["Cache-Control"] = "no-store"
    computadores = (await db.execute(select(Computador).order_by(Computador.nome))).scalars().all()
    return [{"id": item.id, "nome": item.nome} for item in computadores]


@router.post("/api/chamado")
async def abrir_chamado(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    dados = await form(request)
    token = dados.get("token", "")
    validar_token(token)
    computador_id = dados.get("computador_id", "")
    descricao = dados.get("descricao", "").strip()
    computador = await db.get(Computador, int(computador_id)) if computador_id.isdecimal() else None
    if computador is None or not 3 <= len(descricao) <= 4000:
        raise HTTPException(status_code=422, detail="Computador ou descrição inválidos")
    chamado = Chamado(computador_id=computador.id, descricao=descricao, status="aberto", criado_em=agora())
    db.add(chamado)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"id": chamado.id, "status": chamado.status}


@router.get("/api/chamados")
async def listar_chamados(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)):
    chamados = (await db.execute(select(Chamado).options(selectinload(Chamado.computador)).order_by(Chamado.id.desc()))).scalars().all()
    acessos = (await db.execute(select(AcessoRemoto).options(selectinload(AcessoRemoto.solicitante)).order_by(AcessoRemoto.id.desc()))).scalars().all()
    historico: dict[int, list[dict]] = {}
    for acesso in acessos:
        historico.setdefault(acesso.chamado_id, []).append({
            "id": acesso.id, "solicitante": acesso.solicitante.nome,
            "resultado": acesso.resultado, "inicio_em": acesso.inicio_em.isoformat(),
            "fim_em": acesso.fim_em.isoformat() if acesso.fim_em else None,
        })
    return [{
        "id": chamado.id, "computador_id": chamado.computador_id,
        "computador_nome": chamado.computador.nome,
        "grupo": chamado.computador.grupo, "descricao": chamado.descricao,
        "status": chamado.status, "criado_em": chamado.criado_em.isoformat(),
        "solucao": chamado.solucao, "acessos": historico.get(chamado.id, []),
    } for chamado in chamados]


@router.get("/api/computadores")
async def listar_computadores(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)):
    computadores = (await db.execute(select(Computador).options(selectinload(Computador.dono)).order_by(Computador.nome))).scalars().all()
    return [{"id": item.id, "nome": item.nome, "grupo": item.grupo,
             "dono_id": item.dono_id, "dono_nome": item.dono.nome if item.dono else None,
             "mesh_node_id": item.mesh_node_id} for item in computadores]


@router.post("/api/computadores")
async def cadastrar_computador(request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(somente_gestor)):
    dados = await form(request)
    nome = dados.get("nome", "").strip()
    grupo = dados.get("grupo", "")
    dono_id = dados.get("dono_id", "")
    dono = await db.get(Usuario, int(dono_id)) if dono_id.isdecimal() else None
    mesh_node_id = dados.get("mesh_node_id", "").strip() or None
    if not nome or len(nome) > 120 or grupo not in {"empresa", "dono"} or dono is None or (mesh_node_id and len(mesh_node_id) > 255):
        raise HTTPException(status_code=422, detail="Dados do computador inválidos")
    if (await db.execute(select(Computador.id).where(Computador.nome == nome))).first():
        raise HTTPException(status_code=409, detail="Nome do computador já existe")
    computador = Computador(nome=nome, grupo=grupo, dono_id=dono.id, mesh_node_id=mesh_node_id)
    db.add(computador)
    await db.commit()
    return {"id": computador.id}


@router.post("/api/chamados/{chamado_id}/acessos")
async def solicitar_acesso(chamado_id: int, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)):
    chamado = (await db.execute(select(Chamado).options(selectinload(Chamado.computador)).where(Chamado.id == chamado_id))).scalar_one_or_none()
    if chamado is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")
    if chamado.computador.grupo == "dono":
        raise HTTPException(status_code=403, detail="O PC do dono não permite acesso remoto pela administração")
    if chamado.status == "fechado":
        raise HTTPException(status_code=409, detail="Chamado fechado")
    resultado = await remoto_provider.solicitar_acesso(chamado.computador)
    if resultado not in {"aceito", "recusado", "cancelado", "simulado"}:
        raise HTTPException(status_code=502, detail="Resultado inválido do provider remoto")
    instante = agora()
    atualizado = await db.execute(update(Chamado).where(Chamado.id == chamado.id, Chamado.status != "fechado").values(status="em_atendimento"))
    if atualizado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Chamado fechado")
    acesso = AcessoRemoto(chamado_id=chamado.id, solicitante_id=user.user_id,
                          computador_id=chamado.computador_id, inicio_em=instante,
                          fim_em=instante if resultado in {"recusado", "cancelado", "simulado"} else None,
                          resultado=resultado)
    db.add(acesso)
    await db.commit()
    return {"id": acesso.id, "resultado": acesso.resultado}


@router.post("/api/chamados/{chamado_id}/fechar")
async def fechar_chamado(chamado_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)):
    dados = await form(request)
    solucao = dados.get("solucao", "").strip()
    if not 3 <= len(solucao) <= 4000:
        raise HTTPException(status_code=422, detail="Descreva a solução")
    resultado = await db.execute(update(Chamado).where(Chamado.id == chamado_id, Chamado.status != "fechado").values(status="fechado", solucao=solucao))
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Chamado não encontrado ou já fechado")
    await db.commit()
    return {"status": "fechado"}
