import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    content_type: str
    size_bytes: int | None
    doc_metadata: dict
    embedded: bool
    created_at: datetime
