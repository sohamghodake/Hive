import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str
    model: str = "kimi-k2.7-code:cloud"
    tools: list[str] = []
    config: dict = {}


class AgentUpdate(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: dict | None = None


class AgentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    model: str
    tools: list
    config: dict
    created_at: datetime
    updated_at: datetime
