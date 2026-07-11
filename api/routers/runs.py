import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.dependencies import DBSession
from api.models.run import Run
from api.schemas.run import RunCreate, RunDetail, RunOut
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


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, db=DBSession):
    """SSE endpoint — streams step events as they're written to the DB."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    async def event_generator():
        seen_step_ids: set[str] = set()
        poll_interval = 0.5
        max_polls = 300  # 2.5 min timeout

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            await db.refresh(run)

            result = await db.execute(
                select(Run)
                .where(Run.id == run_id)
                .options(selectinload(Run.steps))
            )
            fresh = result.scalar_one_or_none()
            if not fresh:
                break

            for step in fresh.steps:
                sid = str(step.id)
                if sid not in seen_step_ids:
                    seen_step_ids.add(sid)
                    payload = json.dumps({"type": "step", "data": {
                        "id": sid,
                        "node": step.node,
                        "status": step.status,
                        "sequence": step.sequence,
                    }})
                    yield f"data: {payload}\n\n"

            if fresh.status in ("completed", "failed"):
                yield f"data: {json.dumps({'type': 'done', 'status': fresh.status})}\n\n"
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")
