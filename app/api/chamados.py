"""Abertura de chamados e registro de pedidos de acesso remoto."""

import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api._shared import form
from app.api.deps import UsuarioAtual, get_current_user, somente_gestor
from app.core.config import get_settings
from app.core.database import get_db
from app.core.utils import now as agora
from app.models import AcessoRemoto, Chamado, Computador, SessaoMeshCentral, Usuario
from app.services.meshcentral_events import monitor_conectado
from app.services.remoto import provider_remoto_atual

router = APIRouter()


async def expirar_pendentes(db: AsyncSession) -> None:
    instante = agora()
    await db.execute(update(AcessoRemoto).where(AcessoRemoto.resultado == 'pendente', AcessoRemoto.expira_em <= instante).values(resultado='expirado', fim_em=instante))


def serializar_acesso(acesso: AcessoRemoto, computador_nome: str, motivo: str) -> dict:
    """Eventos de consentimento, nao comprovantes de conexao remota efetiva."""
    return {
        "id": acesso.id,
        "chamado_id": acesso.chamado_id,
        "computador_id": acesso.computador_id,
        "computador_nome": computador_nome,
        "motivo": motivo,
        "solicitante": acesso.solicitante.nome if acesso.solicitante else None,
        "solicitante_id": acesso.solicitante_id,
        "resultado": acesso.resultado,
        "inicio_em": acesso.inicio_em.isoformat(),  # hora da SOLICITACAO
        "expira_em": acesso.expira_em.isoformat() if acesso.expira_em else None,
        "autorizado_por_id": acesso.autorizado_por_id,
        "autorizado_em": acesso.autorizado_em.isoformat() if acesso.autorizado_em else None,
        "respondido_por_id": acesso.respondido_por_id,
        "respondido_em": acesso.respondido_em.isoformat() if acesso.respondido_em else None,
        "encerrado_por_id": acesso.encerrado_por_id,
        "fim_em": acesso.fim_em.isoformat() if acesso.fim_em else None,
        "sessao_remota_ativa": False,  # ainda nao ha integracao MeshCentral
        "acesso_url": None,
    }


def validar_token(token: str) -> None:
    esperado = get_settings().chamado_install_token
    if not esperado:
        raise HTTPException(status_code=503, detail="Token de instalação não configurado")
    if not hmac.compare_digest(token, esperado):
        raise HTTPException(status_code=403, detail="Token de instalação inválido")


def suporte(user: UsuarioAtual = Depends(get_current_user)) -> UsuarioAtual:
    if user.role not in {"gestor", "supervisor"}:
        raise HTTPException(status_code=403, detail="Apenas gestor ou responsável")
    return user


def vendedor(user: UsuarioAtual = Depends(get_current_user)) -> UsuarioAtual:
    if user.role != "colaborador":
        raise HTTPException(status_code=403, detail="Apenas colaborador")
    return user


@router.get("/api/chamado/computadores")
async def computadores_publicos(
    response: Response, token: str = "", db: AsyncSession = Depends(get_db)
):
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
    chamado = Chamado(
        computador_id=computador.id,
        descricao=descricao,
        status="aberto",
        criado_em=agora(),
    )
    db.add(chamado)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"id": chamado.id, "status": chamado.status}


@router.get("/api/meus-chamados/computadores")
async def meus_computadores(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(vendedor)
):
    computadores = (
        (
            await db.execute(
                select(Computador)
                .where(
                    Computador.dono_id == user.user_id,
                    Computador.grupo == "empresa",
                )
                .order_by(Computador.nome)
            )
        )
        .scalars()
        .all()
    )
    return [{"id": item.id, "nome": item.nome} for item in computadores]


