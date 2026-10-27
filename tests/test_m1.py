from sqlalchemy import select

from app.models import Atribuicao, Conversa, Mensagem


async def entrar(client, email):
    resposta = await client.post("/login", data={"email": email, "senha": "senha12345"})
    assert resposta.status_code == 303
    assert "httponly" in resposta.headers["set-cookie"].lower()


async def test_login_sem_cadastro_publico_e_papeis(ambiente):
    client, _ = ambiente
    assert (await client.get("/atendimentos")).status_code == 401
    assert (await client.post("/auth/register", json={})).status_code == 404
    await entrar(client, "a@teste.local")
    assert (await client.get("/gestor")).status_code == 403
    assert (await client.post("/gestor/usuarios", data={"nome": "X"})).status_code == 403


async def test_isolamento_lista_detalhe_envio_e_busca_por_id(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    lista = await client.get("/atendimentos")
    assert lista.status_code == 200
    assert "551100001" in lista.text
    assert "551100002" not in lista.text
    busca = await client.get("/atendimentos?q=551100002")
    assert "Nenhuma conversa atribuída" in busca.text
    assert 'href="/atendimentos/11"' not in busca.text
    assert (await client.get("/atendimentos/11")).status_code == 404
    assert (await client.get("/atendimentos/11", headers={"HX-Request": "true"})).status_code == 404
    parcial = await client.get("/atendimentos", headers={"HX-Request": "true"})
    assert 'href="/atendimentos/11"' not in parcial.text
    assert (await client.post("/atendimentos/11/mensagens", data={"texto": "Oi"})).status_code == 404
    assert (await client.get("/atendimentos/10")).status_code == 200
    assert (await client.post("/atendimentos/10/mensagens", data={"texto": "Olá"})).status_code == 303
    async with maker() as db:
        mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10))).scalars().all()
        assert len(mensagens) == 1 and mensagens[0].autor_id == 2
        conversa = await db.get(Conversa, 10)
        assert conversa.primeira_resposta_em is not None


async def test_gestor_transfere_e_registra_historico(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    assert (await client.get("/gestor")).status_code == 200
    resposta = await client.post("/gestor/conversas/10/transferir", data={"usuario_id": "3"})
    assert resposta.status_code == 303
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        historico = (await db.execute(select(Atribuicao).where(Atribuicao.conversa_id == 10))).scalars().all()
        assert conversa.atribuido_id == 3
        assert [(item.de_usuario_id, item.para_usuario_id) for item in historico] == [(2, 3)]
    await entrar(client, "a@teste.local")
    assert (await client.get("/atendimentos/10")).status_code == 404
    await entrar(client, "b@teste.local")
    assert (await client.get("/atendimentos/10")).status_code == 200
