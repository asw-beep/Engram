import pytest

from app.retrieval.recheck import load_passages
from app.types import RetrievalHit
from tests.tenants import DEFAULT_SCOPE

pytestmark = pytest.mark.usefixtures("two_tenants")


def test_closest_chunk_ranks_first(retriever, seed_chunk):
    seed_chunk("kubernetes pods schedule containers")
    seed_chunk("bananas are yellow fruit")
    hits = retriever.search("how do pods schedule", DEFAULT_SCOPE, 20)
    assert hits[0].score > hits[1].score


def test_passages_keep_hit_order_and_metadata(session, seed_chunk):
    first, second = seed_chunk("one"), seed_chunk("two", path="b.md")
    hits = [RetrievalHit(second.id, 0.9), RetrievalHit(first.id, 0.8)]
    passages = load_passages(session, hits, DEFAULT_SCOPE)
    assert [p.document_path for p in passages] == ["b.md", "a.md"]
    top = passages[0]
    assert (top.chunk_id, top.content, top.score) == (second.id, "two", 0.9)
    assert (top.source_name, top.source_type, top.source_config) == ("Uploads", "upload", {})
