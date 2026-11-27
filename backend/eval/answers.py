"""Ask a sample of test questions through the whole answer path, for a manual review.

    uv run python -m eval.answers

It asks every eighth answerable `test` question, at most 15, through `answer_question` with
the settings as configured (the final configuration: hybrid retrieval, reranking and the
calibrated cutoff), one model request each. It writes each answer, its citations and the
stage timings to eval/results/answer_review.json, with an empty `review` per citation for
the reviewer to fill: a `verdict` of `supports`, `partly` or `does not support` and a
one-line `reason`. Each answer's `issues` lists what those verdicts can miss: a statement no
cited passage states, or a claim with no marker. eval.report summarises the file. A file with any review filled in is
never overwritten.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.api.deps import get_current_tenant
from app.config import get_settings
from app.db.models import QueryLog
from app.questions import answer_question
from app.services import build_services
from eval.dataset import Question, load_questions

SAMPLE_EVERY = 8
SAMPLE_MAX = 15
RECORDED = (
    "retrieval_mode",
    "rerank_enabled",
    "rerank_min_score",
    "dense_min_score",
    "llm_model",
    "llm_fallback_model",
)


def sample(questions: list[Question]) -> list[Question]:
    answerable = [q for q in questions if q.split == "test" and q.kind != "unanswerable"]
    return answerable[::SAMPLE_EVERY][:SAMPLE_MAX]


def record(question: Question, result, log) -> dict:
    return {
        "id": question.id,
        # The query log row holds the passages sent to the model, in marker order.
        "query_log": str(result.id),
        "question": question.question,
        "kind": question.kind,
        "outcome": result.outcome,
        "answer": result.answer,
        "model": log.model,
        "citations": [
            {
                "marker": citation.marker,
                "path": citation.document_path,
                "headings": list(citation.heading_path),
                "review": {"verdict": "", "reason": ""},
            }
            for citation in result.citations
        ],
        # Statement-level problems the per-citation verdicts can miss, one line each.
        "issues": [],
        "timings_ms": {
            "retrieve": log.retrieve_ms,
            "rerank": log.rerank_ms,
            "generate": log.generate_ms,
            "total": log.latency_ms,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.answers", description="Ask a sample of test questions for review."
    )
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("eval/results/answer_review.json"))
    args = parser.parse_args(argv)

    if args.out.exists() and _reviewed(json.loads(args.out.read_text(encoding="utf-8"))):
        print(f"{args.out.as_posix()} is already reviewed; move it aside first", file=sys.stderr)
        return 1
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY isn't set in backend/.env", file=sys.stderr)
        return 2

    picked = sample(load_questions(args.questions))
    services = build_services(settings)
    scope = get_current_tenant()
    answers = []
    with services.session_factory() as session:
        for question in picked:
            result = answer_question(
                session,
                question.question,
                scope,
                services.retriever,
                services.llm,
                services.embedder.count_tokens,
                settings,
                services.reranker,
            )
            answers.append(record(question, result, session.get(QueryLog, result.id)))
            print(f"{question.id}: {result.outcome}")
            if result.outcome == "quota_exhausted":
                print("The model quota is exhausted; stopping.", file=sys.stderr)
                break

    review = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions_file": args.questions.as_posix(),
        "settings": {key: getattr(settings, key) for key in RECORDED},
        "reviewer": "",
        "sampled": [q.id for q in picked],
        "answers": answers,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out.as_posix()}: {len(answers)} of {len(picked)} questions asked")
    return 0


def _reviewed(review: dict) -> bool:
    return any(
        citation["review"].get("verdict")
        for answer in review.get("answers", [])
        for citation in answer.get("citations", [])
    )


if __name__ == "__main__":
    raise SystemExit(main())
