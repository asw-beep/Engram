"""Load the evaluation questions from a JSON Lines file, one question per line.

Gold labels name a document path and the heading path of the section that answers the
question, not chunk IDs, so they survive re-chunking and re-ingestion.
"""

import json
from dataclasses import dataclass
from pathlib import Path

KINDS = ("conceptual", "exact_term", "multi_section", "unanswerable")
SPLITS = ("dev", "test")
FIELDS = {"id", "question", "kind", "gold", "split"}


@dataclass(frozen=True)
class Gold:
    path: str
    headings: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    kind: str
    gold: tuple[Gold, ...]
    split: str


def load_questions(path: Path) -> list[Question]:
    """Every question in the file, in order. A defect raises ValueError naming its line."""
    questions: list[Question] = []
    seen: set[str] = set()
    # split("\n"), not splitlines(): JSON strings may hold U+2028 and friends.
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        line = line.removesuffix("\r")
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"line {number}: invalid JSON: {error}") from error
        try:
            question = _question(record)
        except ValueError as error:
            raise ValueError(f"line {number}: {error}") from error
        if question.id in seen:
            raise ValueError(f"line {number}: repeated id {question.id!r}")
        seen.add(question.id)
        questions.append(question)
    return questions


def _question(record: object) -> Question:
    if not isinstance(record, dict):
        raise ValueError("expected a JSON object")
    unknown = sorted(set(record) - FIELDS)
    if unknown:
        raise ValueError(f"unknown field {', '.join(unknown)}")
    qid = _text(record, "id")
    text = _text(record, "question")
    kind = record.get("kind")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    split = record.get("split")
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    raw_gold = record.get("gold", [])
    if not isinstance(raw_gold, list):
        raise ValueError("gold must be a list")
    gold = tuple(_gold(entry) for entry in raw_gold)
    if kind == "unanswerable" and gold:
        raise ValueError("an unanswerable question must have no gold")
    if kind != "unanswerable" and not gold:
        raise ValueError("an answerable question needs gold")
    if kind == "multi_section" and len(gold) < 2:
        raise ValueError("a multi_section question needs at least two gold entries")
    _reject_overlap(gold)
    return Question(qid, text, kind, gold, split)


def _reject_overlap(gold: tuple[Gold, ...]) -> None:
    """Refuse gold entries where one section contains another, or a repeated entry.

    With no overlap, a chunk falls in at most one gold section, so every metric credits
    it the same way whatever order the entries are listed in.
    """
    for i, first in enumerate(gold):
        for second in gold[i + 1 :]:
            shorter = min(len(first.headings), len(second.headings))
            if first.path == second.path and first.headings[:shorter] == second.headings[:shorter]:
                raise ValueError(f"gold entries overlap in {first.path}")


def _text(record: dict, field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _gold(entry: object) -> Gold:
    if not isinstance(entry, dict):
        raise ValueError("each gold entry must be an object")
    path = entry.get("path")
    headings = entry.get("headings")
    if not isinstance(path, str) or not path:
        raise ValueError("gold path must be a non-empty string")
    if path.startswith("/"):
        raise ValueError("gold path must be relative, as documents store it")
    if not isinstance(headings, list) or not all(
        isinstance(h, str) and h.strip() for h in headings
    ):
        raise ValueError("gold headings must be a list of non-empty strings")
    return Gold(path, tuple(headings))
