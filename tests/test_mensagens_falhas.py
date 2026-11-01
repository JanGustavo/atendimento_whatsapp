from sqlalchemy import select
from test_m1 import entrar

from app.models import Mensagem


class ProviderFalha:
    def __init__(self):
        self.falhar = True
        self.envios = []

    async def enviar_texto(self, numero, texto):
        if self.falhar:
            raise RuntimeError("indisponível")
        self.envios.append((numero, texto))
        return "wamid.teste"


async def test_editar_antes_de_reenviar_e_impedir_alteracao_apos_envio(ambiente, monkeypatch):
    client, maker = ambiente
    provider = ProviderFalha()
    monkeypatch.setattr("app.api.atendimentos.provider_para_numero", lambda _: provider)
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/atendimentos/10/mensagens", data={"texto": "errado"})).status_code == 502
    async with maker() as db:
        mensagem = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10))).scalar_one()
        mensagem_id = mensagem.id
    rota = f"/api/atendimentos/10/mensagens/{mensagem_id}"
    assert (await client.patch(rota, data={"texto": "  correto  "})).json()["texto"] == "correto"
    assert (await client.patch(rota, data={"texto": "  "})).status_code == 422
    await entrar(client, "b@teste.local")
    assert (await client.patch(rota, data={"texto": "outro"})).status_code == 404
    assert (await client.delete(rota)).status_code == 404
    await entrar(client, "a@teste.local")
    provider.falhar = False
    assert (await client.post(f"{rota}/reenviar")).status_code == 200
    assert provider.envios == [("551100001", "*Atendente Vendedor A*\ncorreto")]
    assert (await client.patch(rota, data={"texto": "alterado"})).status_code == 409
    assert (await client.delete(rota)).status_code == 409


async def test_descartar_mensagem_falha_remove_apenas_registro_local(ambiente, monkeypatch):
    client, maker = ambiente
    provider = ProviderFalha()
    monkeypatch.setattr("app.api.atendimentos.provider_para_numero", lambda _: provider)
    await entrar(client, "a@teste.local")
    assert (await client.post("/api/atendimentos/10/mensagens", data={"texto": "não enviada"})).status_code == 502
    async with maker() as db:
        mensagem = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10))).scalar_one()
        mensagem_id = mensagem.id
    rota = f"/api/atendimentos/10/mensagens/{mensagem_id}"
    assert (await client.delete(rota)).json() == {"id": mensagem_id, "descartada": True}
    assert (await client.delete(rota)).status_code == 404
    async with maker() as db:
        assert await db.get(Mensagem, mensagem_id) is None
    assert provider.envios == []
