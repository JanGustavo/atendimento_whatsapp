from sqlalchemy import select
from test_m1 import entrar

from app.models import Conversa
from app.providers import MetaProvider, simulador_provider
from app.services.atendimento import receber_mensagem


def webhook(nome, identidade, numero="55118880000"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "123"},
                            "contacts": [{"wa_id": numero, "profile": {"name": nome}}],
                            "messages": [
                                {
                                    "id": identidade,
                                    "from": numero,
                                    "type": "text",
                                    "text": {"body": "oi"},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }


async def test_nome_meta_vai_para_lista_e_detalhe_sem_perder_numero(ambiente):
    client, maker = ambiente
    provider = MetaProvider("v25.0", "123", "token-teste")
    enviados = 0

    async def enviar(_numero, _texto):
        nonlocal enviados
        enviados += 1
        return f"wamid.bot.{enviados}"

    provider.enviar_texto = enviar
    entrada = provider.parse_webhook(webhook("  Jander   Silva  ", "wamid.1"))
    assert entrada.nome_contato == "Jander Silva"
    async with maker() as db:
        await receber_mensagem(db, provider, entrada)
    await entrar(client, "gestor@teste.local")
    lista = (await client.get("/api/atendimentos?q=Jander")).json()
    assert len(lista) == 1
    assert lista[0]["numero"] == "55118880000"
    assert lista[0]["nome_contato"] == "Jander Silva"
    detalhe = (await client.get(f"/api/atendimentos/{lista[0]['id']}")).json()
    assert detalhe["conversa"]["nome_contato"] == "Jander Silva"
    async with maker() as db:
        await receber_mensagem(
            db, provider, provider.parse_webhook(webhook("Nome novo", "wamid.1"))
        )
        conversa = (
            await db.execute(select(Conversa).where(Conversa.numero == "55118880000"))
        ).scalar_one()
        assert conversa.nome_contato == "Jander Silva"  # duplicata não altera o contato
    async with maker() as db:
        await receber_mensagem(
            db, provider, provider.parse_webhook(webhook("Jander Atualizado", "wamid.2"))
        )
        conversa = (
            await db.execute(select(Conversa).where(Conversa.numero == "55118880000"))
        ).scalar_one()
        assert conversa.nome_contato == "Jander Atualizado"


def test_meta_associa_nome_ao_numero_correto_e_simulador_aceita_nome():
    provider = MetaProvider("v25.0", "123", "token-teste")
    payload = webhook("Outra pessoa", "wamid.3")
    payload["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"] = "55999999999"
    assert provider.parse_webhook(payload).nome_contato is None
    simulado = simulador_provider.parse_webhook(
        {"id": "sim-1", "numero": "55118880000", "texto": "oi", "nome_contato": "Cliente 1"}
    )
    assert simulado.nome_contato == "Cliente 1"


async def test_foto_contato_manual_respeita_isolamento(ambiente, monkeypatch, tmp_path):
    from types import SimpleNamespace

    client, maker = ambiente
    monkeypatch.setattr(
        "app.services.media.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path))
    )
    webp = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"
    await entrar(client, "a@teste.local")
    assert (
        await client.post(
            "/api/atendimentos/11/foto", content=webp, headers={"Content-Type": "image/webp"}
        )
    ).status_code == 404
    assert (await client.get("/api/atendimentos/11/foto")).status_code == 404
    resposta = await client.post(
        "/api/atendimentos/10/foto", content=webp, headers={"Content-Type": "image/webp"}
    )
    assert resposta.status_code == 200
    url = resposta.json()["foto_url"]
    assert (await client.get(url)).content == webp
    lista = (await client.get("/api/atendimentos")).json()
    assert lista[0]["foto_url"] == url
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        assert conversa.foto_chave and (tmp_path / conversa.foto_chave).exists()
    await entrar(client, "b@teste.local")
    assert (await client.get(url)).status_code == 404
