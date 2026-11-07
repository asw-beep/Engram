from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobAccepted(BaseModel):
    job_id: UUID


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    name: str
    config: dict[str, Any]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    status: str
    file_counts: dict[str, int]
    errors: list[dict[str, str]]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
