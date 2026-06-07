import uuid
from datetime import datetime

from pydantic import BaseModel


class RunCreate(BaseModel):
    agent_id: uuid.UUID
    input: dict
    metadata: dict = {}


class RunOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agent_id: uuid.UUID | None
    status: str
    input: dict
    output: dict | None
    error: str | None
    metadata: dict
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class StepOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    sequence: int
    node: str
    status: str
    input: dict | None
    output: dict | None
    started_at: datetime | None
    finished_at: datetime | None


class ToolCallOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None
    tool_name: str
    mcp_server: str | None
    input: dict
    output: dict | None
    error: str | None
    duration_ms: int | None
    called_at: datetime


class RunDetail(RunOut):
    steps: list[StepOut] = []
    tool_calls: list[ToolCallOut] = []
