from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

database_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

# Configurações do engine
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "future": True,
}

# Configurações específicas para asyncpg + PgBouncer (Supabase)
if database_url.startswith("postgresql+asyncpg"):
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,  # evita DuplicatePreparedStatementError
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
    """
    Em produção (Render + Supabase), NÃO executar create_all().
    O Supabase usa PgBouncer em modo transaction, que não suporta introspecção
    e quebra com prepared statements internos do SQLAlchemy.
    """
    from src.models import entities  # noqa: F401

    # Só cria tabelas em ambiente local
    if settings.app_env.lower() == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
