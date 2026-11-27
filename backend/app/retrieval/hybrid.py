import logging
from concurrent.futures import ThreadPoolExecutor

from app.retrieval.base import Retriever, SearchResult
from app.retrieval.fusion import reciprocal_rank_fusion
from app.types import AccessScope, RetrievalHit

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Dense and keyword search in parallel, merged with Reciprocal Rank Fusion (spec §5).

    Each hit's score is its RRF score, which ranks but isn't comparable to an evidence cutoff.
    If keyword search fails, the dense hits come back alone as "dense_fallback"; if dense
    search fails, the error propagates, because keyword search alone isn't offered.
    """

    def __init__(self, dense: Retriever, keyword: Retriever, candidate_limit: int, rrf_k: int):
        self._dense = dense
        self._keyword = keyword
        self._candidate_limit = candidate_limit
        self._rrf_k = rrf_k

    def search(self, query: str, scope: AccessScope, limit: int) -> SearchResult:
        # A pool per search, so concurrent questions never queue behind each other's searches.
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hybrid-search")
        try:
            dense_search = pool.submit(self._dense.search, query, scope, self._candidate_limit)
            keyword_search = pool.submit(self._keyword.search, query, scope, self._candidate_limit)
            dense = dense_search.result()
            try:
                keyword = keyword_search.result()
            except Exception:
                logger.warning(
                    "Keyword search failed; answering from dense search alone", exc_info=True
                )
                return SearchResult(dense.hits[:limit], "dense_fallback")
        finally:
            # Don't hold a dense failure back until the keyword search ends; it finishes alone.
            pool.shutdown(wait=False)
        fused = reciprocal_rank_fusion(
            [[hit.chunk_id for hit in dense.hits], [hit.chunk_id for hit in keyword.hits]],
            self._rrf_k,
        )
        return SearchResult(
            [RetrievalHit(chunk_id, score) for chunk_id, score in fused[:limit]], "hybrid"
        )
