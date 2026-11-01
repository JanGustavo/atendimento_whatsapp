import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "segredo-exclusivo-dos-testes-m1")
os.environ["WHATSAPP_PROVIDER"] = "simulador"
os.environ["ENABLE_SIMULATOR"] = "true"
os.environ["EXPEDIENTE_INICIO"] = "00:00"
os.environ["EXPEDIENTE_FIM"] = "23:59"
os.environ["TIMER_ESPERA_SEGUNDOS"] = "90"
os.environ["TIMER_AVISO_SEGUNDOS"] = "60"
os.environ["TIMER_MAXIMO_SEGUNDOS"] = "210"

from app.core.database import Base, get_db
from app.main import app
from app.models import Conversa, Setor, SetorInterno, SimuladorEstado, Usuario
from app.services.auth_service import get_password_hash


@pytest.fixture
async def ambiente():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def database_override():
        async with maker() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    async with maker() as db:
        db.add(SimuladorEstado(id=1, ativo=True))
        db.add_all(
            [
                SetorInterno(id=1, nome="Vendas"),
                SetorInterno(id=2, nome="Estoque"),
                SetorInterno(id=3, nome="Garantia"),
                SetorInterno(id=4, nome="Administração"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                Usuario(
                    id=1,
                    nome="Gestor",
                    email="gestor@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="gestor",
                    ativo=True,
                    online=True,
                    setor_interno_id=4,
                ),
                Usuario(
                    id=2,
                    nome="Vendedor A",
                    email="a@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="colaborador",
                    ativo=True,
                    online=True,
                    setor_interno_id=1,
                ),
                Usuario(
                    id=3,
                    nome="Vendedor B",
                    email="b@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="colaborador",
                    ativo=True,
                    online=True,
                    setor_interno_id=1,
                ),
                Usuario(
                    id=4,
                    nome="Responsável",
                    email="r@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="supervisor",
                    ativo=True,
                    online=True,
                    setor_interno_id=2,
                ),
                Usuario(
                    id=5,
                    nome="Vendedor C",
                    email="c@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="colaborador",
                    ativo=True,
                    online=True,
                    setor_interno_id=1,
                ),
                Usuario(
                    id=6,
                    nome="Responsável 2",
                    email="r2@teste.local",
                    senha_hash=get_password_hash("senha12345"),
                    role="supervisor",
                    ativo=True,
                    online=True,
                    setor_interno_id=3,
                ),
            ]
        )
        db.add_all(
            [
                Setor(id=1, nome="Vendas/Compra", ordem=1),
                Setor(id=2, nome="Devolução", ordem=2, responsavel_id=4),
                Setor(id=3, nome="Garantia", ordem=3, responsavel_id=6),
                Setor(id=4, nome="Outro", ordem=4, responsavel_id=4),
            ]
        )
        db.add_all(
            [
                Conversa(
                    id=10,
                    numero="551100001",
                    setor_id=1,
                    atribuido_id=2,
                    status="aberta",
                    etapa="atribuida",
                    timer_extensoes=0,
                ),
                Conversa(
                    id=11,
                    numero="551100002",
                    setor_id=1,
                    atribuido_id=3,
                    status="aberta",
                    etapa="atribuida",
                    timer_extensoes=0,
                ),
            ]
        )
        await db.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, maker
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
