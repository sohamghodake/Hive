import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.dependencies import DBSession
from api.models.run import Run, RunStep
from api.schemas.run import RunCreate, RunDetail, RunOut
from db.session import _session_factory as session_factory
from orchestrator.graph import run_agent

router = APIRouter()


@router.get("", response_model=list[RunOut])
async def list_runs(db=DBSession, limit: int = 50, offset: int = 0):
    result = await db.execute(
        select(Run).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=RunOut, status_code=201)
async def create_run(body: RunCreate, background: BackgroundTasks, db=DBSession):
    run = Run(agent_id=body.agent_id, input=body.input, run_metadata=body.run_metadata)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    background.add_task(run_agent, str(run.id))
    return run


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: uuid.UUID, db=DBSession):
    result = await db.execute(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.steps), selectinload(Run.tool_calls))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.delete("/{run_id}", status_code=204)
async def delete_run(run_id: uuid.UUID, db=DBSession):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status == "running":
        raise HTTPException(409, "Cannot delete a run that is currently running")
    await db.delete(run)
    await db.commit()


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID):
    """SSE endpoint — streams step events as they're written to the DB."""
    # Deliberately not the request's DBSession: FastAPI closes a yield
    # dependency only after the response has finished, so for a stream its
    # transaction stayed open for up to 10 minutes. Behind PgBouncer's
    # transaction pooling that pinned a server connection per open run page.
    async with session_factory() as s:
        if await s.scalar(select(Run.id).where(Run.id == run_id)) is None:
            raise HTTPException(404, "Run not found")

    async def event_generator():
        last_seq = 0
        poll_interval = 0.5
        max_polls = 1200  # 10 min — rate-limit backoff can stretch a run

        for _ in range(max_polls):
            # A fresh short session per poll. Reusing the request's session kept
            # a transaction open for the whole stream and could serve stale ORM
            # objects from the identity map instead of newly committed rows.
            async with session_factory() as s:
                status = await s.scalar(select(Run.status).where(Run.id == run_id))
                steps = (await s.execute(
                    select(RunStep)
                    .where(RunStep.run_id == run_id, RunStep.sequence > last_seq)
                    .order_by(RunStep.sequence)
                )).scalars().all()

            if status is None:  # deleted mid-stream
                break

            for step in steps:
                last_seq = step.sequence
                payload = json.dumps({"type": "step", "data": {
                    "id": str(step.id),
                    "node": step.node,
                    "status": step.status,
                    "sequence": step.sequence,
                    "tool": (step.input or {}).get("tool"),
                }})
                yield f"data: {payload}\n\n"

            if status in ("completed", "failed"):
                yield f"data: {json.dumps({'type': 'done', 'status': status})}\n\n"
                break

            await asyncio.sleep(poll_interval)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
