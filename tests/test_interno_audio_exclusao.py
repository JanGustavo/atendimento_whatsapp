from test_m1 import entrar

from app.core.config import get_settings


async def test_audio_direto_so_participantes_e_exclusao_so_autor(ambiente, tmp_path, monkeypatch):
    client, _ = ambiente
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()
    audio = b"OggS" + b"\0" * 20 + b"OpusHead" + b"\0" * 40
    try:
        await entrar(client, "a@teste.local")
        enviado = await client.post("/api/interno/mensagens/4/audio", content=audio, headers={"Content-Type": "audio/ogg"})
        assert enviado.status_code == 200
        mid = enviado.json()["id"]
        mensagem = (await client.get("/api/interno/mensagens/4")).json()[0]
        assert mensagem["audio_url"] and not mensagem["apagada"]
        assert (await client.get(mensagem["audio_url"])).content == audio

        await entrar(client, "b@teste.local")
        assert (await client.get(mensagem["audio_url"])).status_code == 404
        assert (await client.delete(f"/api/interno/mensagens/4/{mid}")).status_code == 404

        await entrar(client, "r@teste.local")
        assert (await client.delete(f"/api/interno/mensagens/2/{mid}")).status_code == 404
        await entrar(client, "a@teste.local")
        assert (await client.delete(f"/api/interno/mensagens/4/{mid}")).status_code == 200
        apagada = (await client.get("/api/interno/mensagens/4")).json()[0]
        assert apagada["apagada"] and apagada["audio_url"] is None and apagada["texto"] == ""
        assert (await client.get(mensagem["audio_url"])).status_code == 404
    finally:
        get_settings.cache_clear()


async def test_audio_grupo_e_exclusao_preserva_historico(ambiente, tmp_path, monkeypatch):
    client, _ = ambiente
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()
    audio = b"OggS" + b"\0" * 20 + b"OpusHead" + b"\0" * 40
    try:
        await entrar(client, "a@teste.local")
        enviado = await client.post("/api/interno/grupos/1/audios", content=audio, headers={"Content-Type": "audio/ogg"})
        assert enviado.status_code == 200
        mid = enviado.json()["id"]
        url = (await client.get("/api/interno/grupos/1/mensagens")).json()[0]["audio_url"]

        await entrar(client, "b@teste.local")
        assert (await client.get(url)).status_code == 200
        assert (await client.delete(f"/api/interno/grupos/1/mensagens/{mid}")).status_code == 404
        await entrar(client, "r@teste.local")
        assert (await client.get(url)).status_code == 404
        assert (await client.delete(f"/api/interno/grupos/1/mensagens/{mid}")).status_code == 404

        await entrar(client, "a@teste.local")
        assert (await client.delete(f"/api/interno/grupos/1/mensagens/{mid}")).status_code == 200
        apagada = (await client.get("/api/interno/grupos/1/mensagens")).json()[0]
        assert apagada["id"] == mid and apagada["apagada"] and apagada["audio_url"] is None
    finally:
        get_settings.cache_clear()
