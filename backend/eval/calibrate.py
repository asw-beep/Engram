"""Choose the evidence cutoff on the dev split (spec §5) from a result file eval.run wrote.

    uv run python -m eval.calibrate --config hybrid_rerank

It prints the cutoff and records it, with the rule and its accuracy on dev, in
eval/results/calibration.json, which eval.run and eval.report read. Test questions never
move it: their numbers are reported, not tuned on (spec §3).
"""

import argparse
import json
import sys
from pathlib import Path

from eval.dataset import Question, load_questions
from eval.run import CONFIGS, evidence_gate

RULE = (
    "the threshold, midway between two adjacent `dev` top scores, that maximises balanced "
    "accuracy between answerable and unanswerable `dev` questions, each judged by its highest "
    "passage score; a tie goes to the higher threshold"
)


def best_cutoff(per_question: list[dict], questions: list[Question]) -> dict:
    by_id = {q.id: q for q in questions}
    dev = [(by_id[row["id"]], row) for row in per_question if by_id[row["id"]].split == "dev"]
    answerable = [(q, row) for q, row in dev if q.kind != "unanswerable"]
    unanswerable = [(q, row) for q, row in dev if q.kind == "unanswerable"]
    if not answerable or not unanswerable:
        raise ValueError(
            "calibration needs answerable and unanswerable dev questions "
            f"({len(answerable)} answerable, {len(unanswerable)} unanswerable)"
        )
    scores = sorted({row["top_score"] for _, row in dev if row["top_score"] is not None})
    if len(scores) < 2:
        raise ValueError("calibration needs at least two different dev top scores")

    best: tuple[float, float, float] | None = None  # balanced accuracy, low, high
    for low, high in zip(scores, scores[1:], strict=False):
        accuracy = evidence_gate(answerable, unanswerable, high)["balanced_accuracy"]
        # >= so that a later, higher threshold wins a tie.
        if best is None or accuracy >= best[0]:
            best = (accuracy, low, high)
    _, low, high = best
    cutoff = _between(low, high)
    return {
        "cutoff": cutoff,
        "rule": RULE,
        "dev": {
            "answerable": len(answerable),
            "unanswerable": len(unanswerable),
            **{
                key: value
                for key, value in evidence_gate(answerable, unanswerable, cutoff).items()
                if key != "cutoff"
            },
        },
    }


def _between(low: float, high: float) -> float:
    """The midpoint, rounded as far as it can be while low stays refused and high passes."""
    middle = (low + high) / 2
    for digits in range(2, 10):
        rounded = round(middle, digits)
        if low < rounded <= high:
            return rounded
    return middle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.calibrate", description="Choose the evidence cutoff on dev."
    )
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--results", type=Path, default=Path("eval/results"))
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    args = parser.parse_args(argv)

    result = json.loads((args.results / f"{args.config}.json").read_text(encoding="utf-8"))
    try:
        found = best_cutoff(result["per_question"], load_questions(args.questions))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    found["result_created_at"] = result.get("created_at")

    path = args.results / "calibration.json"
    calibration = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    calibration[args.config] = found
    path.write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")
    dev = found["dev"]
    print(
        f"best_cutoff {found['cutoff']} (balanced accuracy on dev "
        f"{dev['balanced_accuracy']:.3f}: answerable passed {dev['answerable_passed']:.3f}, "
        f"unanswerable refused {dev['unanswerable_refused']:.3f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
