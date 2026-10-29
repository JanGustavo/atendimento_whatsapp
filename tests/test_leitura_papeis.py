import hashlib
import hmac
import json
from types import SimpleNamespace

from sqlalchemy import select

from app.core.database import get_session_maker
from app.main import app
from app.models import LeituraConversa, Mensagem, Usuario
from app.providers.meta import MetaProvider
from app.services.atendimento import proximo_disponivel, vendedores_ativos
from test_m1 import entrar


async def test_leitura_do_atendente_persiste_e_respeita_isolamento(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add(Mensagem(conversa_id=10, origem="cliente", texto="Preciso de peça"))
        await db.commit()
    await entrar(client, "a@teste.local")
    lista = (await client.get("/api/atendimentos")).json()
    assert next(item for item in lista if item["id"] == 10)["nao_lidas"] == 1
    assert (await client.post("/api/atendimentos/11/leitura")).status_code == 404
    assert (await client.post("/api/atendimentos/10/leitura")).status_code == 200
    assert next(item for item in (await client.get("/api/atendimentos")).json() if item["id"] == 10)["nao_lidas"] == 0
    detalhe = (await client.get("/api/atendimentos/10")).json()
    assert detalhe["visualizada_pelo_atendente_em"] is not None
    async with maker() as db:
        assert (await db.execute(select(LeituraConversa).where(LeituraConversa.conversa_id == 10))).scalar_one().usuario_id == 2
        db.add(Mensagem(conversa_id=10, origem="cliente", texto="Mais uma peça"))
        await db.commit()
    assert next(item for item in (await client.get("/api/atendimentos")).json() if item["id"] == 10)["nao_lidas"] == 1
    await entrar(client, "gestor@teste.local")
    assert (await client.get("/api/atendimentos/10")).json()["visualizada_pelo_atendente_em"] is None


async def test_setor_vendas_define_elegibilidade_sem_papel_vendedor(ambiente):
    client, maker = ambiente
    async with maker() as db:
        colaborador = await db.get(Usuario, 5)
        colaborador.setor_interno_id = 2
        await db.commit()
    async with maker() as db:
        assert [item.id for item in await vendedores_ativos(db)] == [2, 3]
        assert (await proximo_disponivel(db)).id in {2, 3}
    await entrar(client, "gestor@teste.local")
    config = (await client.get("/api/gestor/config")).json()
    assert {item["role"] for item in config["usuarios"]} == {"gestor", "supervisor", "colaborador"}
    assert (await client.post("/api/gestor/conversas/10/transferir", data={"usuario_id": 5})).status_code == 422


async def test_meta_status_entregue_lida_e_regressao_ignorada(ambiente, monkeypatch):
    client, maker = ambiente
    async with maker() as db:
        db.add(Mensagem(conversa_id=10, origem="humano", texto="Resposta", provider_id="wamid.saida", envio_status="enviada"))
        await db.commit()
    app.dependency_overrides[get_session_maker] = lambda: maker
    config = SimpleNamespace(meta_verify_token="verificar", meta_app_secret="segredo",
                             meta_graph_version="v24.0", meta_phone_number_id="123", meta_access_token="token")
    monkeypatch.setattr("app.api.webhook.get_settings", lambda: config)
    async def postar(estado):
        payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
            "metadata": {"phone_number_id": "123"}, "statuses": [{"id": "wamid.saida", "status": estado, "timestamp": "1793220000"}]
        }}]}]}
        corpo = json.dumps(payload).encode()
        assinatura = "sha256=" + hmac.new(b"segredo", corpo, hashlib.sha256).hexdigest()
        assert (await client.post("/webhook/whatsapp", content=corpo, headers={"X-Hub-Signature-256": assinatura})).status_code == 200
    await postar("delivered")
    await postar("read")
    await postar("sent")
    async with maker() as db:
        item = (await db.execute(select(Mensagem).where(Mensagem.provider_id == "wamid.saida"))).scalar_one()
        assert item.envio_status == "lida" and item.lida_em is not None
