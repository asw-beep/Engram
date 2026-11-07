"""Types shared across modules that must not import each other."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AccessScope:
    """Who is asking: their tenant and the principals they hold."""

    tenant_id: UUID
    principals: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: UUID
    score: float


@dataclass(frozen=True)
class Passage:
    """A retrieved chunk that passed the recheck, with what a citation needs."""

    chunk_id: UUID
    content: str
    score: float
    document_id: UUID
    document_path: str
    source_name: str
    source_type: str
    source_config: dict
    heading_path: tuple[str, ...]
    start_line: int | None
    end_line: int | None
    page_start: int | None
    page_end: int | None
    revision: str | None
