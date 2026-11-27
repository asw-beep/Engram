"""Run retrieval for every evaluation question under one configuration and save the result.

    uv run python -m eval.run --config dense

The harness calls retrieve_passages, the function the API answers with, through the same
settings, so the numbers describe the code that answers questions (spec §3).
"""

import argparse
import json
import statistics
import sys
from collections.abc import Collection
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.retrieval.base import Retriever
from app.retrieval.pipeline import retrieve_passages
from app.services import build_services
from app.types import AccessScope
from eval.dataset import KINDS, Gold, Question, load_questions
from eval.metrics import Ranked, in_section, ndcg_at, percentile, recall_at, reciprocal_rank

# The settings each configuration overrides.
CONFIGS = {
    "dense": {"retrieval_mode": "dense", "rerank_enabled": False},
    "hybrid": {"retrieval_mode": "hybrid", "rerank_enabled": False},
    "hybrid_rerank": {"retrieval_mode": "hybrid", "rerank_enabled": True},
}
# What the code does when a setting doesn't exist yet. A configuration that needs anything
# else can't run on this build, rather than quietly running as something it isn't.
IMPLICIT = {"retrieval_mode": "dense", "rerank_enabled": False}
# Settings worth recording beside the numbers. Secrets and connection strings are left out.
RECORDED = (
    "retrieval_mode",
    "rerank_enabled",
    "candidate_limit",
    "rrf_k",
    "retrieval_limit",
    "max_passages",
    "max_context_tokens",
    "evidence_min_score",
    "dense_min_score",
    "rerank_min_score",
    "embedding_model_id",
    "embedding_device",
    "embedding_model_revision",
    "reranker_model_id",
    "reranker_model_revision",
    "qdrant_collection",
    "opensearch_index",
)
WARM_UP = "What is a Pod?"


def configure(settings: Settings, config: str) -> Settings:
    updates = {}
    for key, value in CONFIGS[config].items():
        if key in type(settings).model_fields:
            updates[key] = value
        elif IMPLICIT[key] != value:
            raise ValueError(f"configuration {config} needs the {key} setting, not built yet")
    return settings.model_copy(update=updates)


def run_questions(
    session: Session,
    questions: list[Question],
    scope: AccessScope,
    retriever: Retriever,
    settings: Settings,
) -> list[dict]:
    rows = []
    for question in questions:
        outcome = retrieve_passages(session, question.question, scope, retriever, settings)
        passages = outcome.passages
        rows.append(
            {
                "id": question.id,
                "ranked": [
                    {"path": p.document_path, "headings": list(p.heading_path), "score": p.score}
                    for p in passages
                ],
                # The cutoff keeps any passage at or above it, so the highest score decides.
                "top_score": max((p.score for p in passages), default=None),
                "latency_ms": outcome.retrieve_ms + outcome.rerank_ms,
                "mode": outcome.mode,
                "outside": sorted(_outside_gold(session, scope, question.gold)),
            }
        )
    return rows


def _outside_gold(session: Session, scope: AccessScope, gold: tuple[Gold, ...]) -> set[str]:
    """Gold documents with a current chunk outside every gold section, for NDCG's ideal."""
    if not gold:
        return set()
    rows = session.execute(
        select(Document.path, Chunk.heading_path)
        .join(Chunk, Chunk.document_version_id == Document.current_version_id)
        .where(Document.tenant_id == scope.tenant_id, Document.path.in_({g.path for g in gold}))
    ).all()
    return {
        path
        for path, headings in rows
        if not any(in_section(Ranked(path, tuple(headings)), g) for g in gold)
    }


