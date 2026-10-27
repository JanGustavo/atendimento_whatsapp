"""Sanidade das rotas usadas pelo React, sem banco externo."""
from test_m1 import entrar


async def test_login_json_cookie_logout_e_isolamento(ambiente):
    client, _ = ambiente
    assert (await client.post('/api/auth/login', data={'email': 'a@teste.local', 'senha': 'errada'})).status_code == 401
    await entrar(client, 'a@teste.local')
    assert (await client.get('/api/atendimentos')).json()[0]['id'] == 10
    assert (await client.get('/api/atendimentos/11')).status_code == 404
    assert (await client.post('/api/atendimentos/11/encerrar')).status_code == 404
    assert (await client.get('/api/gestor/config')).status_code == 403
    saida = await client.post('/api/auth/logout')
    assert saida.json() == {'ok': True}
    assert (await client.get('/api/me')).status_code == 401


async def test_health_e_webhook_exige_seguro(ambiente):
    client, _ = ambiente
    assert (await client.get('/health')).json() == {'status': 'ok'}
    assert (await client.post('/webhook/whatsapp', json={})).status_code == 401
    assert (await client.get('/api/inexistente')).status_code == 404
