import pytest
from sqlalchemy import select, text

from app.db.base import build_session_factory
from app.db.models import QueryLog
from app.generation.base import LLMQuotaExhausted
from app.questions import RetrievalUnavailable, answer_question
from tests.fakes import FakeEmbedder
from tests.tenants import DEFAULT_SCOPE

# Nothing listens on port 1. psycopg on Windows only gives up at the connect timeout.
DEAD_POSTGRES = "postgresql+psycopg://engram:engram@127.0.0.1:1/engram"


@pytest.fixture
def ask(session, retriever, fake_llm, settings):
    def run(question="how pods work", session=session):
        return answer_question(
            session,
            question,
            DEFAULT_SCOPE,
            retriever,
            fake_llm,
            FakeEmbedder().count_tokens,
            settings,
        )

    return run


def test_citations_follow_the_markers_the_answer_uses(ask, fake_llm, seed_chunk):
    seed_chunk("how pods work", path="a.md")
    seed_chunk("how pods work in a big cluster", path="b.md")
    fake_llm.returns("answered", "B [2]. A [1].")
    citations = ask().citations
    assert [(c.marker, c.document_path) for c in citations] == [(2, "b.md"), (1, "a.md")]


def test_passages_below_the_evidence_score_are_not_sent(ask, fake_llm, seed_chunk):
    seed_chunk("how pods work", path="a.md")
    seed_chunk("completely unrelated bananas", path="b.md")
    fake_llm.returns("answered", "Yes [1].")
    ask()
    assert "bananas" not in fake_llm.calls[0].messages[1]["content"]


def test_quota_exhausted_numbers_passages_in_rank_order(ask, fake_llm, seed_chunk):
    seed_chunk("how pods work", path="a.md")
    seed_chunk("how pods work in a big cluster", path="b.md")
    fake_llm.raises(LLMQuotaExhausted("x"))
    result = ask()
    assert [(p.marker, p.document_path) for p in result.passages] == [(1, "a.md"), (2, "b.md")]
    assert result.citations == [] and result.answer is None


def test_unshown_model_reply_is_kept_in_the_log(ask, fake_llm, seed_chunk, session):
    seed_chunk("how pods work")
    fake_llm.returns("answered", "Yes, no citation.")
    result = ask()
    assert result.answer is None
    log = session.get(QueryLog, result.id)
    assert (log.answer, log.model, log.input_tokens) == ("Yes, no citation.", "fake-model", 10)


def test_failed_recheck_is_still_logged(ask, seed_chunk, session, session_factory):
    seed_chunk("how pods work")
    session.commit()  # End this session's transaction, so nothing else holds a lock on chunks.
    with session_factory() as locker, session_factory() as asker:
        locker.execute(text("SET lock_timeout = '5s'"))
        locker.execute(text("LOCK TABLE chunks IN ACCESS EXCLUSIVE MODE"))
        asker.execute(text("SET lock_timeout = '100ms'"))
        with pytest.raises(RetrievalUnavailable):
            ask(session=asker)
        locker.rollback()
    assert session.scalars(select(QueryLog.outcome)).one() == "retrieval_unavailable"


def test_postgres_down_raises_retrieval_unavailable(ask, fake_llm, seed_chunk):
    seed_chunk("how pods work")
    dead_factory = build_session_factory(DEAD_POSTGRES, connect_timeout=2)
    with dead_factory() as dead, pytest.raises(RetrievalUnavailable):
        ask(session=dead)
    assert fake_llm.calls == []
