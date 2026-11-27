import json

import pytest

from eval.dataset import Gold, Question, load_questions


def _line(**fields):
    base = {
        "id": "k8s-001",
        "question": "What is a Pod?",
        "kind": "conceptual",
        "gold": [{"path": "pods.md", "headings": ["Pods"]}],
        "split": "dev",
    }
    base.update(fields)
    return json.dumps(base)


def _write(tmp_path, *lines):
    path = tmp_path / "questions.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_valid_lines_become_questions(tmp_path):
    path = _write(
        tmp_path,
        _line(),
        "",
        _line(id="k8s-002", kind="unanswerable", gold=[], split="test", question="Bread?"),
    )
    assert load_questions(path) == [
        Question("k8s-001", "What is a Pod?", "conceptual", (Gold("pods.md", ("Pods",)),), "dev"),
        Question("k8s-002", "Bread?", "unanswerable", (), "test"),
    ]


@pytest.mark.parametrize(
    ("bad_line", "reason"),
    [
        ("{not json", "JSON"),
        (_line(kind="vague"), "kind"),
        (_line(split="train"), "split"),
        (_line(gold=[]), "gold"),
        (_line(kind="unanswerable"), "gold"),
        (_line(kind="multi_section"), "two"),
        (_line(question="  "), "question"),
        (_line(gold=[{"path": "pods.md"}]), "headings"),
    ],
    ids=[
        "invalid-json",
        "unknown-kind",
        "unknown-split",
        "answerable-without-gold",
        "unanswerable-with-gold",
        "multi-section-with-one-gold",
        "blank-question",
        "gold-without-headings",
    ],
)
def test_a_defect_is_rejected_naming_its_line(tmp_path, bad_line, reason):
    path = _write(tmp_path, _line(id="k8s-000"), bad_line)
    with pytest.raises(ValueError, match=rf"line 2\b.*{reason}"):
        load_questions(path)


def test_a_repeated_id_is_rejected_naming_its_line(tmp_path):
    path = _write(tmp_path, _line(), _line(question="Again?"))
    with pytest.raises(ValueError, match=r"line 2\b.*k8s-001"):
        load_questions(path)
