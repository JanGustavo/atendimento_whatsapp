from test_m1 import entrar


async def test_gestor_troca_opcoes_do_menu_sem_mover_vendas(ambiente):
    client, _ = ambiente
    await entrar(client, "gestor@teste.local")
    config = (await client.get("/api/gestor/config")).json()
    setor_2 = next(item for item in config["setores"] if item["ordem"] == 2)
    setor_3 = next(item for item in config["setores"] if item["ordem"] == 3)
    resposta = await client.post(f"/api/gestor/setores/{setor_2['id']}", data={
        "nome": setor_2["nome"], "icone": setor_2["icone"], "responsavel_id": str(setor_2["responsavel_id"]), "ordem": "3",
    })
    assert resposta.status_code == 200, resposta.text
    atual = (await client.get("/api/gestor/config")).json()["setores"]
    assert next(item for item in atual if item["id"] == setor_2["id"])["ordem"] == 3
    assert next(item for item in atual if item["id"] == setor_3["id"])["ordem"] == 2
    assert (await client.post(f"/api/gestor/setores/{setor_2['id']}", data={
        "nome": setor_2["nome"], "icone": setor_2["icone"], "responsavel_id": str(setor_2["responsavel_id"]), "ordem": "1",
    })).status_code == 422


async def test_excluir_usuario_sem_historico_e_bloquear_vinculados(ambiente):
    client, _ = ambiente
    await entrar(client, "gestor@teste.local")
    criado = await client.post("/api/gestor/usuarios", data={
        "nome": "Temporário", "email": "temp@teste.local", "senha": "senhatemporaria", "role": "colaborador", "setor_interno_id": "1",
    })
    assert criado.status_code == 200
    usuarios = (await client.get("/api/gestor/config")).json()["usuarios"]
    novo_id = next(item["id"] for item in usuarios if item["email"] == "temp@teste.local")
    assert (await client.delete(f"/api/gestor/usuarios/{novo_id}")).status_code == 200
    assert (await client.delete("/api/gestor/usuarios/1")).status_code == 409
    assert (await client.delete("/api/gestor/usuarios/2")).status_code == 409
