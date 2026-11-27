from app.db.keyword_index import KeywordIndex
from app.retrieval.base import SearchResult
from app.types import AccessScope, RetrievalHit


class KeywordRetriever:
    """BM25 matches from OpenSearch, filtered there by tenant and principals."""

    def __init__(self, index: KeywordIndex):
        self._index = index

    def search(self, query: str, scope: AccessScope, limit: int) -> SearchResult:
        hits = [
            RetrievalHit(chunk_id, score)
            for chunk_id, score in self._index.search(query, scope, limit)
        ]
        return SearchResult(hits, "keyword")
