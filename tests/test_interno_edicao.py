from test_m1 import entrar


async def test_edicao_direta_so_autor_e_atualiza_previa(ambiente):
    client, _ = ambiente
    await entrar(client, "a@teste.local")
    criada = await client.post("/api/interno/mensagens/4", data={"texto": "Antes"})
    mid = criada.json()["id"]
    rota = f"/api/interno/mensagens/4/{mid}"

    await entrar(client, "r@teste.local")
    assert (await client.patch(f"/api/interno/mensagens/2/{mid}", data={"texto": "Inválido"})).status_code == 404
    await entrar(client, "b@teste.local")
    assert (await client.patch(rota, data={"texto": "Inválido"})).status_code == 404

    await entrar(client, "a@teste.local")
    assert (await client.patch(rota, data={"texto": "Depois"})).status_code == 200
    mensagem = (await client.get("/api/interno/mensagens/4")).json()[0]
    assert mensagem["texto"] == "Depois" and mensagem["editada_em"]
    previa = (await client.get("/api/interno/conversas")).json()["conversas"][0]
    assert previa["ultima_previa"] == "Depois"
    assert (await client.patch(rota, data={"texto": " "})).status_code == 422
    assert (await client.delete(rota)).status_code == 200
    assert (await client.patch(rota, data={"texto": "Voltar"})).status_code == 404


async def test_edicao_grupo_so_autor_e_setor(ambiente):
    client, _ = ambiente
    await entrar(client, "a@teste.local")
    criada = await client.post("/api/interno/grupos/1/mensagens", data={"texto": "Reunião"})
    mid = criada.json()["id"]
    rota = f"/api/interno/grupos/1/mensagens/{mid}"
    await entrar(client, "b@teste.local")
    assert (await client.patch(rota, data={"texto": "Alteração"})).status_code == 404
    await entrar(client, "r@teste.local")
    assert (await client.patch(rota, data={"texto": "Alteração"})).status_code == 404
    await entrar(client, "a@teste.local")
    assert (await client.patch(rota, data={"texto": "Reunião às 9h"})).status_code == 200
    mensagem = (await client.get("/api/interno/grupos/1/mensagens")).json()[0]
    assert mensagem["texto"] == "Reunião às 9h" and mensagem["editada_em"]
