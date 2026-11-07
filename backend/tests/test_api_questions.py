from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models import QueryLog
from app.generation.base import LLMError, LLMQuotaExhausted

FIXTURES = Path(__file__).parent / "fixtures"


def ask(client, question="how do pods work"):
    return client.post("/api/questions", json={"question": question})


def test_answered_returns_citations_and_logs(client, fake_llm, seed_chunk, session):
    seed_chunk("how pods work in a cluster")
    fake_llm.returns("answered", "Pods work like this [1].")
    body = ask(client).json()
    assert body["outcome"] == "answered"
    assert body["citations"][0]["marker"] == 1
    log = session.get(QueryLog, UUID(body["id"]))
    assert log.outcome == "answered" and log.chunk_ids and log.latency_ms >= 0


def test_question_before_any_documents_is_insufficient_evidence(client, fake_llm):
    response = ask(client)
    assert response.status_code == 200
    assert response.json()["outcome"] == "insufficient_evidence"
    assert fake_llm.calls == []


def test_weak_evidence_skips_the_llm(client, fake_llm, seed_chunk):
    seed_chunk("completely unrelated bananas")
    assert ask(client, "kubernetes scheduling").json()["outcome"] == "insufficient_evidence"
    assert fake_llm.calls == []


def test_model_can_report_insufficient_evidence(client, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    fake_llm.returns("insufficient_evidence", "")
    body = ask(client).json()
    assert body["outcome"] == "insufficient_evidence" and body["answer"] is None


def test_invalid_marker_is_removed_but_valid_one_kept(client, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    fake_llm.returns("answered", "Yes [1] and [9].")
    body = ask(client).json()
    assert body["outcome"] == "answered" and "[9]" not in body["answer"]


def test_no_valid_marker_is_unverifiable(client, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    fake_llm.returns("answered", "Yes, no citation.")
    body = ask(client).json()
    assert body["outcome"] == "unverifiable" and body["answer"] is None


def test_quota_exhausted_returns_passages(client, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    fake_llm.raises(LLMQuotaExhausted("x"))
    body = ask(client).json()
    assert body["outcome"] == "quota_exhausted" and len(body["passages"]) == 1


def test_llm_failure_is_reported(client, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    fake_llm.raises(LLMError("x"))
    assert ask(client).json()["outcome"] == "llm_error"


def test_store_failure_returns_503_and_logs(client_with_broken_qdrant, session):
    assert ask(client_with_broken_qdrant).status_code == 503
    assert session.scalars(select(QueryLog.outcome)).one() == "retrieval_unavailable"


@pytest.mark.parametrize("question", ["   ", "x" * 2001])
def test_invalid_question_is_rejected(client, question):
    assert ask(client, question).status_code == 422


def test_injected_document_reaches_the_llm_only_as_a_passage(client, fake_llm, seed_chunk):
    seed_chunk((FIXTURES / "injection.md").read_text())
    fake_llm.returns("answered", "Answer [1].")
    ask(client, "ignore previous instructions")
    assert "Ignore all previous" not in fake_llm.calls[0].messages[0]["content"]
