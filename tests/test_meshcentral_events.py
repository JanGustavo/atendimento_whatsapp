"""MeshCentral relay events: source validation, correlation, replay and API isolation."""

from datetime import timedelta

from sqlalchemy import select

from app.core.utils import now
from app.models import AcessoRemoto, Chamado, Computador, SessaoMeshCentral, Usuario
from app.services.meshcentral_events import (
    consumir_mensagem,
    interpretar_relay,
    registrar_evento,
    websocket_url,
)
from test_m1 import entrar

NO = "node//pc-estoque"
OPERADOR = "user//responsavel"


def evento(msgid=15, sessao="relay-0001", node=NO, userid=OPERADOR, momento=None):
    return {
        "etype": "relay",
        "action": "relaylog",
        "protocol": 2,
        "msgid": msgid,
        "nodeid": node,
        "userid": userid,
        "username": "Responsável",
        "msgArgs": [sessao, "192.0.2.1", "192.0.2.2"],
        "time": (momento or now()).isoformat() + "Z",
    }


async def preparar(maker):
    async with maker() as db:
        operador = await db.get(Usuario, 4)
        operador.mesh_user_id = OPERADOR
        computador = Computador(nome="PC Estoque Real", dono_id=2, grupo="empresa", mesh_node_id=NO)
        db.add(computador)
        await db.flush()
        chamado = Chamado(computador_id=computador.id, descricao="Problema de impressora")
        db.add(chamado)
        await db.flush()
        acesso = AcessoRemoto(
            chamado_id=chamado.id,
            computador_id=computador.id,
            solicitante_id=4,
            resultado="autorizado",
            inicio_em=now() - timedelta(minutes=3),
            autorizado_em=now() - timedelta(minutes=2),
            respondido_por_id=2,
            respondido_em=now() - timedelta(minutes=2),
        )
        db.add(acesso)
        await db.commit()
        return computador.id, chamado.id, acesso.id


def test_filtra_estritamente_eventos_reais_e_url_segura():
    assert websocket_url("https://mesh.example.test") == "wss://mesh.example.test/control.ashx"
    for url in ("http://mesh.test", "https://user:password@mesh.test",
                "https://mesh.test/other", "https://mesh.test/?auth=bad"):
        try:
            websocket_url(url)
            assert False, url
        except ValueError:
            pass
    assert interpretar_relay(evento()) is not None
    assert interpretar_relay({**evento(), "protocol": 1}) is None
    assert interpretar_relay({**evento(), "msgid": 14}) is None
    assert interpretar_relay({**evento(), "time": "invalid"}) is None
    assert interpretar_relay({**evento(), "nodeid": "mau"}) is None
    assert interpretar_relay({**evento(), "etype": "node"}) is None


async def test_inicio_fim_repetidos_sao_idempotentes_e_ligados_ao_chamado(ambiente):
    _client, maker = ambiente
    pc_id, _chamado_id, acesso_id = await preparar(maker)
    inicio = evento(momento=now())
    fim = evento(msgid=11, momento=now() + timedelta(seconds=20))
    async with maker() as db:
        assert await registrar_evento(db, inicio)
        await db.commit()
    async with maker() as db:
        assert await registrar_evento(db, inicio)
        await db.commit()
        sessoes = (await db.execute(select(SessaoMeshCentral))).scalars().all()
        assert len(sessoes) == 1
        sessao = sessoes[0]
        assert sessao.computador_id == pc_id
        assert sessao.acesso_id == acesso_id
        assert sessao.estado == "ativa"
        assert sessao.fim_em is None
    async with maker() as db:
        assert await registrar_evento(db, fim)
        assert await registrar_evento(db, fim)
        await db.commit()
        sessao = (await db.execute(select(SessaoMeshCentral))).scalar_one()
        assert sessao.estado == "encerrada"
        assert sessao.fim_em is not None
        assert sessao.inicio_em is not None


async def test_replay_fora_de_ordem_nao_reativa_sessao(ambiente):
    _client, maker = ambiente
    await preparar(maker)
    e = evento(msgid=11, sessao="relay-out-of-order", momento=now() + timedelta(seconds=25))
    i = evento(msgid=15, sessao="relay-out-of-order", momento=now())
    async with maker() as db:
        await registrar_evento(db, e)
        await registrar_evento(db, i)
        await db.commit()
        registro = (await db.execute(select(SessaoMeshCentral).where(
            SessaoMeshCentral.mesh_session_id == "relay-out-of-order"
        ))).scalar_one()
        assert registro.estado == "encerrada"
        assert registro.inicio_em is not None
        assert registro.fim_em is not None


async def test_evento_sem_consentimento_gera_auditoria_nao_vinculada(ambiente):
    _client, maker = ambiente
    await preparar(maker)
    async with maker() as db:
        await registrar_evento(db, evento(sessao="nao-vinculada", userid="user//terceiro"))
        await db.commit()
        s = (await db.execute(select(SessaoMeshCentral).where(
            SessaoMeshCentral.mesh_session_id == "nao-vinculada"
        ))).scalar_one()
        assert s.estado == "ativa" and s.acesso_id is None


async def test_consumidor_rejeita_action_injetada_e_processa_historico(ambiente):
    _client, maker = ambiente
    await preparar(maker)
    assert await consumir_mensagem({"action": "foo", "event": evento()}, maker) == 0
    assert await consumir_mensagem({"action": "events", "responseid": "wrong", "events": [evento()]}, maker) == 0
    assert await consumir_mensagem({"action": "event", "event": evento()}, maker) == 1
    assert await consumir_mensagem({
        "action": "events", "responseid": "fortgiro-replay",
        "events": [evento(msgid=11, momento=now() + timedelta(seconds=10)), evento()],
    }, maker) == 2
    async with maker() as db:
        registro = (await db.execute(select(SessaoMeshCentral))).scalar_one()
        assert registro.estado == "encerrada"


async def test_api_isola_sessoes_por_dono_e_protege_vinculos(ambiente):
    client, maker = ambiente
    pc_id, _chamado_id, acesso_id = await preparar(maker)
    async with maker() as db:
        await registrar_evento(db, evento())
        await db.commit()
    await entrar(client, "b@teste.local")
    resposta = await client.get("/api/meus-sessoes-remotas")
    assert resposta.status_code == 200
    assert resposta.json()["sessoes"] == []
    assert (await client.get("/api/chamados/sessoes-remotas")).status_code == 403
    assert (await client.post("/api/gestor/usuarios/4/meshcentral",
        data={"mesh_user_id": "user//novo"})).status_code == 403

    await entrar(client, "a@teste.local")
    dados = (await client.get("/api/meus-sessoes-remotas")).json()
    assert len(dados["sessoes"]) == 1
    assert dados["sessoes"][0]["acesso_id"] == acesso_id

    await entrar(client, "gestor@teste.local")
    assert len((await client.get("/api/chamados/sessoes-remotas")).json()["sessoes"]) == 1
    outro = await client.post("/api/gestor/usuarios/4/meshcentral",
        data={"mesh_user_id": "user//tecnico-novo"})
    assert outro.status_code == 200
    duplicado = await client.post("/api/gestor/usuarios/6/meshcentral",
        data={"mesh_user_id": "user//tecnico-novo"})
    assert duplicado.status_code == 409
    node = await client.post(f"/api/computadores/{pc_id}/mesh-node",
        data={"mesh_node_id": "node//novo"})
    assert node.status_code == 200
