from test_m1 import entrar


async def test_painel_react_e_api_isolada_por_papel(ambiente):
    client, _ = ambiente
    entrada = await client.get("/login", follow_redirects=False)
    assert entrada.status_code == 303
    assert entrada.headers["location"] == "/painel"
    assert (await client.get("/api/me")).status_code == 401

    await entrar(client, "a@teste.local")
    perfil = (await client.get("/api/me")).json()
    assert perfil == {
        "id": 2,
        "nome": "Vendedor A",
        "email": "a@teste.local",
        "role": "colaborador",
        "foto_url": None,
        "presenca_intervalo_segundos": 30,
        "whatsapp_provider": "simulador",
        "meta_template_disponivel": False,
    }
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


async def test_gestor_configura_icones_dos_setores(ambiente):
    client, _ = ambiente
    await entrar(client, "gestor@teste.local")
    assert (await client.post("/api/gestor/setores/1", data={
        "nome": "Vendas/Compra", "icone": "invalido",
    })).status_code == 422
    assert (await client.post("/api/gestor/setores/1", data={
        "nome": "Vendas/Compra", "icone": "vendas",
    })).status_code == 200
    assert (await client.post("/api/gestor/setores-internos", data={
        "nome": "Pós-venda", "icone": "atendimento",
    })).status_code == 200
    config = (await client.get("/api/gestor/config")).json()
    assert config["setores"][0]["icone"] == "vendas"
    assert next(item for item in config["setores_internos"] if item["nome"] == "Pós-venda")["icone"] == "atendimento"
    assert next(item for item in (await client.get("/api/interno/setores")).json() if item["nome"] == "Pós-venda")["icone"] == "atendimento"
