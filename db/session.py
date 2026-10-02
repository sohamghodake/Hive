import os
from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# In docker-compose this points at PgBouncer (transaction pooling), not Postgres.
_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://hive:hivepass@localhost:5432/hive"
)

# PgBouncer in transaction mode hands each transaction whichever server
# connection is free, so per-connection state cannot be relied on between
# transactions. asyncpg's default prepared-statement names (__asyncpg_stmt_1__,
# _2__, ...) collide across clients sharing a server connection; random names
# and no client-side statement cache avoid that. Harmless against Postgres
# directly, so the same settings serve both.
PGBOUNCER_SAFE_CONNECT_ARGS = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
}

# One engine for the whole process. Runs used to create their own engine each,
# so N concurrent runs opened N separate pools against the database.
engine = create_async_engine(
    _DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args=PGBOUNCER_SAFE_CONNECT_ARGS,
)

_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session
