from test_m1 import entrar

from app.models import Usuario
from app.services.auth_service import verify_password


async def test_vendedor_altera_propria_senha_com_senha_atual(ambiente):
    client, maker = ambiente
    await entrar(client, "a@teste.local")
    rota = "/api/auth/senha"
    assert (
        await client.post(
            rota,
            data={
                "senha_atual": "errada",
                "senha_nova": "nova-senha-123",
                "confirmacao": "nova-senha-123",
            },
        )
    ).status_code == 422
    assert (
        await client.post(
            rota,
            data={
                "senha_atual": "senha12345",
                "senha_nova": "nova-senha-123",
                "confirmacao": "outra",
            },
        )
    ).status_code == 422
    assert (
        await client.post(
            rota,
            data={
                "senha_atual": "senha12345",
                "senha_nova": "nova-senha-123",
                "confirmacao": "nova-senha-123",
            },
        )
    ).status_code == 200
    async with maker() as db:
        usuario = await db.get(Usuario, 2)
        assert verify_password("nova-senha-123", usuario.senha_hash)
    assert (
        await client.post(
            "/api/auth/login",
            data={
                "email": "a@teste.local",
                "senha": "senha12345",
            },
        )
    ).status_code == 401
