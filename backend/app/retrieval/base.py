from typing import Protocol

from app.types import AccessScope, RetrievalHit


class Retriever(Protocol):
    def search(self, query: str, scope: AccessScope, limit: int) -> list[RetrievalHit]: ...
