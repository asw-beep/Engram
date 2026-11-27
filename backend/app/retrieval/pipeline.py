"""Retrieval for one question, shared by the API and the evaluation harness.

Both call this one function through the same settings, so a measured number describes the
code that answers questions.
"""

import time
from dataclasses import replace

from sqlalchemy.orm import Session

from app.config import Settings
from app.embedding.base import embedding_text
from app.retrieval.base import Retriever
from app.retrieval.recheck import load_passages
from app.retrieval.rerank import Reranker
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
    reranker: Reranker | None = None,
) -> RetrievalOutcome:
    """Search, recheck in PostgreSQL, then rerank when given a reranker (spec section 5).

    The recheck comes first, so the reranker only reads text the asker may see. A
    RerankError propagates: scores without reranking aren't comparable to its cutoff.
    """
    started = time.perf_counter()
    query = normalise_question(question)
    result = retriever.search(query, scope, settings.retrieval_limit)
    # Every hit, dense or keyword, is rechecked here against PostgreSQL: tenant, current
    # version and principals.
    passages = load_passages(session, result.hits, scope)
    retrieve_ms = round((time.perf_counter() - started) * 1000)
    if reranker is None:
        return RetrievalOutcome(passages, result.mode, False, retrieve_ms, 0)

    started = time.perf_counter()
    texts = [embedding_text(passage.heading_path, passage.content) for passage in passages]
    scores = reranker.score(query, texts) if passages else []
    rescored = [
        replace(passage, score=score) for passage, score in zip(passages, scores, strict=True)
    ]
    # A stable sort, so equal scores keep the retrieval order.
    rescored.sort(key=lambda passage: passage.score, reverse=True)
    rerank_ms = round((time.perf_counter() - started) * 1000)
    return RetrievalOutcome(rescored, result.mode, True, retrieve_ms, rerank_ms)
