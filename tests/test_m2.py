from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Atribuicao, Conversa, Mensagem, Usuario
from app.providers import MensagemEntrada, simulador_provider
from app.services.atendimento import proximo_disponivel, receber_mensagem, verificar_timers
from app.services.chatbot import MENU_SETOR, processar_mensagem
from test_m1 import entrar

BASE = datetime(2026, 10, 26, 12, 0, 0)


async def enviar(maker, numero: str, texto: str, identidade: str):
    async with maker() as db:
        await receber_mensagem(db, simulador_provider, MensagemEntrada(identidade, numero, texto))


async def timer(maker):
    async with maker() as db:
        await verificar_timers(db, simulador_provider)


async def dados(maker, numero):
    async with maker() as db:
        conversa = (await db.execute(select(Conversa).where(Conversa.numero == numero))).scalar_one()
        mensagens = list((await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars())
        atribuicoes = list((await db.execute(select(Atribuicao).where(Atribuicao.conversa_id == conversa.id).order_by(Atribuicao.id))).scalars())
        return conversa, mensagens, atribuicoes


async def test_chatbot_puro_e_entrada_invalida_repete_menu(ambiente):
    _, maker = ambiente
    assert processar_mensagem("menu_setor", "x") == ("menu_setor", [MENU_SETOR], None)
    assert processar_mensagem("atribuida", "1") == ("atribuida", [], None)
    await enviar(maker, "5511888001", "x", "inv-1")
    conversa, mensagens, _ = await dados(maker, "5511888001")
    assert conversa.etapa == "menu_setor"
    assert mensagens[-1].texto == MENU_SETOR
    await enviar(maker, "5511888001", "1", "inv-2")
    conversa, mensagens, _ = await dados(maker, "5511888001")
    assert conversa.etapa == "menu_vendedor"
    assert "0 - próximo disponível" in mensagens[-1].texto
    await enviar(maker, "5511888001", "9", "inv-3")
    conversa, mensagens, _ = await dados(maker, "5511888001")
    assert conversa.etapa == "menu_vendedor"
    assert "Escolha um vendedor" in mensagens[-1].texto


async def test_opcao_zero_escolhe_menos_conversas_e_historico_original(ambiente, monkeypatch):
    _, maker = ambiente
    monkeypatch.setattr("app.services.atendimento.now", lambda: BASE)
    await enviar(maker, "5511888002", "1", "zero-1")
    await enviar(maker, "5511888002", "0", "zero-2")
    conversa, mensagens, atribuicoes = await dados(maker, "5511888002")
    assert conversa.atribuido_id == 5  # C tinha zero; A e B já tinham uma aberta.
    assert conversa.etapa == "atribuida"
    assert [(a.de_usuario_id, a.para_usuario_id) for a in atribuicoes] == [(None, 5)]
    assert "Vendedor C" in mensagens[-1].texto
    assert conversa.timer_prazo_em == BASE + timedelta(seconds=90)


async def test_desempate_por_ultima_atribuicao_e_somente_online(ambiente):
    _, maker = ambiente
    async with maker() as db:
        db.add(Conversa(numero="5511777000", setor_id=1, atribuido_id=5, status="aberta", etapa="atribuida", timer_extensoes=0))
        for usuario_id, segundos in [(2, 20), (3, 0), (5, 10)]:
            usuario = await db.get(Usuario, usuario_id)
            usuario.ultima_atribuicao_em = BASE + timedelta(seconds=segundos)
        await db.commit()
    async with maker() as db:
        assert (await proximo_disponivel(db)).id == 3
        vendedor_b = await db.get(Usuario, 3)
        vendedor_b.online = False
        await db.commit()
    async with maker() as db:
        assert (await proximo_disponivel(db)).id == 5


async def test_timer_avisa_em_90_e_transfere_em_150(ambiente, monkeypatch):
    _, maker = ambiente
    instante = [BASE]
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888003", "1", "tempo-1")
    await enviar(maker, "5511888003", "1", "tempo-2")  # Vendedor A
    instante[0] = BASE + timedelta(seconds=89)
    await timer(maker)
    conversa, mensagens, _ = await dados(maker, "5511888003")
    assert conversa.etapa == "atribuida"
    assert not any("Transferiremos" in m.texto for m in mensagens)
    instante[0] = BASE + timedelta(seconds=90)
    await timer(maker)
    conversa, mensagens, _ = await dados(maker, "5511888003")
    assert conversa.etapa == "aviso_transferencia"
    assert conversa.timer_prazo_em == BASE + timedelta(seconds=150)
    assert "Transferiremos em 60 segundos" in mensagens[-1].texto
    instante[0] = BASE + timedelta(seconds=150)
    await timer(maker)
    conversa, mensagens, atribuicoes = await dados(maker, "5511888003")
    assert conversa.atribuido_id == 5
    assert [(a.de_usuario_id, a.para_usuario_id, a.motivo) for a in atribuicoes] == [
        (None, 2, "escolha_cliente"), (2, 5, "timer")]
    assert "Vendedor C" in mensagens[-1].texto


async def test_cliente_estende_ate_210_segundos(ambiente, monkeypatch):
    _, maker = ambiente
    instante = [BASE]
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888004", "1", "ext-1")
    await enviar(maker, "5511888004", "1", "ext-2")
    instante[0] = BASE + timedelta(seconds=90)
    await timer(maker)
    instante[0] = BASE + timedelta(seconds=100)
    await enviar(maker, "5511888004", "1", "ext-3")
    conversa, _, _ = await dados(maker, "5511888004")
    assert conversa.timer_prazo_em == BASE + timedelta(seconds=210)
    instante[0] = BASE + timedelta(seconds=130)
    await enviar(maker, "5511888004", "1", "ext-4")
    conversa, _, _ = await dados(maker, "5511888004")
    assert conversa.timer_prazo_em == BASE + timedelta(seconds=210)
    instante[0] = BASE + timedelta(seconds=209)
    await timer(maker)
    conversa, _, _ = await dados(maker, "5511888004")
    assert conversa.atribuido_id == 2
    instante[0] = BASE + timedelta(seconds=210)
    await timer(maker)
    conversa, _, historico = await dados(maker, "5511888004")
    assert conversa.atribuido_id == 5
    assert len(historico) == 2


async def test_duas_tentativas_sem_resposta_entram_em_standby_sem_repetir_bot(ambiente, monkeypatch):
    _, maker = ambiente
    instante = [BASE]
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888080", "1", "stand-1")
    await enviar(maker, "5511888080", "1", "stand-2")
    for segundos in (90, 150, 240, 300):
        instante[0] = BASE + timedelta(seconds=segundos)
        await timer(maker)
    conversa, mensagens, historico = await dados(maker, "5511888080")
    assert conversa.etapa == "standby"
    assert conversa.timer_prazo_em is None
    assert conversa.tentativas_timer == 2
    assert len(historico) == 2
    assert "ficou em espera" in mensagens[-1].texto
    quantidade = len(mensagens)
    instante[0] = BASE + timedelta(seconds=600)
    await timer(maker)
    await enviar(maker, "5511888080", "1", "stand-3")
    assert len((await dados(maker, "5511888080"))[1]) == quantidade + 1


async def test_fora_expediente_responde_uma_vez_e_reabre_no_inicio(ambiente, monkeypatch):
    _, maker = ambiente
    from app.core.config import get_settings
    config = get_settings().model_copy(update={"expediente_inicio": "07:00", "expediente_fim": "18:30"})
    monkeypatch.setattr("app.services.atendimento.get_settings", lambda: config)
    instante = [datetime(2026, 10, 26, 23, 0, 0)]  # 20h em São Paulo.
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888081", "oi", "fora-1")
    await enviar(maker, "5511888081", "oi de novo", "fora-2")
    conversa, mensagens, _ = await dados(maker, "5511888081")
    assert conversa.etapa == "fora_expediente"
    assert [m.origem for m in mensagens] == ["cliente", "bot", "cliente"]
    instante[0] = datetime(2026, 10, 27, 10, 0, 0)  # 7h em São Paulo.
    await timer(maker)
    await timer(maker)
    conversa, mensagens, _ = await dados(maker, "5511888081")
    assert conversa.etapa == "menu_setor"
    assert len([m for m in mensagens if m.origem == "bot"]) == 2
    assert "Estamos de volta" in mensagens[-1].texto and "Escolha o setor" in mensagens[-1].texto


async def test_timer_pausa_ao_fechar_expediente_sem_enviar_aviso(ambiente, monkeypatch):
    _, maker = ambiente
    from app.core.config import get_settings
    config = get_settings().model_copy(update={"expediente_inicio": "07:00", "expediente_fim": "18:30"})
    monkeypatch.setattr("app.services.atendimento.get_settings", lambda: config)
    instante = [datetime(2026, 10, 26, 20, 0, 0)]  # 17h em São Paulo.
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888082", "1", "pausa-1")
    await enviar(maker, "5511888082", "1", "pausa-2")
    conversa, mensagens, _ = await dados(maker, "5511888082")
    quantidade = len(mensagens)
    instante[0] = datetime(2026, 10, 26, 22, 0, 0)  # 19h em São Paulo.
    await timer(maker)
    conversa, mensagens, _ = await dados(maker, "5511888082")
    assert conversa.etapa == "fora_expediente"
    assert conversa.timer_prazo_em is None
    assert len(mensagens) == quantidade


async def test_primeira_resposta_humana_cancela_timer(ambiente, monkeypatch):
    client, maker = ambiente
    instante = [BASE]
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await enviar(maker, "5511888005", "1", "hum-1")
    await enviar(maker, "5511888005", "1", "hum-2")
    conversa, _, _ = await dados(maker, "5511888005")
    await entrar(client, "a@teste.local")
    assert (await client.post(f"/api/atendimentos/{conversa.id}/mensagens", data={"texto": "Bom dia"})).status_code == 200
    instante[0] = BASE + timedelta(seconds=220)
    await timer(maker)
    conversa, mensagens, historico = await dados(maker, "5511888005")
    assert conversa.atribuido_id == 2
    assert conversa.timer_prazo_em is None
    assert conversa.primeira_resposta_em is not None
    assert not any("Transferiremos" in m.texto for m in mensagens)
    assert len(historico) == 1


async def test_simulador_usa_entrada_comum_e_setor_fixo(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    assert (await client.get("/api/simulador")).status_code == 200
    assert (await client.post("/api/simulador", data={"cliente": "cliente2", "texto": "oi"})).status_code == 200
    assert (await client.post("/api/simulador", data={"cliente": "cliente2", "texto": "2"})).status_code == 200
    pagina = await client.get("/api/simulador?cliente=cliente2")
    assert MENU_SETOR in [m["texto"] for m in pagina.json()["mensagens"]]
    conversa, mensagens, historico = await dados(maker, "5511999000002")
    assert conversa.setor_id == 2 and conversa.atribuido_id == 4
    assert historico[0].motivo == "setor"
    assert "Responsável" in mensagens[-1].texto
    await entrar(client, "a@teste.local")
    assert (await client.get("/api/simulador")).status_code == 403


async def test_gestor_configura_nome_e_responsavel_do_setor(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    resposta = await client.post("/api/gestor/setores/2", data={"nome": "Trocas", "responsavel_id": "6"})
    assert resposta.status_code == 200
    await enviar(maker, "5511888006", "inválido", "setor-1")
    conversa, mensagens, _ = await dados(maker, "5511888006")
    assert "2 - Trocas" in mensagens[-1].texto
    await enviar(maker, "5511888006", "2", "setor-2")
    conversa, _, historico = await dados(maker, "5511888006")
    assert conversa.atribuido_id == 6
    assert conversa.timer_prazo_em is None
    assert historico[0].para_usuario_id == 6


async def test_encerrar_conversa_grava_estado_e_respeita_isolamento(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/atendimentos/11/encerrar")).status_code == 404
    assert (await client.post("/api/atendimentos/10/encerrar")).status_code == 200
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        assert conversa.etapa == "encerrada"
        assert conversa.status == "encerrada"
        assert conversa.timer_prazo_em is None
