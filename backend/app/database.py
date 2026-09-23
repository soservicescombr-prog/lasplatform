# netguard/backend/app/database.py
"""
NetGuard - Configuração do banco de dados (SQLAlchemy Async).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url_computed,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


# create_all() does not evolve existing tables. These additive migrations keep
# installations upgraded from intermediate 1.5.x builds schema-compatible.
COMPATIBILITY_MIGRATIONS = (
    "ALTER TABLE device_metrics ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS load_15m DOUBLE PRECISION",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS network_packets_sent BIGINT",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS network_packets_recv BIGINT",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS network_send_bps DOUBLE PRECISION",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS network_recv_bps DOUBLE PRECISION",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS disk_read_bytes BIGINT",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS disk_write_bytes BIGINT",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS disk_read_bps DOUBLE PRECISION",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS disk_write_bps DOUBLE PRECISION",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS process_count INTEGER",
    "ALTER TABLE agent_metrics ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE log_metrics ADD COLUMN IF NOT EXISTS minimum_span_seconds INTEGER NOT NULL DEFAULT 180",
)


async def get_db() -> AsyncSession:
    """Dependency que fornece sessão de banco para cada request."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Cria tabelas uma única vez, mesmo com vários workers no startup."""
    async with engine.begin() as conn:
        # Uvicorn inicia o lifespan em cada worker. O lock transacional evita
        # que dois processos executem CREATE TABLE simultaneamente no PostgreSQL.
        await conn.execute(text("SELECT pg_advisory_xact_lock(2026092301)"))
        await conn.run_sync(Base.metadata.create_all)
        for statement in COMPATIBILITY_MIGRATIONS:
            await conn.execute(text(statement))
