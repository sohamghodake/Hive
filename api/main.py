import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from api.config import settings
from api.models.run import Run
from api.routers import agents, documents, health, runs, workspace
from api.services.ingest import backfill_unindexed
from db.session import _session_factory

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": %(message)s}',
)

_background: set[asyncio.Task] = set()


async def _fail_orphaned_runs() -> None:
    """Runs execute in-process, so any run still pending/running at startup was
    killed by the previous shutdown and will never finish on its own."""
    async with _session_factory() as db:
        result = await db.execute(
            update(Run)
            .where(Run.status.in_(("pending", "running")))
            .values(
                status="failed",
                error="Interrupted: the API restarted while this run was in progress.",
                finished_at=datetime.now(UTC),
            )
        )
        await db.commit()
    if result.rowcount:
        logging.getLogger(__name__).warning("marked %d orphaned run(s) as failed", result.rowcount)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await _fail_orphaned_runs()
    # Embedding takes seconds per document; do not hold up startup for it.
    task = asyncio.create_task(backfill_unindexed())
    _background.add(task)
    task.add_done_callback(_background.discard)
    yield


app = FastAPI(
    title="Hive",
    description="Multi-agent orchestration platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])
