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


class QuestionIn(BaseModel):
    question: str


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    marker: int
    document_path: str
    source_name: str
    heading_path: list[str]
    start_line: int | None
    end_line: int | None
    page_start: int | None
    page_end: int | None
    revision: str | None
    snippet: str
    url: str | None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    outcome: str
    answer: str | None
    citations: list[CitationOut]
    passages: list[CitationOut]
