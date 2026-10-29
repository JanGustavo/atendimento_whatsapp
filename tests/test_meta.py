"""Integração Meta sem rede externa: HTTP simulado e webhook assinado."""
import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
from sqlalchemy import select

from app.core.database import get_session_maker
from app.main import app
from app.models import Conversa, Mensagem
from app.providers import MetaProvider, MensagemEntrada, simulador_provider
from app.services.atendimento import receber_mensagem


def payload(*mensagens, phone_number_id="123"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "waba-1", "changes": [{
        "field": "messages", "value": {"metadata": {"phone_number_id": phone_number_id},
                                      "messages": list(mensagens)}
    }]}]}


def texto(identidade, numero="55118880000", corpo="oi"):
    return {"id": identidade, "from": numero, "type": "text", "text": {"body": corpo}}


async def test_meta_recoloca_nono_digito_no_destino_brasileiro(monkeypatch):
    enviados = []

    def responder(request):
        enviados.append(json.loads(request.content)["to"])
        return httpx.Response(200, json={"messages": [{"id": "wamid.saida"}]})

    cliente_original = httpx.AsyncClient
    transporte = httpx.MockTransport(responder)
    monkeypatch.setattr("app.providers.meta.httpx.AsyncClient", lambda **kwargs: cliente_original(transport=transporte, **kwargs))
    provider = MetaProvider("v25.0", "123", "token-teste")
    assert await provider.enviar_texto("558398442632", "Olá") == "wamid.saida"
    await provider.enviar_texto("551132341234", "Olá")
    assert enviados == ["5583998442632", "551132341234"]


async def test_meta_envia_texto_consulta_status_e_mantem_regras(ambiente, monkeypatch):
    requisicoes = []

    def responder(request):
        requisicoes.append(request)
        if request.method == "POST":
            assert request.headers["authorization"] == "Bearer token-teste"
            if len(requisicoes) == 1:
                assert json.loads(request.content) == {
                    "messaging_product": "whatsapp", "recipient_type": "individual",
                    "to": "55118880000", "type": "text", "text": {"body": "Olá"},
                }
            return httpx.Response(200, json={"messages": [{"id": "wamid.saida"}]})
        return httpx.Response(200, json={"id": "123"})

    cliente_original = httpx.AsyncClient
    transporte = httpx.MockTransport(responder)
    monkeypatch.setattr("app.providers.meta.httpx.AsyncClient", lambda **kwargs: cliente_original(transport=transporte, **kwargs))
    provider = MetaProvider("v24.0", "123", "token-teste")
    assert await provider.enviar_texto("+55 (11) 888-0000", "Olá") == "wamid.saida"
    assert await provider.status() == "conectado"
    assert [request.url.path for request in requisicoes] == ["/v24.0/123/messages", "/v24.0/123"]

    _, maker = ambiente
    async with maker() as db:
        await receber_mensagem(db, simulador_provider, MensagemEntrada("sim-1", "55118889991", "invalido"))
    async with maker() as db:
        await receber_mensagem(db, provider, MensagemEntrada("meta-1", "55118889992", "invalido"))
    async with maker() as db:
        conversas = (await db.execute(select(Conversa).where(Conversa.numero.in_([
            "55118889991", "55118889992",
        ])).order_by(Conversa.numero))).scalars().all()
        assert [item.etapa for item in conversas] == ["menu_setor", "menu_setor"]


async def test_webhook_meta_verifica_assinatura_idempotencia_midia_e_lote(ambiente, monkeypatch):
    client, maker = ambiente
    app.dependency_overrides[get_session_maker] = lambda: maker
    config = SimpleNamespace(meta_verify_token="verificar", meta_app_secret="segredo",
                             meta_graph_version="v24.0", meta_phone_number_id="123",
                             meta_access_token="token-teste")
    monkeypatch.setattr("app.api.webhook.get_settings", lambda: config)
    provider = MetaProvider("v24.0", "123", "token-teste")
    envios = []

    async def enviar(numero, mensagem):
        envios.append((numero, mensagem))

    monkeypatch.setattr(provider, "enviar_texto", enviar)
    monkeypatch.setattr("app.api.webhook.MetaProvider", lambda *_: provider)
    assert (await client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "42",
    })).status_code == 403
    verificado = await client.get("/webhook/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "verificar", "hub.challenge": "42",
    })
    assert verificado.status_code == 200 and verificado.text == "42"

    async def postar(conteudo, assinatura_valida=True):
        corpo = json.dumps(conteudo).encode()
        assinatura = "sha256=" + hmac.new(b"segredo", corpo, hashlib.sha256).hexdigest()
        return await client.post("/webhook/whatsapp", content=corpo, headers={
            "Content-Type": "application/json", "X-Hub-Signature-256": assinatura if assinatura_valida else "sha256=falsa",
        })

    entrada = payload(texto("wamid.1"), texto("wamid.2", corpo="99"),
                      texto("wamid.grupo", numero="123@g.us"))
    assert (await postar(entrada, False)).status_code == 401
    assert (await postar(entrada)).status_code == 200
    assert (await postar(entrada)).status_code == 200
    assert (await postar(payload({"id": "wamid.midia", "from": "55118880000", "type": "image", "image": {"id": "foto"}}))).status_code == 200
    assert (await postar({"object": "whatsapp_business_account", "entry": [{"changes": [{
        "field": "messages", "value": {"statuses": [{"id": "wamid.saida", "status": "delivered"}]}
    }]}]})).status_code == 200
    assert (await postar(payload(texto("wamid.outro"), phone_number_id="999"))).status_code == 200
    async with maker() as db:
        conversa = (await db.execute(select(Conversa).where(Conversa.numero == "55118880000"))).scalar_one()
        mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars().all()
    assert [item.provider_id for item in mensagens if item.origem == "cliente"] == ["wamid.1", "wamid.2", "wamid.midia"]
    assert [item.texto for item in mensagens if item.origem == "bot"] == [
        "Escolha o setor:\n1 - Vendas/Compra\n2 - Devolução\n3 - Garantia\n4 - Outro",
        "Escolha o setor:\n1 - Vendas/Compra\n2 - Devolução\n3 - Garantia\n4 - Outro",
        "No momento só atendemos por texto",
    ]
    assert len(envios) == 3
