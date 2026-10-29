from types import SimpleNamespace


async def test_host_https_cookie_seguro_e_post_com_origem(ambiente, monkeypatch):
    client, _ = ambiente
    config = SimpleNamespace(panel_https_host="painel.jangustavo.me")
    monkeypatch.setattr("app.main.get_settings", lambda: config)
    monkeypatch.setattr("app.api.auth.get_settings", lambda: config)
    base = {"Host": "painel.jangustavo.me"}
    bloqueado = await client.post(
        "/api/auth/login",
        headers={**base, "Origin": "https://site-externo.test"},
        data={"email": "gestor@teste.local", "senha": "senha12345"},
    )
    assert bloqueado.status_code == 403
    permitido = await client.post(
        "/api/auth/login",
        headers={**base, "Origin": "https://painel.jangustavo.me"},
        data={"email": "gestor@teste.local", "senha": "senha12345"},
    )
    assert permitido.status_code == 200
    assert "secure" in permitido.headers["set-cookie"].lower()


async def test_login_local_continua_sem_cookie_secure(ambiente):
    client, _ = ambiente
    resposta = await client.post(
        "/api/auth/login", data={"email": "gestor@teste.local", "senha": "senha12345"}
    )
    assert resposta.status_code == 200
    assert "secure" not in resposta.headers["set-cookie"].lower()
