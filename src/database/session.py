from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

database_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "future": True,
}

if database_url.startswith("postgresql+asyncpg"):
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,  # Fix para Supabase pgbouncer (pool_mode=transaction)
        "server_settings": {"jit": "off"},
    }

engine = create_async_engine(database_url, **engine_kwargs)

SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return SessionFactory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


async def init_db() -> None:
    # Importa os modelos para registrar os mapeamentos no SQLAlchemy
    from src.models import entities  # noqa: F401

    async with engine.begin() as conn:
        # O schema já existe no Supabase; create_all mantém compatível em ambiente local/dev.
        await conn.run_sync(Base.metadata.create_all)
