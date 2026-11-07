"""Smoke test against the real services, using the questions in smoke_questions.jsonl.

--retrieval-only searches in-process and prints each question's top score, using no LLM
quota. The default mode asks the running API and prints outcome, citations and latency.
Every question asked through the API may use one of OpenRouter's 50 free daily requests.

Run from backend/:
    uv run python -m scripts.smoke --retrieval-only
    uv run python -m scripts.smoke --base-url http://127.0.0.1:8000
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

QUESTIONS = Path(__file__).with_name("smoke_questions.jsonl")
MIN_ANSWERED = 6


def load_questions() -> list[dict[str, str]]:
    lines = QUESTIONS.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def retrieval_only(questions: list[dict[str, str]]) -> int:
    # Imported here so the API mode doesn't need the model or the databases.
    from app.config import get_settings
    from app.db.constants import DEFAULT_TENANT_ID
    from app.retrieval.recheck import load_passages
    from app.services import build_services
    from app.types import AccessScope

    settings = get_settings()
    services = build_services(settings)
    scope = AccessScope(DEFAULT_TENANT_ID, ("tenant",))
    scores: dict[str, list[float]] = {"answered": [], "insufficient_evidence": []}
    print(f"{'top':>6}  {'expects':<22} {'top document':<24} question")
    with services.session_factory() as session:
        for item in questions:
            hits = services.retriever.search(item["question"], scope, settings.retrieval_limit)
            passages = load_passages(session, hits, scope)
            top = passages[0] if passages else None
            score = top.score if top else 0.0
            scores[item["expects"]].append(score)
            path = top.document_path if top else "-"
            print(f"{score:6.3f}  {item['expects']:<22} {path:<24} {item['question']}")

    lowest_answerable = min(scores["answered"])
    highest_unrelated = max(scores["insufficient_evidence"])
    print(f"\nlowest answerable top score: {lowest_answerable:.3f}")
    print(f"highest unrelated top score: {highest_unrelated:.3f}")
    if lowest_answerable > highest_unrelated:
        print(f"midpoint cutoff: {(lowest_answerable + highest_unrelated) / 2:.3f}")
    else:
        print("the ranges overlap, so no cutoff separates them")
    print(f"current evidence_min_score: {settings.evidence_min_score:.3f}")
    return 0


def via_api(questions: list[dict[str, str]], base_url: str) -> int:
    answered = unrelated_refused = 0
    print(f"{'seconds':>7}  {'outcome':<22} {'cites':>5}  question")
    with httpx.Client(base_url=base_url, timeout=180) as client:
        for item in questions:
            started = time.perf_counter()
            response = client.post("/api/questions", json={"question": item["question"]})
            seconds = time.perf_counter() - started
            body = response.json() if response.status_code == 200 else {}
            outcome = body.get("outcome", f"HTTP {response.status_code}")
            citations = len(body.get("citations", []))
            if item["expects"] == "answered" and outcome == "answered" and citations:
                answered += 1
            if item["expects"] == "insufficient_evidence" and outcome == "insufficient_evidence":
                unrelated_refused += 1
            print(f"{seconds:7.1f}  {outcome:<22} {citations:>5}  {item['question']}")

    expected_answers = sum(item["expects"] == "answered" for item in questions)
    expected_refusals = len(questions) - expected_answers
    print(f"\nanswered with citations: {answered} of {expected_answers}")
    print(f"unrelated questions refused: {unrelated_refused} of {expected_refusals}")
    passed = answered >= MIN_ANSWERED and unrelated_refused == expected_refusals
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    questions = load_questions()
    if args.retrieval_only:
        return retrieval_only(questions)
    return via_api(questions, args.base_url)


if __name__ == "__main__":
    sys.exit(main())
