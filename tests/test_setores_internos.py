from app.models import MensagemGrupo
from test_m1 import entrar


async def test_exclusao_setor_interno_exige_gestor_e_setor_vazio(ambiente):
    client, _ = ambiente
    await entrar(client, "a@teste.local")
    assert (await client.delete("/api/gestor/setores-internos/2")).status_code == 403
    await entrar(client, "gestor@teste.local")
    assert (await client.delete("/api/gestor/setores-internos/1")).status_code == 409
    assert (await client.delete("/api/gestor/setores-internos/2")).status_code == 409
    criado = await client.post("/api/gestor/setores-internos", data={"nome": "Teste vazio", "icone": "estoque"})
    assert criado.status_code == 200
    setor_id = criado.json()["id"]
    assert (await client.delete(f"/api/gestor/setores-internos/{setor_id}")).status_code == 200
    assert (await client.delete(f"/api/gestor/setores-internos/{setor_id}")).status_code == 404


async def test_exclusao_preserva_historico_do_grupo(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    criado = await client.post("/api/gestor/setores-internos", data={"nome": "Com histórico", "icone": "equipe"})
    setor_id = criado.json()["id"]
    async with maker() as db:
        db.add(MensagemGrupo(setor_id=setor_id, remetente_id=1, texto="Mensagem antiga"))
        await db.commit()
    resposta = await client.delete(f"/api/gestor/setores-internos/{setor_id}")
    assert resposta.status_code == 409
