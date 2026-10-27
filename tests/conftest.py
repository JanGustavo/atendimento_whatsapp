import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "segredo-exclusivo-dos-testes-m1")

from app.core.database import Base, get_db
from app.main import app
from app.models import Conversa, Setor, Usuario
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
        db.add_all([
            Usuario(id=1, nome="Gestor", email="gestor@teste.local", senha_hash=get_password_hash("senha12345"), role="gestor", ativo=True, online=True),
            Usuario(id=2, nome="Vendedor A", email="a@teste.local", senha_hash=get_password_hash("senha12345"), role="vendedor", ativo=True, online=True),
            Usuario(id=3, nome="Vendedor B", email="b@teste.local", senha_hash=get_password_hash("senha12345"), role="vendedor", ativo=True, online=True),
            Usuario(id=4, nome="Responsável", email="r@teste.local", senha_hash=get_password_hash("senha12345"), role="responsavel", ativo=True, online=True),
            Usuario(id=5, nome="Vendedor C", email="c@teste.local", senha_hash=get_password_hash("senha12345"), role="vendedor", ativo=True, online=True),
            Usuario(id=6, nome="Responsável 2", email="r2@teste.local", senha_hash=get_password_hash("senha12345"), role="responsavel", ativo=True, online=True),
        ])
        db.add_all([
            Setor(id=1, nome="Vendas/Compra", ordem=1),
            Setor(id=2, nome="Devolução", ordem=2, responsavel_id=4),
            Setor(id=3, nome="Garantia", ordem=3, responsavel_id=6),
            Setor(id=4, nome="Outro", ordem=4, responsavel_id=4),
        ])
        db.add_all([
            Conversa(id=10, numero="551100001", setor_id=1, atribuido_id=2, status="aberta", etapa="atribuida", timer_extensoes=0),
            Conversa(id=11, numero="551100002", setor_id=1, atribuido_id=3, status="aberta", etapa="atribuida", timer_extensoes=0),
        ])
        await db.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, maker
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
