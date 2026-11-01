import json
import subprocess
from datetime import timedelta

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.utils import now
from app.models import Conversa, Mensagem
from app.providers.meta import MetaProvider


async def entrar(client, email):
    resposta = await client.post("/api/auth/login", data={"email": email, "senha": "senha12345"})
    assert resposta.status_code == 200


async def test_arquivar_isolamento_e_desarquivar(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/atendimentos/11/arquivar")).status_code == 404
    assert (await client.post("/api/atendimentos/10/arquivar")).status_code == 200
    lista = (await client.get("/api/atendimentos")).json()
    assert lista[0]["arquivada"] is True
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        assert conversa.status == "aberta" and conversa.arquivada_por_id == 2
    assert (await client.post("/api/atendimentos/10/desarquivar")).status_code == 200
    assert (await client.get("/api/atendimentos")).json()[0]["arquivada"] is False


async def test_novo_contato_exige_consentimento_e_nao_assume_conversa_alheia(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    dados = {"nome": "Cliente Novo", "numero": "5583999990001", "optin": "nao"}
    assert (await client.post("/api/atendimentos/novo-contato", data=dados)).status_code == 422
    dados["optin"] = "sim"
    resposta = await client.post("/api/atendimentos/novo-contato", data=dados)
    assert resposta.status_code == 200
    assert (await client.post("/api/atendimentos/novo-contato", data=dados)).status_code == 409
    async with maker() as db:
        conversa = await db.get(Conversa, resposta.json()["id"])
        assert conversa.atribuido_id == 2 and conversa.contato_optin_em is not None
        mensagem = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id))).scalar_one()
        assert mensagem.envio_status == "enviada" and mensagem.texto.startswith("Template:")


async def test_audio_envio_e_leitura_isolados(ambiente, tmp_path):
    client, maker = ambiente
    config = get_settings()
    antigo = config.media_dir
    config.media_dir = str(tmp_path)
    try:
        await entrar(client, "a@teste.local")
        dados = b"ID3" + b"\x00" * 100
        resposta = await client.post("/api/atendimentos/10/mensagens", content=dados, headers={"Content-Type": "audio/mpeg"})
        assert resposta.status_code == 200
        mensagem_id = resposta.json()["id"]
        audio = await client.get(f"/api/atendimentos/10/mensagens/{mensagem_id}/audio")
        assert audio.status_code == 200 and audio.content == dados
        parcial = await client.get(f"/api/atendimentos/10/mensagens/{mensagem_id}/audio", headers={"Range": "bytes=0-9"})
        assert parcial.status_code == 206 and parcial.content == dados[:10]
        assert parcial.headers["content-range"] == f"bytes 0-9/{len(dados)}"
        await entrar(client, "b@teste.local")
        assert (await client.get(f"/api/atendimentos/10/mensagens/{mensagem_id}/audio")).status_code == 404
        async with maker() as db:
            mensagem = await db.get(Mensagem, mensagem_id)
            assert mensagem.audio_chave.endswith(".mp3") and mensagem.envio_status == "enviada"
    finally:
        config.media_dir = antigo


async def test_meta_marca_ogg_opus_como_mensagem_de_voz(monkeypatch, tmp_path):
    config = get_settings()
    anterior = config.media_dir
    config.media_dir = str(tmp_path)
    try:
        (tmp_path / "gravacao.ogg").write_bytes(b"OggS" + b"\0" * 24 + b"OpusHead")
        (tmp_path / "anexo.mp3").write_bytes(b"ID3" + b"\0" * 24)
        enviados = []

        def responder(request):
            if request.url.path.endswith("/media"):
                if len(enviados) == 0:
                    assert b"audio/ogg; codecs=opus" in request.content
                return httpx.Response(200, json={"id": "media-id"})
            enviados.append(request.content)
            return httpx.Response(200, json={"messages": [{"id": "wamid.audio"}]})

        original = httpx.AsyncClient
        transporte = httpx.MockTransport(responder)
        monkeypatch.setattr("app.providers.meta.httpx.AsyncClient", lambda **kwargs: original(transport=transporte, **kwargs))
        provider = MetaProvider("v25.0", "123", "token-teste")
        assert await provider.enviar_audio("5583999990001", "gravacao.ogg") == "wamid.audio"
        assert await provider.enviar_audio("5583999990001", "anexo.mp3") == "wamid.audio"
        assert json.loads(enviados[0])["audio"] == {"id": "media-id", "voice": True}
        assert json.loads(enviados[1])["audio"] == {"id": "media-id"}
    finally:
        config.media_dir = anterior


