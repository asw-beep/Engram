import pytest
import torch
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings
from app.db.models import QueryLog
from app.embedding.base import embedding_text
from app.questions import RetrievalUnavailable, answer_question
from app.retrieval.base import SearchResult
from app.retrieval.pipeline import retrieve_passages
from app.retrieval.rerank import BgeReranker, RerankError
from app.services import build_services
from app.types import RetrievalHit
from tests.fakes import FailingReranker, FakeEmbedder, FakeReranker
from tests.tenants import DEFAULT_SCOPE


class FixedRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query, scope, limit):
        return SearchResult(self.hits, "hybrid")


def _retrieve(session, settings, hits, reranker, question="how pods work"):
    return retrieve_passages(
        session, question, DEFAULT_SCOPE, FixedRetriever(hits), settings, reranker=reranker
    )


def test_reranked_passages_come_back_in_reranker_order_with_its_scores(
    session, settings, seed_chunk
):
    bananas = seed_chunk("bananas are yellow", path="a.md")
    pods = seed_chunk("how pods work in kubernetes", path="b.md")
    hits = [RetrievalHit(bananas.id, 0.9), RetrievalHit(pods.id, 0.8)]
    outcome = _retrieve(session, settings, hits, FakeReranker())
    assert [(p.document_path, p.score) for p in outcome.passages] == [("b.md", 1.0), ("a.md", 0.0)]
    assert outcome.reranked is True and outcome.rerank_ms >= 0


def test_the_reranker_reads_the_question_and_each_passage_with_its_headings(
    session, settings, seed_chunk
):
    chunk = seed_chunk("Pods restart on failure.")
    chunk.heading_path = ["Pods", "Restart policy"]
    session.commit()
    reranker = FakeReranker()
    _retrieve(session, settings, [RetrievalHit(chunk.id, 0.9)], reranker, "  how   pods\nrestart ")
    expected = embedding_text(("Pods", "Restart policy"), "Pods restart on failure.")
    assert reranker.calls == [("how pods restart", [expected])]


def test_equal_reranker_scores_keep_the_retrieval_order(session, settings, seed_chunk):
    first = seed_chunk("pods one", path="a.md")
    second = seed_chunk("pods two", path="b.md")
    hits = [RetrievalHit(first.id, 0.9), RetrievalHit(second.id, 0.8)]
    outcome = _retrieve(session, settings, hits, FakeReranker(), question="pods")
    assert [p.document_path for p in outcome.passages] == ["a.md", "b.md"]


@pytest.mark.parametrize("count", [0, 1])
def test_zero_or_one_passages_are_reranked(session, settings, seed_chunk, count):
    hits = [RetrievalHit(seed_chunk("how pods work").id, 0.9)][:count]
    outcome = _retrieve(session, settings, hits, FakeReranker())
    assert outcome.reranked is True
    assert [p.score for p in outcome.passages] == [1.0][:count]


def test_without_a_reranker_scores_are_left_alone(session, settings, seed_chunk):
    chunk = seed_chunk("bananas are yellow")
    outcome = _retrieve(session, settings, [RetrievalHit(chunk.id, 0.9)], None)
    assert outcome.reranked is False and outcome.rerank_ms == 0
    assert [p.score for p in outcome.passages] == [0.9]


def test_a_reranker_failure_propagates_from_retrieval(session, settings, seed_chunk):
    hits = [RetrievalHit(seed_chunk("how pods work").id, 0.9)]
    with pytest.raises(RerankError):
        _retrieve(session, settings, hits, FailingReranker())


def _ask(session, settings, fake_llm, hits, reranker):
    return answer_question(
        session,
        "how pods work",
        DEFAULT_SCOPE,
        FixedRetriever(hits),
        fake_llm,
        FakeEmbedder().count_tokens,
        settings,
        reranker=reranker,
    )


def test_a_reranker_failure_gives_retrieval_unavailable(session, settings, fake_llm, seed_chunk):
    hits = [RetrievalHit(seed_chunk("how pods work").id, 0.9)]
    with pytest.raises(RetrievalUnavailable):
        _ask(session, settings, fake_llm, hits, FailingReranker())
    assert session.scalars(select(QueryLog.outcome)).one() == "retrieval_unavailable"
    assert fake_llm.calls == []


