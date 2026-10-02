import os

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app
from api.dependencies import get_db
from db.base import Base

# Overridable so the suite can run either on the host or inside the api container,
# where the database is reachable as "postgres" rather than "localhost".
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://hive:hivepass@localhost:5432/hive_test"
)


@pytest_asyncio.fixture
async def engine():
    """Built per test.

    asyncpg connections are bound to the event loop that opened them, and
    pytest-asyncio runs each test in a fresh loop. A module-level engine
    therefore hands out connections belonging to a dead loop, which surfaces as
    "another operation is in progress" rather than anything obviously loop-related.
    """
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
