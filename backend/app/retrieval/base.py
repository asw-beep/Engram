from dataclasses import dataclass
from typing import Protocol

from app.types import AccessScope, RetrievalHit


@dataclass(frozen=True)
class SearchResult:
    """Ranked hits and how they were found: "dense", "keyword", "hybrid" or "dense_fallback"."""

    hits: list[RetrievalHit]
    mode: str


class Retriever(Protocol):
    def search(self, query: str, scope: AccessScope, limit: int) -> SearchResult: ...
