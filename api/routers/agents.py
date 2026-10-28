import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import DBSession
from api.models.agent import Agent
from api.schemas.agent import AgentCreate, AgentOut, AgentUpdate

router = APIRouter()


@router.get("", response_model=list[AgentOut])
async def list_agents(db=DBSession):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(body: AgentCreate, db=DBSession):
    agent = Agent(**body.model_dump())
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError:
        # The unique index on name is the source of truth; a check-then-insert
        # would race with a concurrent create of the same name.
        await db.rollback()
        raise HTTPException(409, f"An agent named {body.name!r} already exists") from None
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: uuid.UUID, db=DBSession):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: uuid.UUID, body: AgentUpdate, db=DBSession):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: uuid.UUID, db=DBSession):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()
