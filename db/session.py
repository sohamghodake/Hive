import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://hive:hivepass@localhost:5432/hive"
)

engine = create_async_engine(
    _DATABASE_URL,
    echo=os.getenv("ENVIRONMENT", "development") == "development",
    pool_size=10,
    max_overflow=20,
)

_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session
