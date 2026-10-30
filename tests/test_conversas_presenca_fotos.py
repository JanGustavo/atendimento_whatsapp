from datetime import datetime, timedelta
from types import SimpleNamespace

from test_m1 import entrar

from app.models import MensagemGrupo, MensagemInterna, Usuario

WEBP = b"RIFF" + (12).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00\x00\x00\x00"


async def test_conversas_recentes_identificam_remetente_e_leitura_por_chat(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add_all(
            [
                MensagemInterna(remetente_id=3, destinatario_id=2, texto="De B"),
                MensagemInterna(remetente_id=4, destinatario_id=2, texto="De estoque"),
                MensagemInterna(remetente_id=2, destinatario_id=3, texto="Resposta"),
            ]
        )
        await db.commit()
    await entrar(client, "a@teste.local")
    dados = (await client.get("/api/interno/conversas")).json()
    por_id = {item["alvo_id"]: item for item in dados["conversas"] if item["tipo"] == "direta"}
    assert por_id[3]["ultimo_remetente"] == "Você"
    assert por_id[3]["ultima_previa"] == "Resposta"
    assert por_id[3]["nao_lidas"] == 1
    assert por_id[4]["ultimo_remetente"] == "Responsável"
    assert por_id[4]["nao_lidas"] == 1
    assert dados["nao_lidas"] == 2
    assert (await client.post("/api/interno/conversas/direta/3/leitura")).status_code == 200
    dados = (await client.get("/api/interno/conversas")).json()
    por_id = {item["alvo_id"]: item for item in dados["conversas"] if item["tipo"] == "direta"}
    assert por_id[3]["nao_lidas"] == 0
    assert por_id[4]["nao_lidas"] == 1
    assert (await client.post("/api/interno/conversas/grupo/999/leitura")).status_code == 404


async def test_grupos_do_gestor_e_leitura_por_grupo(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add(MensagemGrupo(setor_id=1, remetente_id=3, texto="Equipe de vendas"))
        await db.commit()
    await entrar(client, "gestor@teste.local")
    setores = (await client.get("/api/interno/setores")).json()
    assert next(item for item in setores if item["id"] == 1)["grupo_ativo"] is True
    assert (await client.get("/api/interno/grupos/1/mensagens")).status_code == 200
    await entrar(client, "r@teste.local")
    assert (await client.get("/api/interno/grupos/1/mensagens")).status_code == 404
    await entrar(client, "a@teste.local")
    grupo = next(
        item
        for item in (await client.get("/api/interno/conversas")).json()["conversas"]
        if item["tipo"] == "grupo" and item["alvo_id"] == 1
    )
    assert grupo["nao_lidas"] == 1 and grupo["ultimo_remetente"] == "Vendedor B"
    assert (await client.post("/api/interno/conversas/grupo/1/leitura")).status_code == 200
    grupo = next(
        item
        for item in (await client.get("/api/interno/conversas")).json()["conversas"]
        if item["tipo"] == "grupo" and item["alvo_id"] == 1
    )
    assert grupo["nao_lidas"] == 0


async def test_presenca_expira_sem_heartbeat(ambiente, monkeypatch):
    client, _ = ambiente
    instante = datetime(2026, 10, 29, 12, 0)
    monkeypatch.setattr("app.api.frontend.now", lambda: instante)
    monkeypatch.setattr("app.services.presenca.now", lambda: instante)
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/presenca")).status_code == 200
    await entrar(client, "b@teste.local")
    setores = (await client.get("/api/interno/setores")).json()
    pessoa = next(p for s in setores for p in s["pessoas"] if p["id"] == 2)
    assert pessoa["online"] is True
    monkeypatch.setattr("app.services.presenca.now", lambda: instante + timedelta(seconds=91))
    setores = (await client.get("/api/interno/setores")).json()
    pessoa = next(p for s in setores for p in s["pessoas"] if p["id"] == 2)
    assert pessoa["online"] is False


async def test_foto_do_proprio_usuario_e_acesso_autenticado(ambiente, monkeypatch, tmp_path):
    client, maker = ambiente
    monkeypatch.setattr(
        "app.services.media.get_settings", lambda: SimpleNamespace(media_dir=str(tmp_path))
    )
    await entrar(client, "a@teste.local")
    assert (
        await client.post("/api/me/foto", content=b"abc", headers={"Content-Type": "image/png"})
    ).status_code == 415
    resposta = await client.post(
        "/api/me/foto", content=WEBP, headers={"Content-Type": "image/webp"}
    )
    assert resposta.status_code == 200
    url = resposta.json()["foto_url"]
    assert url == (await client.get("/api/me")).json()["foto_url"]
    assert (await client.get(url)).content == WEBP
    async with maker() as db:
        usuario = await db.get(Usuario, 2)
        assert usuario.foto_chave and usuario.foto_chave in url
    await entrar(client, "b@teste.local")
    assert (await client.get(url)).status_code == 200
    await client.post("/api/auth/logout")
    assert (await client.get(url)).status_code == 401