def summarise(per_question: list[dict], questions: list[Question], cutoff: float) -> dict:
    """Metrics over the test split only. Dev questions are for tuning (spec §3)."""
    by_id = {q.id: q for q in questions}
    test = [(by_id[row["id"]], row) for row in per_question if by_id[row["id"]].split == "test"]
    answerable = [(q, row) for q, row in test if q.kind != "unanswerable"]
    unanswerable = [(q, row) for q, row in test if q.kind == "unanswerable"]
    latencies = [row["latency_ms"] for _, row in test]
    return {
        "split": "test",
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "overall": _ranking(answerable),
        "by_kind": {
            kind: _ranking([(q, row) for q, row in answerable if q.kind == kind])
            for kind in KINDS
            if any(q.kind == kind for q, _ in answerable)
        },
        "latency_ms": {
            "median": statistics.median(latencies) if latencies else None,
            "p95": percentile(latencies, 95) if latencies else None,
        },
        "evidence_gate": _gate(answerable, unanswerable, cutoff),
    }


def _ranking(pairs: list[tuple[Question, dict]]) -> dict | None:
    if not pairs:
        return None

    def mean(metric) -> float:
        return statistics.fmean(metric(q, _ranked(row), row) for q, row in pairs)

    return {
        "count": len(pairs),
        "recall@5": mean(lambda q, ranked, row: recall_at(5, ranked, q.gold)),
        "recall@10": mean(lambda q, ranked, row: recall_at(10, ranked, q.gold)),
        "mrr@10": mean(lambda q, ranked, row: reciprocal_rank(ranked, q.gold, 10)),
        "ndcg@10": mean(lambda q, ranked, row: ndcg_at(10, ranked, q.gold, _outside(row))),
    }


def _ranked(row: dict) -> list[Ranked]:
    return [Ranked(item["path"], tuple(item["headings"])) for item in row["ranked"]]


def _outside(row: dict) -> Collection[str]:
    # Without it NDCG would assume every gold document has more text, so a stale result
    # file must be regenerated rather than scored by a different rule.
    if "outside" not in row:
        raise ValueError(f"result row {row['id']} has no outside set; rerun eval.run")
    return set(row["outside"])


def _gate(answerable: list, unanswerable: list, cutoff: float) -> dict:
    def top(row: dict) -> float:
        return row["top_score"] if row["top_score"] is not None else float("-inf")

    passed = (
        sum(top(row) >= cutoff for _, row in answerable) / len(answerable) if answerable else None
    )
    refused = (
        sum(top(row) < cutoff for _, row in unanswerable) / len(unanswerable)
        if unanswerable
        else None
    )
    balanced = (passed + refused) / 2 if passed is not None and refused is not None else None
    return {
        "cutoff": cutoff,
        "answerable_passed": passed,
        "unanswerable_refused": refused,
        "balanced_accuracy": balanced,
    }


def corpus_counts(session: Session, scope: AccessScope) -> dict:
    """Current documents and their chunks for the tenant the questions are asked as."""
    documents = session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.tenant_id == scope.tenant_id, Document.current_version_id.is_not(None))
    )
    chunks = session.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Document.current_version_id == Chunk.document_version_id)
        .where(Document.tenant_id == scope.tenant_id)
    )
    return {"documents": documents, "chunks": chunks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.run", description="Run the evaluation questions through retrieval."
    )
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    try:
        settings = configure(get_settings(), args.config)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    services = build_services(settings)
    scope = get_current_tenant()
    with services.session_factory() as session:
        # Load the models and warm the connections before anything is timed.
        retrieve_passages(session, WARM_UP, scope, services.retriever, settings)
        per_question = run_questions(session, questions, scope, services.retriever, settings)
        corpus = corpus_counts(session, scope)

    cutoff = settings.evidence_min_score
    result = {
        "config": args.config,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions_file": args.questions.as_posix(),
        "settings": {
            key: getattr(settings, key) for key in RECORDED if key in type(settings).model_fields
        },
        "corpus": corpus,
        # Task 9 replaces this with a cutoff calibrated on the dev split.
        "cutoff_from": "configured",
        "per_question": per_question,
        "summary": summarise(per_question, questions, cutoff),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.config}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    overall = result["summary"]["overall"] or {}
    print(f"Wrote {path.as_posix()}: Recall@5 {overall.get('recall@5')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
