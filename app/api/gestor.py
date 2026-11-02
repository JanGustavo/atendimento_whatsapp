"""Rotas do painel do gestor: visão global, usuários, setores, transferências."""

import json
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._shared import form
from app.api.atendimentos import conversa_visivel
from app.api.deps import UsuarioAtual, somente_gestor
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.utils import now
from app.models import (
    Atribuicao,
    ConfiguracaoBot,
    Conversa,
    Mensagem,
    MensagemGrupo,
    LeituraInterna,
    Setor,
    SetorInterno,
    SimuladorEstado,
    Usuario,
)
from app.providers import provider_para_numero
from app.services.auth_service import get_password_hash

router = APIRouter(prefix="/api/gestor")
ICONES_SETOR = {"equipe", "vendas", "estoque", "garantia", "devolucao", "atendimento", "administracao"}


@router.post("/configuracao-bot")
async def salvar_configuracao_bot(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    try:
        horarios = json.loads(dados.get("horarios", ""))
        dias_fechados = json.loads(dados.get("dias_fechados", ""))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Agenda inválida") from None
    if not isinstance(horarios, dict) or set(horarios) != {str(i) for i in range(7)}:
        raise HTTPException(status_code=422, detail="Informe os sete dias da semana")
    for periodo in horarios.values():
        if (not isinstance(periodo, dict) or type(periodo.get("ativo")) is not bool
                or not isinstance(periodo.get("inicio"), str) or not isinstance(periodo.get("fim"), str)
                or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", periodo["inicio"])
                or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", periodo["fim"])
                or periodo["inicio"] >= periodo["fim"]):
            raise HTTPException(status_code=422, detail="Horário inválido; início deve ser antes do fim")
    if (not isinstance(dias_fechados, list) or len(dias_fechados) > 100
            or any(not isinstance(dia, str) for dia in dias_fechados)):
        raise HTTPException(status_code=422, detail="Datas fechadas inválidas")
    try:
        datas = sorted({date.fromisoformat(dia).isoformat() for dia in dias_fechados})
    except ValueError:
        raise HTTPException(status_code=422, detail="Data fechada inválida") from None
    textos = {}
    for campo in ("mensagem_fora_expediente", "mensagem_reabertura", "mensagem_standby"):
        texto = dados.get(campo, "").strip()
        if not 1 <= len(texto) <= 600:
            raise HTTPException(status_code=422, detail=f"Texto inválido: {campo}")
        textos[campo] = texto
    registro = await db.get(ConfiguracaoBot, 1)
    if registro is None:
        registro = ConfiguracaoBot(id=1)
        db.add(registro)
    registro.horarios = horarios
    registro.dias_fechados = datas
    for campo, texto in textos.items():
        setattr(registro, campo, texto)
    await db.commit()
    return {"ok": True}


@router.post("/setores-internos")
async def criar_setor_interno(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    nome = dados.get("nome", "").strip()
    icone = dados.get("icone", "equipe")
    if not 1 <= len(nome) <= 80:
        raise HTTPException(status_code=422, detail="Nome do setor inválido")
    if icone not in ICONES_SETOR:
        raise HTTPException(status_code=422, detail="Ícone inválido")
    if (await db.execute(select(SetorInterno.id).where(SetorInterno.nome == nome))).first():
        raise HTTPException(status_code=409, detail="Setor já existe")
    setor = SetorInterno(nome=nome, icone=icone)
    db.add(setor)
    await db.commit()
    return {"id": setor.id, "nome": setor.nome, "icone": setor.icone}


@router.post("/setores-internos/{setor_id}")
async def renomear_setor_interno(
    setor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    setor = await db.get(SetorInterno, setor_id)
    if setor is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    dados = await form(request)
    nome = dados.get("nome", "").strip()
    icone = dados.get("icone", setor.icone)
    if not 1 <= len(nome) <= 80:
        raise HTTPException(status_code=422, detail="Nome do setor inválido")
    if icone not in ICONES_SETOR:
        raise HTTPException(status_code=422, detail="Ícone inválido")
    if (
        nome != setor.nome
        and (await db.execute(select(SetorInterno.id).where(SetorInterno.nome == nome))).first()
    ):
        raise HTTPException(status_code=409, detail="Setor já existe")
    setor.nome = nome
    setor.icone = icone
    await db.commit()
    return {"id": setor.id, "nome": setor.nome, "icone": setor.icone}


@router.delete("/setores-internos/{setor_id}")
async def excluir_setor_interno(
    setor_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    setor = await db.get(SetorInterno, setor_id)
    if setor is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    if setor.id == 1:
        raise HTTPException(status_code=409, detail="O setor Vendas é necessário para distribuir atendimentos")
    if (await db.execute(select(Usuario.id).where(Usuario.setor_interno_id == setor_id).limit(1))).first():
        raise HTTPException(status_code=409, detail="Remova ou transfira os usuários vinculados antes de excluir")
    if (await db.execute(select(MensagemGrupo.id).where(MensagemGrupo.setor_id == setor_id).limit(1))).first():
        raise HTTPException(status_code=409, detail="Este setor possui mensagens no chat interno e não pode ser excluído")
    if (await db.execute(select(LeituraInterna.id).where(
        LeituraInterna.tipo == "grupo", LeituraInterna.alvo_id == setor_id
    ).limit(1))).first():
        raise HTTPException(status_code=409, detail="Este setor possui histórico de leitura e não pode ser excluído")
    await db.delete(setor)
    await db.commit()
    return {"ok": True}


@router.post("/simulador")
async def configurar_simulador(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    if not get_settings().enable_simulator:
        raise HTTPException(status_code=404, detail="Simulador desativado")
    dados = await form(request)
    estado = await db.get(SimuladorEstado, 1)
    if estado is None:
        estado = SimuladorEstado(id=1, ativo=False)
        db.add(estado)
    estado.ativo = dados.get("ativo") == "on"
    await db.commit()
    return {"ativo": estado.ativo}


@router.post("/usuarios")
async def criar_usuario(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    dados = await form(request)
    role = dados.get("role", "")
    nome = " ".join(dados.get("nome", "").split())
    if not 1 <= len(nome) <= 120:
        raise HTTPException(status_code=422, detail="Nome deve ter de 1 a 120 caracteres")
    if role not in {"colaborador", "supervisor", "gestor"} or len(dados.get("senha", "")) < 8:
        raise HTTPException(status_code=422, detail="Papel ou senha inválidos")
    email = dados.get("email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if (await db.execute(select(Usuario.id).where(Usuario.email == email))).first():
        raise HTTPException(status_code=409, detail="Email já existe")
    setor_interno_id = dados.get("setor_interno_id") or str(
        {"colaborador": 1, "supervisor": 3, "gestor": 4}[role]
    )
    setor_interno = (
        await db.get(SetorInterno, int(setor_interno_id)) if setor_interno_id.isdecimal() else None
    )
    if setor_interno is None:
        raise HTTPException(status_code=422, detail="Setor interno inválido")
    db.add(
        Usuario(
            nome=nome,
            email=email,
            senha_hash=get_password_hash(dados["senha"]),
            role=role,
            ativo=True,
            online=True,
            setor_interno_id=setor_interno.id,
        )
    )
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
    if role not in {"colaborador", "supervisor", "gestor"}:
        raise HTTPException(status_code=422)
    email = dados.get("email", usuario.email).strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    if (
        email != usuario.email
        and (await db.execute(select(Usuario.id).where(Usuario.email == email))).first()
    ):
        raise HTTPException(status_code=409, detail="Email já existe")
    nome = " ".join(dados.get("nome", usuario.nome).split())
    if not 1 <= len(nome) <= 120:
        raise HTTPException(status_code=422, detail="Nome deve ter de 1 a 120 caracteres")
    usuario.nome = nome
    usuario.email = email
    usuario.role = role
    usuario.ativo = dados.get("ativo") == "on"
    usuario.online = dados.get("online") == "on"
    if "setor_interno_id" in dados:
        setor_id = dados["setor_interno_id"]
        if setor_id:
            setor_interno = await db.get(SetorInterno, int(setor_id)) if setor_id.isdecimal() else None
            if setor_interno is None:
                raise HTTPException(status_code=422, detail="Setor interno inválido")
            usuario.setor_interno_id = setor_interno.id
        else:
            usuario.setor_interno_id = None
    if dados.get("senha"):
        if len(dados["senha"]) < 8:
            raise HTTPException(status_code=422)
        usuario.senha_hash = get_password_hash(dados["senha"])
    await db.commit()
    return {"ok": True}


@router.delete("/usuarios/{usuario_id}")
async def excluir_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    user: UsuarioAtual = Depends(somente_gestor),
):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if usuario_id == user.user_id:
        raise HTTPException(status_code=409, detail="Não é possível excluir sua própria conta")
    # As referências compõem a auditoria. Excluir só é permitido antes do primeiro uso.
    for tabela in Base.metadata.tables.values():
        for coluna in tabela.columns:
            if any(chave.target_fullname == "usuarios.id" for chave in coluna.foreign_keys):
                if (await db.execute(select(coluna).where(coluna == usuario_id).limit(1))).first():
                    raise HTTPException(status_code=409, detail="Usuário possui histórico ou vínculos. Desative a conta para preservar a auditoria")
    await db.delete(usuario)
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
    icone = dados.get("icone", setor.icone)
    if not nome or len(nome) > 80:
        raise HTTPException(status_code=422, detail="Nome do setor inválido")
    if icone not in ICONES_SETOR:
        raise HTTPException(status_code=422, detail="Ícone inválido")
    ordem_texto = dados.get("ordem", str(setor.ordem))
    if not ordem_texto.isdecimal() or int(ordem_texto) not in {1, 2, 3, 4}:
        raise HTTPException(status_code=422, detail="Opção do menu inválida")
    nova_ordem = int(ordem_texto)
    if (setor.ordem == 1) != (nova_ordem == 1):
        raise HTTPException(status_code=422, detail="A opção 1 é reservada a Vendas")
    if (
        nome != setor.nome
        and (await db.execute(select(Setor.id).where(Setor.nome == nome))).first()
    ):
        raise HTTPException(status_code=409, detail="Setor já existe")
    responsavel_id = dados.get("responsavel_id", "")
    responsavel = await db.get(Usuario, int(responsavel_id)) if responsavel_id.isdecimal() else None
    if setor.ordem != 1 and (
        responsavel is None or responsavel.role != "supervisor" or not responsavel.ativo
    ):
        raise HTTPException(status_code=422, detail="Responsável inválido")
    setor.nome = nome
    setor.icone = icone
    setor.responsavel_id = responsavel.id if responsavel else None
    if nova_ordem != setor.ordem:
        outro = (await db.execute(select(Setor).where(Setor.ordem == nova_ordem))).scalar_one_or_none()
        if outro is None:
            raise HTTPException(status_code=422, detail="Opção do menu não encontrada")
        antiga_ordem = setor.ordem
        await db.execute(update(Setor).where(Setor.id == setor.id).values(ordem=-setor.id))
        await db.execute(update(Setor).where(Setor.id == outro.id).values(ordem=antiga_ordem))
        await db.execute(update(Setor).where(Setor.id == setor.id).values(ordem=nova_ordem))
        db.expire(setor)
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
    if (
        alvo is None
        or not alvo.ativo
        or (vendas and (alvo.role != "colaborador" or alvo.setor_interno_id != 1))
        or (not vendas and alvo.role != "supervisor")
    ):
        raise HTTPException(status_code=422, detail="Destino inválido")
    antigo = conversa.atribuido_id
    if antigo is not None and antigo == alvo.id:
        raise HTTPException(status_code=409, detail="Conversa já atribuída a este usuário")
    instante = now()
    condicoes = [
        Conversa.id == conversa_id,
        Conversa.status == "aberta",
    ]
    if antigo is not None:
        condicoes.append(Conversa.atribuido_id == antigo)
    else:
        condicoes.append(Conversa.atribuido_id.is_(None))
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes)
        .values(
            atribuido_id=alvo.id,
            etapa="atribuida",
            primeira_resposta_em=None,
            timer_inicio_em=instante if vendas else None,
            timer_prazo_em=instante + timedelta(seconds=get_settings().timer_espera_segundos)
            if vendas
            else None,
            timer_aviso_em=None,
            timer_extensoes=0,
            tentativas_timer=1 if vendas else 0,
        )
    )
    if resultado.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conversa já transferida")
    db.add(
        Atribuicao(
            conversa_id=conversa_id,
            de_usuario_id=antigo,
            para_usuario_id=alvo.id,
            motivo="gestor",
            criada_em=instante,
        )
    )
    alvo.ultima_atribuicao_em = instante
    config = get_settings()
    if config.aviso_transferencia_ativo:
        texto = config.aviso_transferencia_texto.replace("{nome}", alvo.nome)
        mensagem = Mensagem(
            conversa_id=conversa.id,
            origem="bot",
            texto=texto,
            envio_status="pendente",
            criada_em=now(),
        )
        db.add(mensagem)
        await db.flush()
        try:
            mensagem.provider_id = await provider_para_numero(conversa.numero).enviar_texto(
                conversa.numero, texto
            )
        except Exception:
            mensagem.envio_status = "falhou"
            await db.commit()
            raise HTTPException(
                status_code=502,
                detail="Transferência salva, mas o aviso ao cliente falhou.",
            )
        mensagem.envio_status = "enviada"
    await db.commit()
    return {"ok": True}
