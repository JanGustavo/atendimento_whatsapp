from types import SimpleNamespace

from sqlalchemy import select
from test_m1 import entrar

from app.models import AcessoRemoto, Chamado


async def test_formulario_publico_exige_token_e_registra_chamado(ambiente, monkeypatch):
    client, maker = ambiente
    monkeypatch.setattr(
        "app.api.chamados.get_settings",
        lambda: SimpleNamespace(chamado_install_token="token-de-instalacao"),
    )
    await entrar(client, "gestor@teste.local")
    criado = await client.post(
        "/api/computadores",
        data={"nome": "PC Vendas", "dono_id": "2", "grupo": "empresa"},
    )
    assert criado.status_code == 200
    pc_id = criado.json()["id"]
    assert (await client.get("/api/chamado/computadores")).status_code == 403
    assert (
        await client.post(
            "/api/chamado",
            data={"token": "errado", "computador_id": pc_id, "descricao": "Sem rede"},
        )
    ).status_code == 403
    lista = await client.get("/api/chamado/computadores?token=token-de-instalacao")
    assert lista.status_code == 200 and lista.json() == [{"id": pc_id, "nome": "PC Vendas"}]
    resposta = await client.post(
        "/api/chamado",
        data={
            "token": "token-de-instalacao",
            "computador_id": pc_id,
            "descricao": "Sem rede",
        },
    )
    assert resposta.status_code == 200 and resposta.json()["id"] > 0
    async with maker() as db:
        chamado = (await db.execute(select(Chamado))).scalar_one()
        assert (chamado.computador_id, chamado.descricao, chamado.status) == (
            pc_id,
            "Sem rede",
            "aberto",
        )


async def test_pc_do_dono_bloqueado_no_servidor_e_acesso_auditado(ambiente, monkeypatch):
    client, maker = ambiente
    monkeypatch.setattr(
        "app.api.chamados.get_settings",
        lambda: SimpleNamespace(chamado_install_token="token-de-instalacao"),
    )
    await entrar(client, "gestor@teste.local")
    empresa_id = (
        await client.post(
            "/api/computadores",
            data={"nome": "PC Estoque", "dono_id": "2", "grupo": "empresa"},
        )
    ).json()["id"]
    dono_id = (
        await client.post(
            "/api/computadores",
            data={"nome": "PC Dono", "dono_id": "1", "grupo": "dono"},
        )
    ).json()["id"]
    async with maker() as db:
        db.add_all(
            [
                Chamado(computador_id=empresa_id, descricao="Sistema lento", status="aberto"),
                Chamado(computador_id=dono_id, descricao="Monitor apagado", status="aberto"),
            ]
        )
        await db.commit()
        chamados = (await db.execute(select(Chamado).order_by(Chamado.id))).scalars().all()
        empresa_chamado, dono_chamado = [item.id for item in chamados]

    assert (await client.post(f"/api/chamados/{dono_chamado}/acessos")).status_code == 403

    async with maker() as db:
        assert (await db.execute(select(AcessoRemoto))).scalars().all() == []

    await entrar(client, "r@teste.local")
    lista = await client.get("/api/chamados")
    assert lista.status_code == 200 and len(lista.json()) == 2
    assert (await client.post(f"/api/chamados/{dono_chamado}/acessos")).status_code == 403
    resultado = await client.post(f"/api/chamados/{empresa_chamado}/acessos")
    assert resultado.status_code == 200 and resultado.json()["resultado"] == "simulado"
    async with maker() as db:
        acesso = (await db.execute(select(AcessoRemoto))).scalar_one()
        chamado = await db.get(Chamado, empresa_chamado)
        assert (acesso.chamado_id, acesso.computador_id, acesso.solicitante_id) == (
            empresa_chamado,
            empresa_id,
            4,
        )
        assert (
            acesso.resultado == "simulado"
            and acesso.inicio_em is not None
            and acesso.fim_em is not None
        )
        assert chamado.status == "em_atendimento"

    fechado = await client.post(
        f"/api/chamados/{empresa_chamado}/fechar",
        data={"solucao": "Reiniciei o sistema e testei a conexão."},
    )
    assert fechado.status_code == 200
    assert (await client.post(f"/api/chamados/{empresa_chamado}/acessos")).status_code == 409
    lista = (await client.get("/api/chamados")).json()
    resolvido = next(item for item in lista if item["id"] == empresa_chamado)
    assert resolvido["solucao"] == "Reiniciei o sistema e testei a conexão."
    assert resolvido["acessos"][0]["solicitante"] == "Responsável"
    await entrar(client, "a@teste.local")
    assert (await client.get("/api/chamados")).status_code == 403
    assert (await client.post(f"/api/chamados/{dono_chamado}/acessos")).status_code == 403


async def test_vendedor_abre_chamado_do_proprio_pc_sem_acesso_a_gestao(ambiente):
    client, maker = ambiente
    await entrar(client, "gestor@teste.local")
    pc_a = (
        await client.post(
            "/api/computadores",
            data={"nome": "PC do A", "dono_id": "2", "grupo": "empresa"},
        )
    ).json()["id"]
    pc_b = (
        await client.post(
            "/api/computadores",
            data={"nome": "PC do B", "dono_id": "3", "grupo": "empresa"},
        )
    ).json()["id"]
    await entrar(client, "a@teste.local")
    assert (await client.get("/api/meus-chamados/computadores")).json() == [
        {"id": pc_a, "nome": "PC do A"}
    ]
    assert (
        await client.post(
            "/api/meus-chamados",
            data={"computador_id": pc_b, "descricao": "Problema em outro PC"},
        )
    ).status_code == 404
    aberto = await client.post(
        "/api/meus-chamados",
        data={"computador_id": pc_a, "descricao": "Não consigo acessar o sistema"},
    )
    assert aberto.status_code == 200
    chamado_id = aberto.json()["id"]
    assert [item["id"] for item in (await client.get("/api/meus-chamados")).json()] == [chamado_id]
    assert (await client.get("/api/chamados")).status_code == 403
    assert (await client.post(f"/api/chamados/{chamado_id}/acessos")).status_code == 403
    assert (
        await client.post(f"/api/chamados/{chamado_id}/fechar", data={"solucao": "teste"})
    ).status_code == 403
    async with maker() as db:
        assert (await db.get(Chamado, chamado_id)).computador_id == pc_a
    await entrar(client, "r@teste.local")
    assert chamado_id in [item["id"] for item in (await client.get("/api/chamados")).json()]
