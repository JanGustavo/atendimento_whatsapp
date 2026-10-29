from datetime import timedelta

from sqlalchemy import select
from test_m1 import entrar

from app.core.utils import now
from app.models import Mensagem, MensagemInterna


async def test_eventos_conta_dez_mensagens_sem_vazar_outra_conversa(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    baseline = (await client.get("/api/eventos?inicio=true")).json()
    assert baseline["whatsapp"] == []
    async with maker() as db:
        db.add_all([Mensagem(conversa_id=10, origem="cliente", texto=str(i)) for i in range(10)])
        db.add(Mensagem(conversa_id=11, origem="cliente", texto="segredo de outro vendedor"))
        await db.commit()
    resposta = (
        await client.get(
            "/api/eventos",
            params={
                "whatsapp_apos": baseline["ultimo_whatsapp"],
                "interno_apos": baseline["ultimo_interno"],
            },
        )
    ).json()
    assert len(resposta["whatsapp"]) == 10
    assert all(item["conversa_id"] == 10 for item in resposta["whatsapp"])
    assert (
        await client.get(
            "/api/eventos",
            params={
                "whatsapp_apos": resposta["ultimo_whatsapp"],
            },
        )
    ).json()["whatsapp"] == []


async def test_simulador_toggle_do_gestor_bloqueia_envio(ambiente):
    client, _ = ambiente
    await entrar(client, "gestor@teste.local")
    assert (await client.post("/api/gestor/simulador", data={"ativo": "off"})).json() == {
        "ativo": False
    }
    assert (await client.get("/api/gestor/config")).json()["simulador_ativo"] is False
    assert (await client.get("/api/simulador")).status_code == 403
    assert (
        await client.post("/api/simulador", data={"cliente": "cliente1", "texto": "oi"})
    ).status_code == 403
    assert (await client.post("/api/gestor/simulador", data={"ativo": "on"})).json() == {
        "ativo": True
    }
    assert (await client.get("/api/simulador")).status_code == 200
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/gestor/simulador", data={"ativo": "off"})).status_code == 403


async def test_eventos_internos_entregues_apenas_ao_destinatario(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add_all(
            [
                MensagemInterna(remetente_id=3, destinatario_id=2, texto=f"recado {i}")
                for i in range(10)
            ]
        )
        db.add(MensagemInterna(remetente_id=3, destinatario_id=4, texto="outro destinatário"))
        await db.commit()
    await entrar(client, "a@teste.local")
    recebidas = (await client.get("/api/eventos")).json()
    assert len(recebidas["interno"]) == 10
    assert all(item["remetente_id"] == 3 for item in recebidas["interno"])


async def test_primeira_abertura_notifica_recentes_sem_reapresentar_antigas(ambiente):
    client, maker = ambiente
    async with maker() as db:
        db.add(
            MensagemInterna(
                remetente_id=3,
                destinatario_id=2,
                texto="antiga",
                criada_em=now() - timedelta(days=3),
            )
        )
        await db.flush()
        antiga = (
            await db.execute(select(MensagemInterna.id).where(MensagemInterna.texto == "antiga"))
        ).scalar_one()
        db.add(MensagemInterna(remetente_id=3, destinatario_id=2, texto="recente", criada_em=now()))
        await db.commit()
    await entrar(client, "a@teste.local")
    inicio = (await client.get("/api/eventos?inicio=true")).json()
    assert inicio["ultimo_interno"] > antiga
    assert [item["texto"] for item in inicio["interno"]] == ["recente"]
    assert (
        await client.get("/api/eventos", params={"interno_apos": inicio["ultimo_interno"]})
    ).json()["interno"] == []
