from types import SimpleNamespace
from sqlalchemy import select
from app.core.database import get_session_maker
from app.main import app
from app.models import Atribuicao, Conversa, Mensagem
from app.providers import EvolutionProvider, MensagemEntrada, simulador_provider
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
    assert falso.envios == [('551100001', 'Olá')]
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


async def test_webhook_ignora_duplicado_fromme_grupo_e_aceita_midia(ambiente, monkeypatch):
    client, maker = ambiente
    app.dependency_overrides[get_session_maker] = lambda: maker
    config = SimpleNamespace(evolution_webhook_secret='segredo', evolution_base_url='http://evolution:8080',
                             evolution_api_key='chave', evolution_instancia='fortgiro')
    monkeypatch.setattr('app.api.webhook.get_settings', lambda: config)
    def payload(identidade, jid='55118880000@s.whatsapp.net', from_me=False, message=None):
        return {'event': 'messages.upsert', 'data': {'key': {'id': identidade, 'remoteJid': jid, 'fromMe': from_me},
                'message': message or {'conversation': 'oi'}}}
    cabecalho = {'X-Webhook-Secret': 'segredo'}
    assert (await client.post('/webhook/whatsapp', json=payload('x'), headers={})).status_code == 401
    for item in [payload('x'), payload('x'), payload('mim', from_me=True), payload('grupo', jid='123@g.us'),
                 payload('midia', message={'imageMessage': {'caption': 'foto'}})]:
        assert (await client.post('/webhook/whatsapp', json=item, headers=cabecalho)).status_code == 200
    async with maker() as db:
        conversa = (await db.execute(select(Conversa).where(Conversa.numero == '55118880000'))).scalar_one()
        mensagens = (await db.execute(select(Mensagem).where(Mensagem.conversa_id == conversa.id).order_by(Mensagem.id))).scalars().all()
        assert [m.provider_id for m in mensagens if m.origem == 'cliente'] == ['x', 'midia']
        assert [m.texto for m in mensagens if m.origem == 'bot'] == ['Escolha o setor:\n1 - Vendas/Compra\n2 - Devolução\n3 - Garantia\n4 - Outro', 'No momento só atendemos por texto']
        assert conversa.etapa == 'menu_setor'


async def test_provider_evolution_http_e_regras_iguais(ambiente, monkeypatch):
    import httpx
    import json
    chamadas = []

    def responder(request):
        chamadas.append(request)
        if request.url.path.startswith('/message/sendText/'):
            assert request.headers['apikey'] == 'chave'
            if len(chamadas) == 1:
                assert json.loads(request.content) == {"number": "55118880000", "text": "Olá"}
            return httpx.Response(201, json={'key': {'id': 'saida'}})
        return httpx.Response(200, json={'instance': {'state': 'open'}})

    original = httpx.AsyncClient
    transporte = httpx.MockTransport(responder)
    monkeypatch.setattr('app.providers.evolution.httpx.AsyncClient', lambda **kwargs: original(transport=transporte, **kwargs))
    provider = EvolutionProvider('http://evolution', 'chave', 'instancia')
    await provider.enviar_texto('+55 (11) 888-0000@s.whatsapp.net', 'Olá')
    assert await provider.status() == 'conectado'
    assert [item.url.path for item in chamadas] == ['/message/sendText/instancia', '/instance/connectionState/instancia']

    _, maker = ambiente
    async with maker() as db:
        await receber_mensagem(db, simulador_provider, MensagemEntrada('sim-1', '55118889991', 'invalido'))
    async with maker() as db:
        await receber_mensagem(db, provider, MensagemEntrada('evo-1', '55118889992', 'invalido'))
    async with maker() as db:
        conversas = (await db.execute(select(Conversa).where(Conversa.numero.in_(['55118889991', '55118889992'])).order_by(Conversa.numero))).scalars().all()
        assert [item.etapa for item in conversas] == ['menu_setor', 'menu_setor']
