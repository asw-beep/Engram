import logging
import threading
from uuid import uuid4

import pytest

from app.retrieval.base import SearchResult
from app.retrieval.dense import DenseRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.keyword import KeywordRetriever
from app.retrieval.pipeline import retrieve_passages
from app.services import build_services
from app.types import RetrievalHit
from tests.tenants import DEFAULT_SCOPE

A, B, C = (uuid4() for _ in range(3))


class FixedRetriever:
    """Returns the given chunk IDs in order, scored from 0.9 down, and records each limit."""

    def __init__(self, chunk_ids, mode, barrier=None):
        self.chunk_ids = chunk_ids
        self.mode = mode
        self.barrier = barrier
        self.limits = []

    def search(self, query, scope, limit):
        self.limits.append(limit)
        if self.barrier is not None:
            self.barrier.wait()
        hits = [RetrievalHit(chunk_id, 0.9 - n / 100) for n, chunk_id in enumerate(self.chunk_ids)]
        return SearchResult(hits[:limit], self.mode)


class BrokenRetriever:
    def search(self, query, scope, limit):
        raise ConnectionError("unavailable (test)")


def _hybrid(dense, keyword):
    return HybridRetriever(dense, keyword, candidate_limit=50, rrf_k=60)


def _ids(result):
    return [hit.chunk_id for hit in result.hits]


def test_a_chunk_found_by_both_searches_appears_once_first():
    result = _hybrid(FixedRetriever([A, B], "dense"), FixedRetriever([B, C], "keyword")).search(
        "q", DEFAULT_SCOPE, 10
    )
    assert result.mode == "hybrid"
    assert _ids(result) == [B, A, C]
    assert result.hits[0].score == pytest.approx(1 / 62 + 1 / 61)


def test_each_search_is_asked_for_the_candidate_limit_and_the_top_limit_is_kept():
    dense, keyword = FixedRetriever([A, B], "dense"), FixedRetriever([B, C], "keyword")
    result = _hybrid(dense, keyword).search("q", DEFAULT_SCOPE, 2)
    assert dense.limits == [50] and keyword.limits == [50]
    assert _ids(result) == [B, A]


def test_the_two_searches_run_at_the_same_time():
    # Each search waits for the other to start; run one after the other, they would time out.
    barrier = threading.Barrier(2, timeout=5)
    dense = FixedRetriever([A], "dense", barrier)
    keyword = FixedRetriever([B], "keyword", barrier)
    assert _ids(_hybrid(dense, keyword).search("q", DEFAULT_SCOPE, 10)) == [A, B]


def test_a_keyword_failure_falls_back_to_the_dense_hits(caplog):
    dense = FixedRetriever([A, B, C], "dense")
    with caplog.at_level(logging.WARNING):
        result = _hybrid(dense, BrokenRetriever()).search("q", DEFAULT_SCOPE, 2)
    assert result.mode == "dense_fallback"
    assert result.hits == [RetrievalHit(A, 0.9), RetrievalHit(B, 0.89)]
    assert "keyword search failed" in caplog.text.lower()


def test_a_dense_failure_raises():
    with pytest.raises(ConnectionError):
        _hybrid(BrokenRetriever(), FixedRetriever([A], "keyword")).search("q", DEFAULT_SCOPE, 10)


@pytest.mark.parametrize("found", [[], [A]], ids=["none", "one"])
def test_zero_or_one_candidates_come_back_as_found(found):
    result = _hybrid(FixedRetriever(found, "dense"), FixedRetriever([], "keyword")).search(
        "q", DEFAULT_SCOPE, 10
    )
    assert (result.mode, _ids(result)) == ("hybrid", found)


def test_a_keyword_hit_from_a_version_no_longer_current_is_dropped(
    session, settings, seed_chunk, supersede, keyword_index
):
    chunk = seed_chunk("rollout notes for the canary")
    supersede(chunk)
    # Still in OpenSearch: only the PostgreSQL recheck can drop it.
    assert [hit[0] for hit in keyword_index.search("rollout", DEFAULT_SCOPE, 10)] == [chunk.id]
    hybrid = _hybrid(FixedRetriever([], "dense"), KeywordRetriever(keyword_index))
    outcome = retrieve_passages(session, "rollout notes", DEFAULT_SCOPE, hybrid, settings)
    assert (outcome.mode, outcome.passages) == ("hybrid", [])


def test_a_keyword_only_hit_reaches_the_passages(session, settings, seed_chunk, keyword_index):
    chunk = seed_chunk("rollout notes for the canary")
    hybrid = _hybrid(FixedRetriever([], "dense"), KeywordRetriever(keyword_index))
    outcome = retrieve_passages(session, "rollout notes", DEFAULT_SCOPE, hybrid, settings)
    assert [passage.chunk_id for passage in outcome.passages] == [chunk.id]


def test_keyword_retriever_reports_keyword_mode(seed_chunk, keyword_index):
    chunk = seed_chunk("rollout notes for the canary")
    result = KeywordRetriever(keyword_index).search("canary", DEFAULT_SCOPE, 10)
    assert (result.mode, _ids(result)) == ("keyword", [chunk.id])


@pytest.mark.parametrize(("mode", "kind"), [("hybrid", HybridRetriever), ("dense", DenseRetriever)])
def test_build_services_picks_the_retriever_for_the_mode(settings, mode, kind):
    services = build_services(settings.model_copy(update={"retrieval_mode": mode}))
    assert isinstance(services.retriever, kind)
