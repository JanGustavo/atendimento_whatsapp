from types import SimpleNamespace

from app.models import MensagemGrupo
from test_m1 import entrar


async def test_grupo_surge_com_dois_membros_e_isola_mensagens(ambiente, monkeypatch, tmp_path):
    client, maker = ambiente
    monkeypatch.setattr("app.api.interno.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path)))
    await entrar(client, "gestor@teste.local")
    criado = await client.post("/api/gestor/setores-internos", data={"nome": "Supervisão"})
    assert criado.status_code == 200
    setor_id = criado.json()["id"]
    await entrar(client, "a@teste.local")
    assert (await client.post(f"/api/interno/grupos/{setor_id}/mensagens", data={"texto": "Olá"})).status_code == 404
    await entrar(client, "gestor@teste.local")
    for usuario_id in (3, 5):
        resposta = await client.post(f"/api/gestor/usuarios/{usuario_id}", data={
            "nome": "Pessoa", "email": f"p{usuario_id}@teste.local", "role": "colaborador",
            "ativo": "on", "online": "on", "setor_interno_id": str(setor_id),
        })
        assert resposta.status_code == 200
    await entrar(client, "p3@teste.local")
    grupo = next(item for item in (await client.get("/api/interno/setores")).json() if item["id"] == setor_id)
    assert grupo["grupo_ativo"] is True
    assert (await client.post(f"/api/interno/grupos/{setor_id}/mensagens", data={"texto": "Reunião"})).status_code == 200
    imagem = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"
    assert (await client.post(f"/api/interno/grupos/{setor_id}/imagens", content=imagem,
                              headers={"Content-Type": "image/webp"})).status_code == 200
    await entrar(client, "p5@teste.local")
    mensagens = (await client.get(f"/api/interno/grupos/{setor_id}/mensagens")).json()
    assert mensagens[0]["texto"] == "Reunião"
    assert (await client.get(mensagens[1]["imagem_url"])).status_code == 200
    await entrar(client, "a@teste.local")
    assert (await client.get(f"/api/interno/grupos/{setor_id}/mensagens")).status_code == 404
    assert (await client.get(mensagens[1]["imagem_url"])).status_code == 404
    async with maker() as db:
        assert await db.get(MensagemGrupo, 1) is not None


async def test_imagem_webp_fica_privada_e_no_banco_so_chave(ambiente, monkeypatch, tmp_path):
    client, maker = ambiente
    monkeypatch.setattr("app.api.interno.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path)))
    imagem = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"
    await entrar(client, "a@teste.local")
    ruim = await client.post("/api/interno/mensagens/4/imagem", content=b"abc", headers={"Content-Type": "image/png"})
    assert ruim.status_code == 415
    enviada = await client.post("/api/interno/mensagens/4/imagem", content=imagem, headers={"Content-Type": "image/webp"})
    assert enviada.status_code == 200
    mensagem = (await client.get("/api/interno/mensagens/4")).json()[0]
    assert mensagem["texto"] == "" and mensagem["imagem_url"].startswith("/api/interno/imagens/")
    assert (await client.get(mensagem["imagem_url"])).content == imagem
    await entrar(client, "b@teste.local")
    assert (await client.get(mensagem["imagem_url"])).status_code == 404
    await entrar(client, "r@teste.local")
    assert (await client.get(mensagem["imagem_url"])).status_code == 200
