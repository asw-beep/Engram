"""Retrieval for one question, shared by the API and the evaluation harness.

Both call this one function through the same settings, so a measured number describes the
code that answers questions.
"""

import time

from sqlalchemy.orm import Session

from app.config import Settings
from app.retrieval.base import Retriever
from app.retrieval.recheck import load_passages
from app.types import AccessScope, RetrievalOutcome


def normalise_question(question: str) -> str:
    """Trim the question and collapse its whitespace. Nothing else changes it (spec §5)."""
    return " ".join(question.split())


def retrieve_passages(
    session: Session,
    question: str,
    scope: AccessScope,
    retriever: Retriever,
    settings: Settings,
) -> RetrievalOutcome:
    started = time.perf_counter()
    hits = retriever.search(normalise_question(question), scope, settings.retrieval_limit)
    passages = load_passages(session, hits, scope)
    retrieve_ms = round((time.perf_counter() - started) * 1000)
    return RetrievalOutcome(passages, "dense", False, retrieve_ms, 0)
