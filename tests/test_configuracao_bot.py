"""Agenda e textos automáticos definidos pelo gestor."""

import json
from datetime import datetime

from test_m1 import entrar
from test_m2 import dados, enviar, timer


def agenda():
    return {str(dia): {"ativo": True, "inicio": "07:00", "fim": "18:30"} for dia in range(7)}


async def test_gestor_configura_dia_fechado_e_mensagens(ambiente, monkeypatch):
    client, maker = ambiente
    instante = [datetime(2026, 11, 2, 15, 0)]  # Segunda, meio-dia em São Paulo.
    monkeypatch.setattr("app.services.atendimento.now", lambda: instante[0])
    await entrar(client, "a@teste.local")
    resposta = await client.post("/api/gestor/configuracao-bot", data={})
    assert resposta.status_code == 403
    await entrar(client, "gestor@teste.local")
    formulario = {
        "horarios": json.dumps(agenda()),
        "dias_fechados": json.dumps(["2026-11-02"]),
        "mensagem_fora_expediente": "Fechado hoje. Voltamos amanhã.",
        "mensagem_reabertura": "Abrimos novamente.",
        "mensagem_standby": "Aguarde nossa equipe.",
    }
    assert (await client.post("/api/gestor/configuracao-bot", data=formulario)).status_code == 200
    config = (await client.get("/api/gestor/config")).json()["configuracao_bot"]
    assert config["dias_fechados"] == ["2026-11-02"]
    assert (await client.get("/api/operacao-status")).json() == {"em_expediente": False}
    await enviar(maker, "55118889001", "oi", "fechado-1")
    await enviar(maker, "55118889001", "oi de novo", "fechado-2")
    conversa, mensagens, _ = await dados(maker, "55118889001")
    assert conversa.etapa == "fora_expediente"
    assert [item.texto for item in mensagens if item.origem == "bot"] == ["Fechado hoje. Voltamos amanhã."]
    instante[0] = datetime(2026, 11, 3, 15, 0)
    await timer(maker)
    conversa, mensagens, _ = await dados(maker, "55118889001")
    assert conversa.etapa == "menu_setor"
    assert "Abrimos novamente." in mensagens[-1].texto


async def test_valida_agenda_antes_de_salvar(ambiente):
    client, _ = ambiente
    await entrar(client, "gestor@teste.local")
    horarios = agenda()
    horarios["0"]["fim"] = "06:00"
    resposta = await client.post("/api/gestor/configuracao-bot", data={
        "horarios": json.dumps(horarios), "dias_fechados": "[]",
        "mensagem_fora_expediente": "Fechado", "mensagem_reabertura": "Aberto",
        "mensagem_standby": "Aguarde",
    })
    assert resposta.status_code == 422
