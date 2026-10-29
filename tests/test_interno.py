from sqlalchemy import select

from app.models import MensagemInterna, Usuario
from test_m1 import entrar


async def test_chat_interno_lista_so_online_e_mensagem_fica_entre_usuarios(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    grupos = (await client.get("/api/interno/setores")).json()
    assert [item["nome"] for item in grupos] == ["Administração", "Estoque", "Garantia", "Vendas"]
    assert [p["id"] for p in next(item for item in grupos if item["nome"] == "Estoque")["pessoas"]] == [4]
    assert (await client.post("/api/interno/mensagens/4", data={"texto": "Preciso de uma peça"})).status_code == 200
    assert (await client.get("/api/interno/mensagens/4")).json()[0]["texto"] == "Preciso de uma peça"
    await entrar(client, "b@teste.local")
    assert (await client.get("/api/interno/mensagens/4")).json() == []
    await entrar(client, "r@teste.local")
    resposta = (await client.get("/api/interno/mensagens/2")).json()
    assert len(resposta) == 1 and resposta[0]["remetente_id"] == 2
    async with maker() as db:
        mensagens = (await db.execute(select(MensagemInterna))).scalars().all()
        assert len(mensagens) == 1


async def test_chat_interno_mostra_offline_e_guarda_mensagem(ambiente):
    client, maker = ambiente
    async with maker() as db:
        colega = await db.get(Usuario, 4)
        colega.online = False
        await db.commit()
    await entrar(client, "a@teste.local")
    grupos = (await client.get("/api/interno/setores")).json()
    assert next(item for item in grupos if item["nome"] == "Estoque")["pessoas"][0]["online"] is False
    assert (await client.post("/api/interno/mensagens/4", data={"texto": "Olá"})).status_code == 200


async def test_gestor_define_setor_interno_do_usuario(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    resposta = await client.post("/api/gestor/usuarios/3", data={
        "nome": "Vendedor B", "email": "b@teste.local", "role": "colaborador",
        "ativo": "on", "online": "on", "setor_interno_id": "2",
    })
    assert resposta.status_code == 200
    await entrar(client, "a@teste.local")
    grupos = (await client.get("/api/interno/setores")).json()
    assert [p["id"] for p in next(item for item in grupos if item["nome"] == "Estoque")["pessoas"]] == [4, 3]


async def test_historico_interno_paginar_sem_misturar_conversas(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add_all([MensagemInterna(remetente_id=2, destinatario_id=4, texto=f"item {i}") for i in range(55)])
        db.add(MensagemInterna(remetente_id=3, destinatario_id=4, texto="outra conversa"))
        await db.commit()
    await entrar(client, "a@teste.local")
    recentes = (await client.get("/api/interno/mensagens/4")).json()
    antigas = (await client.get("/api/interno/mensagens/4", params={"antes": recentes[0]["id"]})).json()
    assert len(recentes) == 50 and len(antigas) == 5
    assert antigas[0]["texto"] == "item 0"
    assert recentes[-1]["texto"] == "item 54"
    assert (await client.get("/api/interno/mensagens/4", params={"antes": antigas[0]["id"]})).json() == []
