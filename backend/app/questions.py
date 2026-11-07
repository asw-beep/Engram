"""The question flow in spec section 6: search, recheck, evidence check, context, generate,
validate citations, then respond and log."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import QueryLog
from app.generation.base import (
    GenerationRequest,
    GenerationResult,
    LLMError,
    LLMProvider,
    LLMQuotaExhausted,
)
from app.generation.citations import Citation, build_citation, validate_citations
from app.generation.context import select_passages
from app.generation.prompts import build_messages
from app.retrieval.base import Retriever
from app.retrieval.recheck import load_passages
from app.types import AccessScope, Passage

logger = logging.getLogger(__name__)


class RetrievalUnavailable(Exception):
    """Qdrant or Postgres failed, so there is no evidence to answer from."""


@dataclass(frozen=True)
class QuestionResult:
    id: UUID
    outcome: str
    answer: str | None
    citations: list[Citation]
    passages: list[Citation]


def answer_question(
    session: Session,
    question: str,
    scope: AccessScope,
    retriever: Retriever,
    llm: LLMProvider,
    count_tokens: Callable[[str], int],
    settings: Settings,
) -> QuestionResult:
    started = time.perf_counter()

    def finish(
        outcome: str,
        context: list[Passage],
        answer: str | None = None,
        citations: list[Citation] | None = None,
        passages: list[Citation] | None = None,
        generation: GenerationResult | None = None,
    ) -> QuestionResult:
        entry = QueryLog(
            id=uuid4(),
            tenant_id=scope.tenant_id,
            question=question,
            # The model's own reply, kept even when the user isn't shown it.
            answer=generation.answer if generation else None,
            outcome=outcome,
            chunk_ids=[passage.chunk_id for passage in context],
            model=generation.model if generation else None,
            input_tokens=generation.input_tokens if generation else None,
            output_tokens=generation.output_tokens if generation else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        _write_log(session, entry)
        return QuestionResult(entry.id, outcome, answer, citations or [], passages or [])

    try:
        hits = retriever.search(question, scope, settings.retrieval_limit)
        found = load_passages(session, hits, scope)
    except Exception as error:
        logger.warning("Retrieval failed, so the question can't be answered", exc_info=True)
        _rollback(session)
        finish("retrieval_unavailable", [])
        raise RetrievalUnavailable from error

    strong = [passage for passage in found if passage.score >= settings.evidence_min_score]
    context = select_passages(
        strong, count_tokens, settings.max_passages, settings.max_context_tokens
    )
    if not context:
        return finish("insufficient_evidence", [])

    try:
        generation = llm.generate(GenerationRequest(build_messages(question, context)))
    except LLMQuotaExhausted:
        numbered = [build_citation(number, passage) for number, passage in enumerate(context, 1)]
        return finish("quota_exhausted", context, passages=numbered)
    except LLMError as error:
        logger.warning("No model could answer: %s", error)
        return finish("llm_error", context)

    if generation.status == "insufficient_evidence":
        return finish("insufficient_evidence", context, generation=generation)
    check = validate_citations(generation.answer, len(context))
    if not check.markers:
        return finish("unverifiable", context, generation=generation)
    citations = [build_citation(marker, context[marker - 1]) for marker in check.markers]
    return finish(
        "answered", context, answer=check.answer, citations=citations, generation=generation
    )


def _write_log(session: Session, entry: QueryLog) -> None:
    """Write the query log, or warn when Postgres is down, so the response still goes out."""
    try:
        session.add(entry)
        session.commit()
    except SQLAlchemyError:
        logger.warning("Could not write the query log", exc_info=True)
        _rollback(session)


def _rollback(session: Session) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        logger.warning("Rollback failed", exc_info=True)
