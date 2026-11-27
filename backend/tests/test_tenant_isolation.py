from uuid import uuid4

import pytest

from app.retrieval.recheck import load_passages
from app.types import AccessScope, RetrievalHit
from tests.tenants import DEFAULT_SCOPE, TENANT_A, TENANT_B

pytestmark = pytest.mark.usefixtures("two_tenants")

SCOPE_B = AccessScope(TENANT_B, ("tenant",))


def test_tenant_b_search_finds_nothing_from_tenant_a(retriever, seed_chunk):
    seed_chunk("secret", tenant=TENANT_A)
    assert retriever.search("secret", SCOPE_B, 20).hits == []


def test_hybrid_search_for_tenant_b_finds_only_tenant_bs_chunks(hybrid_retriever, seed_chunk):
    seed_chunk("secret plans", tenant=TENANT_A)
    own = seed_chunk("secret plans", tenant=TENANT_B)
    result = hybrid_retriever.search("secret plans", SCOPE_B, 20)
    assert result.mode == "hybrid"
    assert [hit.chunk_id for hit in result.hits] == [own.id]


def test_recheck_drops_foreign_chunk_even_if_qdrant_returns_it(session, seed_chunk):
    chunk = seed_chunk("secret", tenant=TENANT_A)
    assert load_passages(session, [RetrievalHit(chunk.id, 0.99)], SCOPE_B) == []


def test_recheck_drops_chunk_without_matching_principal(session, seed_chunk):
    chunk = seed_chunk("x", principals=["team:a"])
    assert load_passages(session, [RetrievalHit(chunk.id, 0.9)], DEFAULT_SCOPE) == []


def test_recheck_drops_chunk_from_non_current_version(session, seed_chunk, supersede):
    chunk = seed_chunk("old")
    supersede(chunk)
    assert load_passages(session, [RetrievalHit(chunk.id, 0.9)], DEFAULT_SCOPE) == []


def test_recheck_ignores_missing_rows(session):
    assert load_passages(session, [RetrievalHit(uuid4(), 0.9)], DEFAULT_SCOPE) == []


def test_hybrid_search_needs_a_shared_principal(hybrid_retriever, seed_chunk):
    seed_chunk("restricted runbook", principals=["group:sre"])
    assert hybrid_retriever.search("restricted runbook", DEFAULT_SCOPE, 20).hits == []
    sre = AccessScope(DEFAULT_SCOPE.tenant_id, ("tenant", "group:sre"))
    assert len(hybrid_retriever.search("restricted runbook", sre, 20).hits) == 1
