from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401

url = get_settings().database_url.replace("sqlite+aiosqlite:", "sqlite+pysqlite:", 1)
if not url.startswith("sqlite+pysqlite:"):
    raise RuntimeError("Migração alpha suporta apenas SQLite")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
