from types import SimpleNamespace

from test_m1 import entrar


async def test_atalho_meshcentral_so_para_suporte(ambiente, monkeypatch):
    client, _ = ambiente
    monkeypatch.setattr("app.api.chamados.get_settings", lambda: SimpleNamespace(
        meshcentral_url="https://mesh.jangustavo.me", remoto_provider="simulado",
    ))
    await entrar(client, "a@teste.local")
    assert (await client.get("/api/chamados/sessoes-remotas")).status_code == 403
    await entrar(client, "r@teste.local")
    dados = (await client.get("/api/chamados/sessoes-remotas")).json()
    assert dados["meshcentral_url"] == "https://mesh.jangustavo.me"
    assert dados["remoto_provider"] == "simulado"


async def test_atalho_rejeita_url_meshcentral_insegura(ambiente, monkeypatch):
    client, _ = ambiente
    monkeypatch.setattr("app.api.chamados.get_settings", lambda: SimpleNamespace(
        meshcentral_url="http://mesh.jangustavo.me", remoto_provider="meshcentral",
    ))
    await entrar(client, "gestor@teste.local")
    assert (await client.get("/api/chamados/sessoes-remotas")).status_code == 503