@router.get("/api/meus-chamados")
async def meus_chamados(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(vendedor)):
    chamados = (
        (
            await db.execute(
                select(Chamado)
                .join(Computador)
                .where(
                    Computador.dono_id == user.user_id,
                    Computador.grupo == "empresa",
                )
                .options(selectinload(Chamado.computador))
                .order_by(Chamado.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "computador_nome": item.computador.nome,
            "descricao": item.descricao,
            "status": item.status,
            "criado_em": item.criado_em.isoformat(),
            "solucao": item.solucao,
        }
        for item in chamados
    ]


@router.post("/api/meus-chamados")
async def abrir_meu_chamado(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(vendedor),
):
    dados = await form(request)
    computador_id = dados.get("computador_id", "")
    descricao = dados.get("descricao", "").strip()
    if not computador_id.isdecimal() or not 3 <= len(descricao) <= 4000:
        raise HTTPException(status_code=422, detail="Computador ou descrição inválidos")
    computador = (
        await db.execute(
            select(Computador).where(
                Computador.id == int(computador_id),
                Computador.dono_id == user.user_id,
                Computador.grupo == "empresa",
            )
        )
    ).scalar_one_or_none()
    if computador is None:
        raise HTTPException(status_code=404, detail="Computador não encontrado")
    chamado = Chamado(
        computador_id=computador.id,
        descricao=descricao,
        status="aberto",
        criado_em=agora(),
    )
    db.add(chamado)
    await db.commit()
    return {"id": chamado.id, "status": chamado.status}


@router.get("/api/chamados")
async def listar_chamados(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)
):
    chamados = (
        (
            await db.execute(
                select(Chamado)
                .options(selectinload(Chamado.computador))
                .order_by(Chamado.id.desc())
            )
        )
        .scalars()
        .all()
    )
    await expirar_pendentes(db)
    await db.commit()
    acessos = (
        (
            await db.execute(
                select(AcessoRemoto)
                .options(selectinload(AcessoRemoto.solicitante))
                .order_by(AcessoRemoto.id.desc())
            )
        )
        .scalars()
        .all()
    )
    chamados_por_id = {chamado.id: chamado for chamado in chamados}
    historico: dict[int, list[dict]] = {}
    for acesso in acessos:
        historico.setdefault(acesso.chamado_id, []).append(
            {
                "id": acesso.id,
                "chamado_id": acesso.chamado_id,
                "computador_id": acesso.computador_id,
                "computador_nome": chamados_por_id[acesso.chamado_id].computador.nome,
                "motivo": chamados_por_id[acesso.chamado_id].descricao,
                "solicitante": acesso.solicitante.nome,
                "solicitante_id": acesso.solicitante_id,
                "autorizado_por_id": acesso.autorizado_por_id,
                "autorizado_em": acesso.autorizado_em.isoformat() if acesso.autorizado_em else None,
                "respondido_por_id": acesso.respondido_por_id,
                "respondido_em": acesso.respondido_em.isoformat() if acesso.respondido_em else None,
                "encerrado_por_id": acesso.encerrado_por_id,
                "sessao_remota_ativa": False,
                "resultado": acesso.resultado,
                "inicio_em": acesso.inicio_em.isoformat(),
                "fim_em": acesso.fim_em.isoformat() if acesso.fim_em else None,
                "expira_em": acesso.expira_em.isoformat() if acesso.expira_em else None,
                "acesso_url": None,  # Fail closed ate existir revogacao real MeshCentral.
            }
        )
    return [
        {
            "id": chamado.id,
            "computador_id": chamado.computador_id,
            "computador_nome": chamado.computador.nome,
            "grupo": chamado.computador.grupo,
            "descricao": chamado.descricao,
            "status": chamado.status,
            "criado_em": chamado.criado_em.isoformat(),
            "solucao": chamado.solucao,
            "acessos": historico.get(chamado.id, []),
        }
        for chamado in chamados
    ]


@router.get("/api/computadores")
async def listar_computadores(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte)
):
    computadores = (
        (
            await db.execute(
                select(Computador).options(selectinload(Computador.dono)).order_by(Computador.nome)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "nome": item.nome,
            "grupo": item.grupo,
            "dono_id": item.dono_id,
            "dono_nome": item.dono.nome if item.dono else None,
            "mesh_node_id": item.mesh_node_id,
        }
        for item in computadores
    ]


@router.post("/api/computadores")
async def cadastrar_computador(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    nome = dados.get("nome", "").strip()
    grupo = dados.get("grupo", "")
    dono_id = dados.get("dono_id", "")
    dono = await db.get(Usuario, int(dono_id)) if dono_id.isdecimal() else None
    mesh_node_id = dados.get("mesh_node_id", "").strip() or None
    if (
        not nome
        or len(nome) > 120
        or grupo not in {"empresa", "dono"}
        or dono is None
        or (mesh_node_id and len(mesh_node_id) > 255)
    ):
        raise HTTPException(status_code=422, detail="Dados do computador inválidos")
    if (await db.execute(select(Computador.id).where(Computador.nome == nome))).first():
        raise HTTPException(status_code=409, detail="Nome do computador já existe")
    if mesh_node_id:
        partes = mesh_node_id.split("/")
        if len(partes) != 3 or partes[0] != "node" or not partes[2]:
            raise HTTPException(status_code=422, detail="Mesh node ID invalido")
        if (await db.execute(select(Computador.id).where(Computador.mesh_node_id == mesh_node_id))).first():
            raise HTTPException(status_code=409, detail="No MeshCentral ja cadastrado")
    computador = Computador(nome=nome, grupo=grupo, dono_id=dono.id, mesh_node_id=mesh_node_id)
    db.add(computador)
    await db.commit()
    return {"id": computador.id}


@router.post("/api/chamados/{chamado_id}/acessos")
async def solicitar_acesso(
    chamado_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(suporte),
):
    chamado = (
        await db.execute(
            select(Chamado)
            .options(selectinload(Chamado.computador))
            .where(Chamado.id == chamado_id)
        )
    ).scalar_one_or_none()
    if chamado is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")
    if chamado.computador.grupo == "dono":
        raise HTTPException(
            status_code=403,
            detail="O PC do dono não permite acesso remoto pela administração",
        )
    if chamado.status == "fechado":
        raise HTTPException(status_code=409, detail="Chamado fechado")
    await expirar_pendentes(db)
    pendente = (await db.execute(select(AcessoRemoto.id).where(AcessoRemoto.computador_id == chamado.computador_id, AcessoRemoto.resultado == "pendente"))).first()
    if pendente:
        raise HTTPException(status_code=409, detail="Ja existe uma solicitacao pendente para este computador")
    provider = provider_remoto_atual()
    resultado = await provider.solicitar_acesso(chamado.computador)
    if resultado not in {"pendente", "recusado", "cancelado", "simulado"}:
        raise HTTPException(status_code=502, detail="Resultado inválido do provider remoto")
    instante = agora()
    atualizado = await db.execute(
        update(Chamado)
        .where(Chamado.id == chamado.id, Chamado.status != "fechado")
        .values(status="em_atendimento")
    )
    if atualizado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Chamado fechado")
    acesso = AcessoRemoto(
        chamado_id=chamado.id,
        solicitante_id=user.user_id,
        computador_id=chamado.computador_id,
        inicio_em=instante,
        fim_em=instante if resultado in {"recusado", "cancelado", "simulado"} else None,
        expira_em=instante + timedelta(seconds=60) if resultado == "pendente" else None,
        resultado=resultado,
    )
    db.add(acesso)
    await db.commit()
    return {"id": acesso.id, "resultado": acesso.resultado,
            "acesso_url": None}


@router.post("/api/chamados/{chamado_id}/fechar")
async def fechar_chamado(
    chamado_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(suporte),
):
    dados = await form(request)
    solucao = dados.get("solucao", "").strip()
    if not 3 <= len(solucao) <= 4000:
        raise HTTPException(status_code=422, detail="Descreva a solução")
    resultado = await db.execute(
        update(Chamado)
        .where(Chamado.id == chamado_id, Chamado.status != "fechado")
        .values(status="fechado", solucao=solucao)
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Chamado não encontrado ou já fechado")
    await db.execute(update(AcessoRemoto).where(AcessoRemoto.chamado_id == chamado_id, AcessoRemoto.resultado.in_(["pendente", "autorizado"])).values(resultado="encerrado", fim_em=agora(), encerrado_por_id=user.user_id))
    await db.commit()
    return {"status": "fechado"}


@router.get("/api/meus-acessos")
async def meus_acessos(db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(vendedor)):
    await expirar_pendentes(db)
    acessos = (
        await db.execute(
            select(AcessoRemoto, Computador.nome, Chamado.descricao)
            .join(Computador, AcessoRemoto.computador_id == Computador.id)
            .join(Chamado, AcessoRemoto.chamado_id == Chamado.id)
            .options(selectinload(AcessoRemoto.solicitante))
            .where(
                Computador.dono_id == user.user_id,
                Computador.grupo == "empresa",
                AcessoRemoto.resultado.in_(["pendente", "autorizado"]),
            )
            .order_by(AcessoRemoto.id.desc())
        )
    ).all()
    await db.commit()
    return [
        serializar_acesso(acesso, computador_nome, motivo)
        for acesso, computador_nome, motivo in acessos
    ]


@router.post("/api/meus-acessos/{acesso_id}/decisao")
async def decidir_acesso(acesso_id: int, request: Request, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(vendedor)):
    dados = await form(request)
    decisao = dados.get("decisao")
    if decisao not in {"autorizar", "recusar"}:
        raise HTTPException(status_code=422, detail="Decisao invalida")
    await expirar_pendentes(db)
    instante = agora()
    resultado = "autorizado" if decisao == "autorizar" else "recusado"
    atualizacao = await db.execute(update(AcessoRemoto).where(AcessoRemoto.id == acesso_id, AcessoRemoto.resultado == "pendente", AcessoRemoto.expira_em > instante, AcessoRemoto.computador_id.in_(select(Computador.id).where(Computador.dono_id == user.user_id, Computador.grupo == "empresa"))).values(resultado=resultado, autorizado_por_id=user.user_id if decisao == "autorizar" else None, autorizado_em=instante if decisao == "autorizar" else None, respondido_por_id=user.user_id, respondido_em=instante, fim_em=instante if decisao == "recusar" else None))
    if atualizacao.rowcount != 1:
        await db.commit()  # preserva a expiracao realizada antes da tentativa invalida
        raise HTTPException(status_code=409, detail="Solicitacao expirada, encerrada ou nao autorizada")
    await db.commit()
    return {"resultado": resultado, "acesso_url": None, "detalhe": "Consentimento registrado; conexao MeshCentral permanece desabilitada"}


@router.post("/api/meus-acessos/{acesso_id}/encerrar")
async def encerrar_meu_acesso(acesso_id: int, db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(vendedor)):
    instante = agora()
    atualizado = await db.execute(update(AcessoRemoto).where(AcessoRemoto.id == acesso_id, AcessoRemoto.resultado.in_(["pendente", "autorizado"]), AcessoRemoto.computador_id.in_(select(Computador.id).where(Computador.dono_id == user.user_id, Computador.grupo == "empresa"))).values(resultado="encerrado", fim_em=instante, encerrado_por_id=user.user_id))
    if atualizado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Solicitacao ja finalizada ou nao autorizada")
    await db.commit()
    return {"resultado": "encerrado"}


def serializar_sessao(
    sessao: SessaoMeshCentral, computador_nome: str, chamado_id: int | None, motivo: str | None
) -> dict:
    return {
        "id": sessao.id,
        "computador_id": sessao.computador_id,
        "computador_nome": computador_nome,
        "chamado_id": chamado_id,
        "motivo": motivo,
        "mesh_session_id": sessao.mesh_session_id,
        "mesh_username": sessao.mesh_username,
        "mesh_user_id": sessao.mesh_user_id,
        "acesso_id": sessao.acesso_id,
        "autorizacao_correlacionada": sessao.acesso_id is not None,
        "estado": sessao.estado,
        "inicio_em": sessao.inicio_em.isoformat() if sessao.inicio_em else None,
        "fim_em": sessao.fim_em.isoformat() if sessao.fim_em else None,
    }


@router.get("/api/meus-sessoes-remotas")
async def sessoes_remotas_do_colaborador(
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(vendedor),
):
    registros = (await db.execute(
        select(SessaoMeshCentral, Computador.nome, Chamado.id, Chamado.descricao)
        .join(Computador, SessaoMeshCentral.computador_id == Computador.id)
        .outerjoin(AcessoRemoto, SessaoMeshCentral.acesso_id == AcessoRemoto.id)
        .outerjoin(Chamado, AcessoRemoto.chamado_id == Chamado.id)
        .where(Computador.dono_id == user.user_id, Computador.grupo == "empresa")
        .order_by(SessaoMeshCentral.id.desc()).limit(50)
    )).all()
    return {
        "monitor_conectado": monitor_conectado(),
        "sessoes": [serializar_sessao(s, nome, chamado_id, motivo)
            for s, nome, chamado_id, motivo in registros],
    }


@router.get("/api/chamados/sessoes-remotas")
async def auditar_sessoes_remotas(
    db: AsyncSession = Depends(get_db), user: UsuarioAtual = Depends(suporte),
):
    registros = (await db.execute(
        select(SessaoMeshCentral, Computador.nome, Chamado.id, Chamado.descricao)
        .join(Computador, SessaoMeshCentral.computador_id == Computador.id)
        .outerjoin(AcessoRemoto, SessaoMeshCentral.acesso_id == AcessoRemoto.id)
        .outerjoin(Chamado, AcessoRemoto.chamado_id == Chamado.id)
        .order_by(SessaoMeshCentral.id.desc()).limit(200)
    )).all()
    return {
        "monitor_conectado": monitor_conectado(),
        "sessoes": [serializar_sessao(s, nome, chamado_id, motivo)
            for s, nome, chamado_id, motivo in registros],
    }


@router.post("/api/computadores/{computador_id}/mesh-node")
async def vincular_no_meshcentral(
    computador_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    nodeid = dados.get("mesh_node_id", "").strip()
    if (not nodeid.startswith("node/") or len(nodeid.split("/")) != 3
            or not nodeid.split("/")[2] or len(nodeid) > 255):
        raise HTTPException(status_code=422, detail="Informe o ID completo node/<dominio>/<identificador>")
    pc = await db.get(Computador, computador_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Computador nao encontrado")
    outro = (await db.execute(select(Computador.id).where(
        Computador.mesh_node_id == nodeid, Computador.id != computador_id
    ))).first()
    if outro:
        raise HTTPException(status_code=409, detail="No MeshCentral vinculado a outro computador")
    pc.mesh_node_id = nodeid
    await db.commit()
    return {"computador_id": pc.id, "mesh_node_id": nodeid}


@router.post("/api/gestor/usuarios/{usuario_id}/meshcentral")
async def vincular_operador_meshcentral(
    usuario_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    mesh_id = dados.get("mesh_user_id", "").strip()
    if (not mesh_id.startswith("user/") or len(mesh_id.split("/")) != 3
            or any(not parte for parte in mesh_id.split("/")[2:]) or len(mesh_id) > 255):
        raise HTTPException(status_code=422, detail="Informe o MeshCentral user/<dominio>/<login>")
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None or usuario.role not in {"gestor", "supervisor"}:
        raise HTTPException(status_code=404, detail="Tecnico nao encontrado")
    outro = (await db.execute(select(Usuario.id).where(
        Usuario.mesh_user_id == mesh_id, Usuario.id != usuario_id
    ))).first()
    if outro:
        raise HTTPException(status_code=409, detail="Identidade MeshCentral ja vinculada")
    usuario.mesh_user_id = mesh_id
    await db.commit()
    return {"usuario_id": usuario.id, "mesh_user_id": mesh_id}
