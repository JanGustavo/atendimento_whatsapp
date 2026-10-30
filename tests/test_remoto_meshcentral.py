from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from test_m1 import entrar

from app.models import AcessoRemoto, Chamado, Computador
from app.services.remoto import RemotoMeshCentral


def test_link_meshcentral_usa_node_id_codificado():
    provider = RemotoMeshCentral("https://mesh.jangustavo.me")
    computador = Computador(nome="PC", grupo="empresa", mesh_node_id="node//abc+def")
    link = provider.link_acesso(computador)
    assert link.startswith("https://mesh.jangustavo.me/?")
    assert parse_qs(urlparse(link).query) == {"node": ["node//abc+def"], "viewmode": ["11"]}


async def test_meshcentral_exige_node_id_e_preserva_regra_do_pc_do_dono(ambiente, monkeypatch):
    from sqlalchemy import select

    client, maker = ambiente
    monkeypatch.setattr(
        "app.services.remoto.get_settings",
        lambda: SimpleNamespace(
            remoto_provider="meshcentral", meshcentral_url="https://mesh.jangustavo.me"
        ),
    )
    await entrar(client, "gestor@teste.local")
    ids = []
    for nome, grupo, node in [
        ("PC com agente", "empresa", "node//abc"),
        ("PC sem agente", "empresa", ""),
        ("PC do dono", "dono", "node//dono"),
    ]:
        resposta = await client.post(
            "/api/computadores",
            data={
                "nome": nome,
                "dono_id": "2",
                "grupo": grupo,
                "mesh_node_id": node,
            },
        )
        assert resposta.status_code == 200
        ids.append(resposta.json()["id"])
    async with maker() as db:
        db.add_all(
            [Chamado(computador_id=pc_id, descricao="Problema", status="aberto") for pc_id in ids]
        )
        await db.commit()
        chamados = (await db.execute(select(Chamado).order_by(Chamado.id))).scalars().all()
        chamados_ids = [item.id for item in chamados]
    assert (await client.post(f"/api/chamados/{chamados_ids[2]}/acessos")).status_code == 403
    assert (await client.post(f"/api/chamados/{chamados_ids[1]}/acessos")).status_code == 409
    resposta = await client.post(f"/api/chamados/{chamados_ids[0]}/acessos")
    assert resposta.status_code == 200
    assert resposta.json()["resultado"] == "pendente"
    assert resposta.json()["acesso_url"] is None
    lista = (await client.get("/api/chamados")).json()
    assert next(item for item in lista if item["id"] == chamados_ids[0])["acessos"][0]["acesso_url"] is None
    async with maker() as db:
        acessos = (await db.execute(select(AcessoRemoto))).scalars().all()
        assert len(acessos) == 1
        assert acessos[0].resultado == "pendente" and acessos[0].fim_em is None
