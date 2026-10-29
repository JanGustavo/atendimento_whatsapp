from test_m1 import entrar


async def test_painel_react_e_api_isolada_por_papel(ambiente):
    client, _ = ambiente
    entrada = await client.get("/login", follow_redirects=False)
    assert entrada.status_code == 303
    assert entrada.headers["location"] == "/painel"
    assert (await client.get("/api/me")).status_code == 401

    await entrar(client, "a@teste.local")
    perfil = (await client.get("/api/me")).json()
    assert perfil == {"id": 2, "nome": "Vendedor A", "email": "a@teste.local", "role": "colaborador"}
    lista = (await client.get("/api/atendimentos")).json()
    assert [item["id"] for item in lista] == [10]
    assert (await client.get("/api/atendimentos/11")).status_code == 404
    assert (await client.get("/api/gestor/config")).status_code == 403
    assert (await client.get("/api/simulador")).status_code == 403
    detalhe = (await client.get("/api/atendimentos/10")).json()
    assert detalhe["conversa"]["atribuido_id"] == 2

    await entrar(client, "gestor@teste.local")
    assert len((await client.get("/api/atendimentos")).json()) == 2
    config = (await client.get("/api/gestor/config")).json()
    assert len(config["setores"]) == 4
    assert "senha_hash" not in config["usuarios"][0]
    assert (await client.get("/api/simulador?cliente=cliente1")).status_code == 200
