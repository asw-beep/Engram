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
from app.retrieval.pipeline import retrieve_passages
from app.retrieval.rerank import Reranker
from app.types import AccessScope, Passage, RetrievalOutcome

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
    reranker: Reranker | None = None,
) -> QuestionResult:
    started = time.perf_counter()
    retrieval: RetrievalOutcome | None = None
    generate_ms: int | None = None

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
            retrieval_mode=retrieval.mode if retrieval else None,
            reranked=retrieval.reranked if retrieval else None,
            retrieve_ms=retrieval.retrieve_ms if retrieval else None,
            rerank_ms=retrieval.rerank_ms if retrieval and retrieval.reranked else None,
            generate_ms=generate_ms,
        )
        _write_log(session, entry)
        return QuestionResult(entry.id, outcome, answer, citations or [], passages or [])

    try:
        retrieval = retrieve_passages(session, question, scope, retriever, settings, reranker)
    except Exception as error:
        logger.warning("Retrieval failed, so the question can't be answered", exc_info=True)
        _rollback(session)
        finish("retrieval_unavailable", [])
        raise RetrievalUnavailable from error

    # Reranker scores and dense similarities are on different scales, so each has its cutoff.
    cutoff = settings.rerank_min_score if retrieval.reranked else settings.dense_min_score
    strong = [passage for passage in retrieval.passages if passage.score >= cutoff]
    context = select_passages(
        strong, count_tokens, settings.max_passages, settings.max_context_tokens
    )
    if not context:
        return finish("insufficient_evidence", [])

    generate_started = time.perf_counter()
    try:
        generation = llm.generate(GenerationRequest(build_messages(question, context)))
    except LLMQuotaExhausted:
        generate_ms = _ms_since(generate_started)
        numbered = [build_citation(number, passage) for number, passage in enumerate(context, 1)]
        return finish("quota_exhausted", context, passages=numbered)
    except LLMError as error:
        generate_ms = _ms_since(generate_started)
        logger.warning("No model could answer: %s", error)
        return finish("llm_error", context)
    generate_ms = _ms_since(generate_started)

    if generation.status == "insufficient_evidence":
        return finish("insufficient_evidence", context, generation=generation)
    check = validate_citations(generation.answer, len(context))
    if not check.markers:
        return finish("unverifiable", context, generation=generation)
    citations = [build_citation(marker, context[marker - 1]) for marker in check.markers]
    return finish(
        "answered", context, answer=check.answer, citations=citations, generation=generation
    )


def _ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


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
