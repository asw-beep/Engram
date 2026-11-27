from app.retrieval.pipeline import retrieve_passages
from app.types import RetrievalHit
from tests.tenants import DEFAULT_SCOPE, TENANT_B


class RecordingRetriever:
    """Returns fixed hits and remembers every search it was asked for."""

    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, scope, limit):
        self.calls.append((query, scope, limit))
        return self.hits


def test_question_whitespace_is_collapsed_before_searching(session, settings):
    retriever = RecordingRetriever([])
    retrieve_passages(session, "  how   pods\n\twork  ", DEFAULT_SCOPE, retriever, settings)
    assert retriever.calls == [("how pods work", DEFAULT_SCOPE, settings.retrieval_limit)]


def test_rechecked_passages_come_back_in_rank_order(session, settings, seed_chunk):
    first = seed_chunk("how pods work", path="a.md")
    second = seed_chunk("how pods work in a big cluster", path="b.md")
    foreign = seed_chunk("how pods work", tenant=TENANT_B, path="c.md")
    retriever = RecordingRetriever(
        [RetrievalHit(second.id, 0.9), RetrievalHit(foreign.id, 0.8), RetrievalHit(first.id, 0.7)]
    )
    outcome = retrieve_passages(session, "how pods work", DEFAULT_SCOPE, retriever, settings)
    assert [(p.document_path, p.score) for p in outcome.passages] == [("b.md", 0.9), ("a.md", 0.7)]
    assert (outcome.mode, outcome.reranked, outcome.rerank_ms) == ("dense", False, 0)
    assert outcome.retrieve_ms >= 0
