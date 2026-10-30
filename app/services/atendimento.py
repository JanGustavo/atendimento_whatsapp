"""Aplica as transições do chatbot e executa os prazos persistidos."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.utils import now
from app.models import Atribuicao, Conversa, Mensagem, Setor, Usuario
from app.providers import MensagemEntrada, WhatsAppProvider
from app.services.chatbot import MENU_SETOR, processar_mensagem


def em_expediente(instante: datetime) -> bool:
    config = get_settings()
    horario = instante.replace(tzinfo=UTC).astimezone(ZoneInfo(config.expediente_fuso)).time()
    inicio = time.fromisoformat(config.expediente_inicio)
    fim = time.fromisoformat(config.expediente_fim)
    return inicio <= horario < fim if inicio < fim else horario >= inicio or horario < fim


def menu_vendedores(vendedores: list[Usuario]) -> str:
    linhas = ["Escolha um vendedor:"]
    linhas.extend(f"{i} - {v.nome}" for i, v in enumerate(vendedores, 1))
    linhas.append("0 - próximo disponível")
    return "\n".join(linhas)


async def menu_setores(db: AsyncSession) -> str:
    setores = (await db.execute(select(Setor).order_by(Setor.ordem))).scalars().all()
    return "Escolha o setor:\n" + "\n".join(f"{setor.ordem} - {setor.nome}" for setor in setores)


async def vendedores_ativos(db: AsyncSession) -> list[Usuario]:
    return list(
        (
            await db.execute(
                select(Usuario)
                .where(
                    Usuario.role == "colaborador",
                    Usuario.setor_interno_id == 1,
                    Usuario.ativo.is_(True),
                )
                .order_by(Usuario.id)
            )
        ).scalars()
    )


async def proximo_disponivel(db: AsyncSession, excluir_id: int | None = None) -> Usuario | None:
    vendedores = (
        (
            await db.execute(
                select(Usuario)
                .where(
                    Usuario.role == "colaborador",
                    Usuario.setor_interno_id == 1,
                    Usuario.ativo.is_(True),
                    Usuario.online.is_(True),
                )
                .order_by(Usuario.id)
            )
        )
        .scalars()
        .all()
    )
    vendedores = [v for v in vendedores if v.id != excluir_id]
    if not vendedores:
        return None
    contagens = dict(
        (
            await db.execute(
                select(Conversa.atribuido_id, func.count(Conversa.id))
                .where(Conversa.status == "aberta", Conversa.atribuido_id.is_not(None))
                .group_by(Conversa.atribuido_id)
            )
        ).all()
    )
    return min(
        vendedores,
        key=lambda v: (
            contagens.get(v.id, 0),
            v.ultima_atribuicao_em or datetime.min,
            v.id,
        ),
    )


async def _registrar_bot(
    db: AsyncSession, conversa: Conversa, texto: str, provider: WhatsAppProvider
) -> None:
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
        mensagem.provider_id = await provider.enviar_texto(conversa.numero, texto)
    except Exception:
        mensagem.envio_status = "falhou"
    else:
        mensagem.envio_status = "enviada"


async def _atribuir(
    db: AsyncSession,
    conversa: Conversa,
    usuario: Usuario,
    motivo: str,
    estado_esperado: str,
    provider: WhatsAppProvider,
) -> bool:
    instante = now()
    setor = await db.get(Setor, conversa.setor_id) if conversa.setor_id else None
    prazo = (
        instante + timedelta(seconds=get_settings().timer_espera_segundos)
        if setor and setor.ordem == 1
        else None
    )
    antigo = conversa.atribuido_id
    condicoes = [
        Conversa.id == conversa.id,
        Conversa.etapa == estado_esperado,
        Conversa.atribuido_id == antigo,
        Conversa.status == "aberta",
    ]
    if motivo == "timer":
        condicoes.extend(
            [
                Conversa.primeira_resposta_em.is_(None),
                Conversa.timer_prazo_em <= instante,
            ]
        )
    resultado = await db.execute(
        update(Conversa)
        .where(*condicoes)
        .values(
            atribuido_id=usuario.id,
            etapa="atribuida",
            timer_inicio_em=instante if prazo else None,
            timer_prazo_em=prazo,
            timer_aviso_em=None,
            timer_extensoes=0,
            primeira_resposta_em=None,
            tentativas_timer=Conversa.tentativas_timer + 1
            if motivo == "timer"
            else 1
            if prazo
            else 0,
        )
    )
    if resultado.rowcount != 1:
        return False
    db.add(
        Atribuicao(
            conversa_id=conversa.id,
            de_usuario_id=antigo,
            para_usuario_id=usuario.id,
            motivo=motivo,
            criada_em=instante,
        )
    )
    usuario.ultima_atribuicao_em = instante
    await _registrar_bot(
        db,
        conversa,
        f"Atendimento encaminhado para {usuario.nome}. Aguarde a resposta.",
        provider,
    )
    return True


async def receber_mensagem(
    db: AsyncSession, provider: WhatsAppProvider, entrada: MensagemEntrada
) -> None:
    """Entrada única para simulador e webhook da Meta."""
    if entrada.de_mim or "@g.us" in entrada.numero or not entrada.id or not entrada.numero:
        return
    if (await db.execute(select(Mensagem.id).where(Mensagem.provider_id == entrada.id))).first():
        return
    conversa = (
        await db.execute(
            select(Conversa)
            .where(Conversa.numero == entrada.numero, Conversa.status == "aberta")
            .order_by(Conversa.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if conversa is None:
        await db.execute(
            sqlite_insert(Conversa)
            .values(
                numero=entrada.numero,
                nome_contato=entrada.nome_contato,
                etapa="menu_setor",
                status="aberta",
                timer_extensoes=0,
                criada_em=now(),
            )
            .on_conflict_do_nothing(
                index_elements=[Conversa.numero],
                index_where=Conversa.status == "aberta",
            )
        )
        conversa = (
            await db.execute(
                select(Conversa)
                .where(Conversa.numero == entrada.numero, Conversa.status == "aberta")
                .limit(1)
            )
        ).scalar_one()
    resultado = await db.execute(
        sqlite_insert(Mensagem)
        .values(
            conversa_id=conversa.id,
            origem="cliente",
            texto=entrada.texto,
            provider_id=entrada.id,
            criada_em=now(),
        )
        .on_conflict_do_nothing(index_elements=[Mensagem.provider_id])
    )
    if resultado.rowcount == 0:
        await db.rollback()
        return
    if entrada.nome_contato:
        conversa.nome_contato = entrada.nome_contato
    if conversa.primeira_resposta_em is None and not em_expediente(now()):
        if conversa.etapa != "fora_expediente":
            conversa.etapa = "fora_expediente"
            conversa.timer_prazo_em = None
            await _registrar_bot(db, conversa, get_settings().mensagem_fora_expediente, provider)
        await db.commit()
        return
    if conversa.etapa == "fora_expediente":
        # A reabertura é enviada pelo loop do lifespan, mesmo sem nova mensagem.
        await db.commit()
        return
    if entrada.tipo == "midia":
        await _registrar_bot(db, conversa, "No momento só atendemos por texto", provider)
        await db.commit()
        return
    if conversa.status != "aberta" or conversa.etapa == "encerrada":
        await db.commit()
        return
    novo_estado, respostas, acao = processar_mensagem(conversa.etapa, entrada.texto)
    if acao == "listar_vendedores":
        vendedores = await vendedores_ativos(db)
        conversa.etapa = "menu_vendedor"
        respostas.append(menu_vendedores(vendedores))
    elif acao and acao.startswith("atribuir_setor:"):
        ordem = int(acao.rsplit(":", 1)[1])
        setor = (await db.execute(select(Setor).where(Setor.ordem == ordem))).scalar_one_or_none()
        responsavel = (
            await db.get(Usuario, setor.responsavel_id) if setor and setor.responsavel_id else None
        )
        if (
            setor is None
            or responsavel is None
            or not responsavel.ativo
            or responsavel.role != "supervisor"
        ):
            respostas.append("Setor sem responsável disponível. Tente novamente.\n" + MENU_SETOR)
        else:
            conversa.setor_id = setor.id
            await db.flush()
            await _atribuir(db, conversa, responsavel, "setor", "menu_setor", provider)
    elif acao and acao.startswith("escolher_vendedor:"):
        numero = int(acao.rsplit(":", 1)[1])
        vendedores = await vendedores_ativos(db)
        escolhido = (
            await proximo_disponivel(db)
            if numero == 0
            else vendedores[numero - 1]
            if 1 <= numero <= len(vendedores)
            else None
        )
        if escolhido is None:
            respostas.append(menu_vendedores(vendedores))
        else:
            setor = (await db.execute(select(Setor).where(Setor.ordem == 1))).scalar_one_or_none()
            if setor is None:
                respostas.append("Setor Vendas indisponível. Tente novamente.")
            else:
                conversa.setor_id = setor.id
                await db.flush()
                await _atribuir(
                    db,
                    conversa,
                    escolhido,
                    "escolha_cliente" if numero else "proximo_disponivel",
                    "menu_vendedor",
                    provider,
                )
    elif acao == "estender_espera":
        config = get_settings()
        instante = now()
        if (
            conversa.timer_inicio_em
            and conversa.timer_prazo_em
            and instante < conversa.timer_prazo_em
            and conversa.primeira_resposta_em is None
        ):
            limite = conversa.timer_inicio_em + timedelta(seconds=config.timer_maximo_segundos)
            novo_prazo = min(
                conversa.timer_prazo_em + timedelta(seconds=config.timer_aviso_segundos),
                limite,
            )
            if conversa.timer_extensoes == 0 and novo_prazo > conversa.timer_prazo_em:
                resultado = await db.execute(
                    update(Conversa)
                    .where(
                        Conversa.id == conversa.id,
                        Conversa.etapa == "aviso_transferencia",
                        Conversa.atribuido_id == conversa.atribuido_id,
                        Conversa.primeira_resposta_em.is_(None),
                        Conversa.timer_prazo_em == conversa.timer_prazo_em,
                        Conversa.timer_prazo_em > instante,
                    )
                    .values(
                        timer_prazo_em=novo_prazo,
                        timer_extensoes=Conversa.timer_extensoes + 1,
                    )
                )
                if resultado.rowcount == 1:
                    respostas.append(
                        f"Tudo bem. Vamos aguardar mais {config.timer_aviso_segundos} segundos pelo vendedor."
                    )
    else:
        conversa.etapa = novo_estado
    for resposta in respostas:
        if MENU_SETOR in resposta:
            resposta = resposta.replace(MENU_SETOR, await menu_setores(db))
        await _registrar_bot(db, conversa, resposta, provider)
    await db.commit()


async def verificar_timers(db: AsyncSession, provider: WhatsAppProvider) -> None:
    config = get_settings()
    instante = now()
    if em_expediente(instante):
        pendentes = (
            (
                await db.execute(
                    select(Conversa).where(
                        Conversa.status == "aberta",
                        Conversa.etapa == "fora_expediente",
                    )
                )
            )
            .scalars()
            .all()
        )
        for conversa in pendentes:
            resultado = await db.execute(
                update(Conversa)
                .where(
                    Conversa.id == conversa.id,
                    Conversa.etapa == "fora_expediente",
                )
                .values(
                    etapa="menu_setor",
                    setor_id=None,
                    atribuido_id=None,
                    timer_inicio_em=None,
                    timer_prazo_em=None,
                    timer_aviso_em=None,
                    timer_extensoes=0,
                    tentativas_timer=0,
                )
            )
            if resultado.rowcount:
                await _registrar_bot(
                    db,
                    conversa,
                    config.mensagem_reabertura + "\n" + await menu_setores(db),
                    provider,
                )
    else:
        await db.execute(
            update(Conversa)
            .where(
                Conversa.status == "aberta",
                Conversa.primeira_resposta_em.is_(None),
                Conversa.timer_prazo_em.is_not(None),
            )
            .values(etapa="fora_expediente", timer_prazo_em=None)
        )
        await db.commit()
        return
    conversas = (
        (
            await db.execute(
                select(Conversa)
                .join(Setor, Conversa.setor_id == Setor.id)
                .where(
                    Setor.ordem == 1,
                    Conversa.status == "aberta",
                    Conversa.primeira_resposta_em.is_(None),
                    Conversa.timer_prazo_em.is_not(None),
                    Conversa.timer_prazo_em <= instante,
                )
            )
        )
        .scalars()
        .all()
    )
    for conversa in conversas:
        if conversa.etapa == "atribuida" and conversa.timer_aviso_em is None:
            prazo = min(
                conversa.timer_inicio_em
                + timedelta(seconds=config.timer_espera_segundos + config.timer_aviso_segundos),
                conversa.timer_inicio_em + timedelta(seconds=config.timer_maximo_segundos),
            )
            resultado = await db.execute(
                update(Conversa)
                .where(
                    Conversa.id == conversa.id,
                    Conversa.etapa == "atribuida",
                    Conversa.primeira_resposta_em.is_(None),
                    Conversa.timer_prazo_em <= instante,
                )
                .values(
                    etapa="aviso_transferencia",
                    timer_aviso_em=instante,
                    timer_prazo_em=prazo,
                )
            )
            if resultado.rowcount:
                await _registrar_bot(
                    db,
                    conversa,
                    f"Ainda não recebemos resposta. Transferiremos em {config.timer_aviso_segundos} segundos. Responda 1 para esperar mais {config.timer_aviso_segundos} segundos.",
                    provider,
                )
        elif conversa.etapa == "aviso_transferencia":
            if conversa.tentativas_timer >= 2:
                resultado = await db.execute(
                    update(Conversa)
                    .where(
                        Conversa.id == conversa.id,
                        Conversa.etapa == "aviso_transferencia",
                        Conversa.primeira_resposta_em.is_(None),
                        Conversa.timer_prazo_em <= instante,
                    )
                    .values(etapa="standby", timer_prazo_em=None)
                )
                if resultado.rowcount:
                    await _registrar_bot(db, conversa, config.mensagem_standby, provider)
                continue
            proximo = await proximo_disponivel(db, excluir_id=conversa.atribuido_id)
            if proximo is None:
                resultado = await db.execute(
                    update(Conversa)
                    .where(
                        Conversa.id == conversa.id,
                        Conversa.etapa == "aviso_transferencia",
                        Conversa.primeira_resposta_em.is_(None),
                        Conversa.timer_prazo_em <= instante,
                    )
                    .values(etapa="standby", timer_prazo_em=None)
                )
                if resultado.rowcount:
                    await _registrar_bot(db, conversa, config.mensagem_standby, provider)
                continue
            await _atribuir(db, conversa, proximo, "timer", "aviso_transferencia", provider)
    await db.commit()
