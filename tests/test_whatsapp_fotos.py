from types import SimpleNamespace

from test_m1 import entrar

WEBP = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"


async def test_enviar_foto_com_mensagem_whatsapp(ambiente, monkeypatch, tmp_path):
    client, maker = ambiente
    monkeypatch.setattr(
        "app.services.media.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path))
    )
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            whatsapp_provider="simulador",
            media_dir=str(tmp_path),
            presenca_intervalo_segundos=30,
        ),
    )
    await entrar(client, "a@teste.local")

    # Conversa 10 pertence ao colaborador A (Vendedor A)
    resposta = await client.post(
        "/api/atendimentos/10/mensagens?texto=Olha+a+foto",
        content=WEBP,
        headers={"Content-Type": "image/webp"},
    )
    assert resposta.status_code == 200
    msg_id = resposta.json()["id"]

    detalhe = (await client.get("/api/atendimentos/10")).json()
    ultima = detalhe["mensagens"][-1]
    assert ultima["id"] == msg_id
    assert ultima["texto"] == "Olha a foto"
    assert ultima["imagem_url"] == f"/api/atendimentos/10/mensagens/{msg_id}/imagem"

    # Ler a imagem com o próprio atendente
    img_resp = await client.get(ultima["imagem_url"])
    assert img_resp.status_code == 200
    assert img_resp.content == WEBP
    assert img_resp.headers["content-type"] == "image/webp"

    # Outro atendente sem acesso à conversa não pode ler a imagem
    await entrar(client, "b@teste.local")
    assert (await client.get(ultima["imagem_url"])).status_code == 404

    # Gestor pode ver e acessar a imagem
    await entrar(client, "gestor@teste.local")
    gestor_img = await client.get(ultima["imagem_url"])
    assert gestor_img.status_code == 200
    assert gestor_img.content == WEBP


async def test_enviar_foto_sem_texto_whatsapp(ambiente, monkeypatch, tmp_path):
    client, maker = ambiente
    monkeypatch.setattr(
        "app.services.media.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path))
    )
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            whatsapp_provider="simulador",
            media_dir=str(tmp_path),
            presenca_intervalo_segundos=30,
        ),
    )
    await entrar(client, "a@teste.local")

    # Envia apenas imagem sem query param de texto
    resposta = await client.post(
        "/api/atendimentos/10/mensagens",
        content=WEBP,
        headers={"Content-Type": "image/webp"},
    )
    assert resposta.status_code == 200
    msg_id = resposta.json()["id"]

    detalhe = (await client.get("/api/atendimentos/10")).json()
    ultima = detalhe["mensagens"][-1]
    assert ultima["id"] == msg_id
    assert ultima["texto"] == ""
    assert ultima["imagem_url"] == f"/api/atendimentos/10/mensagens/{msg_id}/imagem"