@pytest.mark.parametrize(
    ("text", "retrieval_score", "reranked", "outcome"),
    [
        # Every question word (reranker score 1) despite a retrieval score below both cutoffs:
        # passing means the reranker's score was gated, not the retrieval score.
        ("how pods work", 0.2, True, "answered"),
        ("how pods work", 0.2, False, "insufficient_evidence"),
        # Two question words in three (reranker score 0.67) lies between the cutoffs, so it
        # is refused only if the reranker cutoff, not the dense one, is applied.
        ("pods work", 0.95, True, "insufficient_evidence"),
        # A dense score between the cutoffs passes only at the dense cutoff.
        ("pods work", 0.6, False, "answered"),
    ],
    ids=["reranked-passes", "dense-refuses", "reranked-refuses", "dense-passes"],
)
def test_the_cutoff_follows_whether_scores_were_reranked(
    session, settings, fake_llm, seed_chunk, text, retrieval_score, reranked, outcome
):
    settings = settings.model_copy(update={"dense_min_score": 0.3, "rerank_min_score": 0.9})
    hits = [RetrievalHit(seed_chunk(text).id, retrieval_score)]
    fake_llm.returns("answered", "Pods work [1].")
    result = _ask(session, settings, fake_llm, hits, FakeReranker() if reranked else None)
    assert result.outcome == outcome
    log = session.get(QueryLog, result.id)
    assert log.reranked is reranked
    assert (log.rerank_ms is not None) is reranked


def test_hybrid_retrieval_needs_the_reranker():
    with pytest.raises(ValidationError, match="rerank"):
        Settings(_env_file=None, retrieval_mode="hybrid", rerank_enabled=False)
    Settings(_env_file=None, retrieval_mode="dense", rerank_enabled=False)


def test_the_defaults_are_hybrid_with_reranking():
    settings = Settings(_env_file=None)
    assert (settings.retrieval_mode, settings.rerank_enabled) == ("hybrid", True)


@pytest.mark.parametrize("enabled", [True, False])
def test_build_services_makes_a_reranker_only_when_enabled(settings, enabled):
    update = {"rerank_enabled": enabled, "retrieval_mode": "hybrid" if enabled else "dense"}
    services = build_services(settings.model_copy(update=update))
    assert isinstance(services.reranker, BgeReranker) is enabled
    assert (services.reranker is None) is (not enabled)


class OutOfMemoryAbove:
    """Stands in for the CrossEncoder: runs out of GPU memory above a batch size."""

    def __init__(self, largest):
        self.largest = largest
        self.batch_sizes = []

    def predict(self, pairs, batch_size, **kwargs):
        self.batch_sizes.append(batch_size)
        if batch_size > self.largest:
            raise torch.cuda.OutOfMemoryError("out of memory (test)")
        return torch.full((len(pairs),), 0.5).numpy()


def _reranker_with(settings, model):
    reranker = BgeReranker(settings.model_copy(update={"reranker_batch_size": 16}))
    reranker._model = model
    return reranker


def test_out_of_memory_halves_the_batch_until_it_fits(settings):
    model = OutOfMemoryAbove(largest=2)
    assert _reranker_with(settings, model).score("q", ["a", "b", "c"]) == [0.5, 0.5, 0.5]
    assert model.batch_sizes == [16, 8, 4, 2]


def test_out_of_memory_at_batch_size_one_is_a_rerank_error(settings):
    model = OutOfMemoryAbove(largest=0)
    with pytest.raises(RerankError):
        _reranker_with(settings, model).score("q", ["a"])
    assert model.batch_sizes == [16, 8, 4, 2, 1]


def test_no_passages_need_no_model(settings):
    reranker = BgeReranker(settings)
    assert reranker.score("q", []) == []
    assert reranker._model is None


def test_a_model_that_fails_to_load_is_a_rerank_error(settings, monkeypatch):
    reranker = BgeReranker(settings)

    def refuse(local_files_only):
        raise OSError("no model files (test)")

    monkeypatch.setattr(reranker, "_load_model", refuse)
    with pytest.raises(RerankError):
        reranker.score("q", ["a"])
