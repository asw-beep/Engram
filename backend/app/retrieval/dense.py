from app.db.vector_index import VectorIndex
from app.embedding.base import Embedder
from app.types import AccessScope, RetrievalHit


class DenseRetriever:
    """Nearest chunks by BGE-M3 vector, filtered in Qdrant by tenant and principals."""

    def __init__(self, embedder: Embedder, index: VectorIndex):
        self._embedder = embedder
        self._index = index

    def search(self, query: str, scope: AccessScope, limit: int) -> list[RetrievalHit]:
        vector = self._embedder.embed_query(query)
        return [
            RetrievalHit(chunk_id, score)
            for chunk_id, score in self._index.search(vector, scope, limit)
        ]
