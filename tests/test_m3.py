from sqlalchemy import select
from app.models import Atribuicao, Conversa, Mensagem
from app.providers import MensagemEntrada, simulador_provider
from app.services.atendimento import receber_mensagem
from test_m1 import entrar


class ProviderFalso:
    def __init__(self, falhar=False):
        self.falhar = falhar
        self.envios = []

    async def enviar_texto(self, numero, texto):
        if self.falhar:
            raise RuntimeError('indisponível')
        self.envios.append((numero, texto))


async def test_vendedor_so_cancela_timer_apos_envio_confirmado(ambiente, monkeypatch):
    client, maker = ambiente
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        from datetime import datetime
        conversa.timer_prazo_em = datetime(2026, 10, 27, 12)
        await db.commit()
    falso = ProviderFalso(True)
    monkeypatch.setattr('app.api.atendimentos.provider_para_numero', lambda _: falso)
    await entrar(client, 'a@teste.local')
    resposta = await client.post('/api/atendimentos/10/mensagens', data={'texto': 'Olá'})
    assert resposta.status_code == 502
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        mensagem = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10))).scalar_one()
        assert mensagem.envio_status == 'falhou'
        assert conversa.timer_prazo_em is not None and conversa.primeira_resposta_em is None
    falso.falhar = False
    assert (await client.post('/api/atendimentos/10/mensagens', data={'texto': 'Olá'})).status_code == 200
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10).order_by(Mensagem.id))).scalars().all()
        assert [m.envio_status for m in mensagens] == ['falhou', 'enviada']
        assert conversa.timer_prazo_em is None and conversa.primeira_resposta_em is not None
    assert falso.envios == [('551100001', '*Atendente Vendedor A*\nOlá')]


async def test_atendente_transfere_com_isolamento_e_historico(ambiente, monkeypatch):
    client, maker = ambiente
    falso = ProviderFalso()
    monkeypatch.setattr('app.api.atendimentos.provider_para_numero', lambda _: falso)
    await entrar(client, 'a@teste.local')
    detalhe = (await client.get('/api/atendimentos/10')).json()
    assert {'valor': 'vendedor:3', 'nome': 'Vendas · Vendedor B'} in detalhe['destinos']
    assert (await client.post('/api/atendimentos/11/transferir', data={'destino': 'vendedor:5'})).status_code == 404
    assert (await client.post('/api/atendimentos/10/transferir', data={'destino': 'vendedor:3'})).status_code == 200
    assert (await client.get('/api/atendimentos/10')).status_code == 404
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        historico = (await db.execute(select(Atribuicao).where(Atribuicao.conversa_id == 10))).scalar_one()
        assert (conversa.setor_id, conversa.atribuido_id) == (1, 3)
        assert (historico.de_usuario_id, historico.para_usuario_id, historico.motivo) == (2, 3, 'atendente')
    assert falso.envios == [('551100001', 'Seu atendimento foi transferido para Vendedor B.')]


async def test_atendente_transfere_para_setor_fixo(ambiente, monkeypatch):
    client, maker = ambiente
    falso = ProviderFalso()
    monkeypatch.setattr('app.api.atendimentos.provider_para_numero', lambda _: falso)
    await entrar(client, 'a@teste.local')
    assert (await client.post('/api/atendimentos/10/transferir', data={'destino': 'setor:3'})).status_code == 200
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        assert (conversa.setor_id, conversa.atribuido_id, conversa.timer_prazo_em) == (3, 6, None)
    assert (await client.get('/api/atendimentos/11')).status_code == 404


async def test_numero_encerrado_abre_nova_conversa_e_duplicata_nao_abre_outra(ambiente):
    _, maker = ambiente
    async with maker() as db:
        await receber_mensagem(db, simulador_provider, MensagemEntrada('nova-1', '55118889999', 'oi'))
    async with maker() as db:
        primeira = (await db.execute(select(Conversa).where(Conversa.numero == '55118889999'))).scalar_one()
        primeira.status = 'encerrada'
        primeira.etapa = 'encerrada'
        await db.commit()
    async with maker() as db:
        await receber_mensagem(db, simulador_provider, MensagemEntrada('nova-1', '55118889999', 'oi'))
        await receber_mensagem(db, simulador_provider, MensagemEntrada('nova-2', '55118889999', 'novo'))
    async with maker() as db:
        conversas = (await db.execute(select(Conversa).where(Conversa.numero == '55118889999').order_by(Conversa.id))).scalars().all()
        assert len(conversas) == 2
        assert [c.status for c in conversas] == ['encerrada', 'aberta']
        assert conversas[1].etapa == 'menu_setor'


async def test_transferencia_manual_registra_historico_e_avisa(ambiente, monkeypatch):
    client, maker = ambiente
    falso = ProviderFalso()
    monkeypatch.setattr('app.api.gestor.provider_para_numero', lambda _: falso)
    from app.providers import simulador_provider
    monkeypatch.setattr('app.api.frontend.provider_atual', lambda: simulador_provider)
    await entrar(client, 'gestor@teste.local')
    assert (await client.get('/api/gestor/whatsapp-status')).json() == {'status': 'simulado'}
    assert (await client.post('/api/gestor/conversas/10/transferir', data={'usuario_id': '3'})).status_code == 200
    async with maker() as db:
        conversa = await db.get(Conversa, 10)
        historico = (await db.execute(select(Atribuicao).where(Atribuicao.conversa_id == 10))).scalars().all()
        aviso = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == 10))).scalar_one()
        assert conversa.atribuido_id == 3
        assert (historico[0].de_usuario_id, historico[0].para_usuario_id, historico[0].motivo) == (2, 3, 'gestor')
        assert aviso.envio_status == 'enviada'
    assert falso.envios == [('551100001', 'Seu atendimento foi transferido para Vendedor B.')]
