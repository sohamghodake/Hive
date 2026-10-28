import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from api.config import settings
from orchestrator.tools import TOOL_MAP


def _known_tools(tools: list[str]) -> list[str]:
    """Reject tool names the registry does not have.

    An unknown name used to be stored as-is, then silently dropped when the
    model was bound and refused if the model asked for it, so a typo surfaced
    only as an agent that mysteriously could not do its job.
    """
    unknown = sorted(set(tools) - TOOL_MAP.keys())
    if unknown:
        raise ValueError(
            f"Unknown tool(s): {', '.join(unknown)}. Available: {', '.join(sorted(TOOL_MAP))}"
        )
    return tools


ToolNames = Annotated[list[str], AfterValidator(_known_tools)]


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str
    # LLM_MODEL, the same setting the orchestrator falls back to.
    model: str = Field(default_factory=lambda: settings.llm_model)
    tools: ToolNames = []
    config: dict = {}


class AgentUpdate(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: ToolNames | None = None
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
