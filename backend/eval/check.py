"""Check every gold label against the ingested corpus.

    uv run python -m eval.check

Exits non-zero, naming each question, when a gold path has no current document or no
current chunk of it sits under the gold headings. Run it after writing questions and after
re-ingesting the corpus, before any evaluation run.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.config import get_settings
from app.db.base import build_session_factory
from app.db.models import Chunk, Document
from app.types import AccessScope
from eval.dataset import Question, load_questions
from eval.metrics import Ranked, in_section


def label_problems(session: Session, scope: AccessScope, questions: list[Question]) -> list[str]:
    """One line per gold entry that names nothing in the current corpus, in file order."""
    paths = {entry.path for question in questions for entry in question.gold}
    sections: dict[str, list[tuple[str, ...]]] = {}
    rows = session.execute(
        select(Document.path, Chunk.heading_path)
        .join(Chunk, Chunk.document_version_id == Document.current_version_id)
        .where(Document.tenant_id == scope.tenant_id, Document.path.in_(paths))
    ).all()
    for path, headings in rows:
        sections.setdefault(path, []).append(tuple(headings))

    problems = []
    for question in questions:
        for entry in question.gold:
            if entry.path not in sections:
                problems.append(f"{question.id}: no current document {entry.path}")
            elif not any(in_section(Ranked(entry.path, h), entry) for h in sections[entry.path]):
                under = " > ".join(entry.headings)
                problems.append(f"{question.id}: no chunk of {entry.path} under {under}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.check", description="Check gold labels against the corpus."
    )
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    session_factory = build_session_factory(get_settings().database_url)
    with session_factory() as session:
        problems = label_problems(session, get_current_tenant(), questions)
    for problem in problems:
        print(problem, file=sys.stderr)
    gold = sum(len(q.gold) for q in questions)
    print(f"{len(questions)} questions, {gold} gold entries, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