async def test_contato_meta_sem_template_fica_salvo_sem_envio_livre(ambiente):
    client, maker = ambiente
    config = get_settings()
    antigo_provider, antigo_template = config.whatsapp_provider, config.meta_template_nome
    config.whatsapp_provider = "meta"
    config.meta_template_nome = ""
    try:
        await entrar(client, "a@teste.local")
        resposta = await client.post("/api/atendimentos/novo-contato", data={
            "nome": "Contato", "numero": "5583999990002", "optin": "sim"
        })
        assert resposta.status_code == 200 and resposta.json()["template_enviado"] is False
        conversa_id = resposta.json()["id"]
        assert (await client.post(f"/api/atendimentos/{conversa_id}/mensagens", data={"texto": "Oi"})).status_code == 409
        assert (await client.post(f"/api/atendimentos/{conversa_id}/template")).status_code == 409
        async with maker() as db:
            mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa_id))).scalars().all()
            assert mensagens == []
    finally:
        config.whatsapp_provider, config.meta_template_nome = antigo_provider, antigo_template



async def test_gravacao_webm_e_convertida_para_ogg(ambiente, tmp_path):
    client, maker = ambiente
    config = get_settings()
    antigo = config.media_dir
    config.media_dir = str(tmp_path)
    try:
        gravacao = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.25",
             "-c:a", "libopus", "-f", "webm", "pipe:1"],
            capture_output=True, check=True, timeout=10,
        ).stdout
        await entrar(client, "a@teste.local")
        resposta = await client.post("/api/atendimentos/10/mensagens", content=gravacao,
                                     headers={"Content-Type": "audio/webm"})
        assert resposta.status_code == 200
        async with maker() as db:
            mensagem = await db.get(Mensagem, resposta.json()["id"])
            assert mensagem.audio_chave.endswith(".ogg")
            assert (tmp_path / mensagem.audio_chave).read_bytes().startswith(b"OggS")
    finally:
        config.media_dir = antigo


async def test_painel_indica_janela_meta_encerrada_e_reaberta(ambiente):
    client, maker = ambiente
    config = get_settings()
    antigo = config.whatsapp_provider
    config.whatsapp_provider = "meta"
    try:
        await entrar(client, "a@teste.local")
        detalhe = (await client.get("/api/atendimentos/10")).json()
        assert detalhe["janela_texto_aberta"] is False
        async with maker() as db:
            db.add(Mensagem(conversa_id=10, origem="cliente", texto="Oi", criada_em=now() - timedelta(hours=25)))
            await db.commit()
        detalhe = (await client.get("/api/atendimentos/10")).json()
        assert detalhe["janela_texto_aberta"] is False
        async with maker() as db:
            db.add(Mensagem(conversa_id=10, origem="cliente", texto="Voltei", criada_em=now()))
            await db.commit()
        detalhe = (await client.get("/api/atendimentos/10")).json()
        assert detalhe["janela_texto_aberta"] is True
    finally:
        config.whatsapp_provider = antigo


async def test_status_gestor_alerta_webhook_sem_chave(ambiente):
    client, _ = ambiente
    config = get_settings()
    antigo_provider, antigo_secret = config.whatsapp_provider, config.meta_app_secret
    config.whatsapp_provider = "meta"
    config.meta_app_secret = ""
    try:
        await entrar(client, "gestor@teste.local")
        resposta = await client.get("/api/gestor/whatsapp-status")
        assert resposta.status_code == 200
        assert resposta.json() == {"status": "webhook sem chave"}
    finally:
        config.whatsapp_provider, config.meta_app_secret = antigo_provider, antigo_secret
