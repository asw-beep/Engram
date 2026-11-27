import json

import pytest

from eval.calibrate import best_cutoff, main
from eval.dataset import Gold, Question


def _q(qid, kind, split="dev"):
    gold = () if kind == "unanswerable" else (Gold("a.md", ("A",)),)
    return Question(qid, f"question {qid}", kind, gold, split)


def _rows(tops):
    return [{"id": qid, "top_score": top} for qid, top in tops.items()]


def _dataset(answerable, unanswerable, split="dev", prefix=""):
    questions, tops = [], {}
    for n, top in enumerate(answerable):
        questions.append(_q(f"{prefix}a{n}", "conceptual", split))
        tops[f"{prefix}a{n}"] = top
    for n, top in enumerate(unanswerable):
        questions.append(_q(f"{prefix}u{n}", "unanswerable", split))
        tops[f"{prefix}u{n}"] = top
    return questions, tops


def test_the_cutoff_maximises_balanced_accuracy_on_dev():
    questions, tops = _dataset([0.9, 0.8, 0.4], [0.3, 0.5])
    found = best_cutoff(_rows(tops), questions)
    # Between 0.5 and 0.8: two of three answerable pass and both unanswerable are refused.
    assert found["cutoff"] == pytest.approx(0.65)
    dev = found["dev"]
    assert (dev["answerable"], dev["unanswerable"]) == (3, 2)
    assert dev["answerable_passed"] == pytest.approx(2 / 3)
    assert dev["unanswerable_refused"] == 1.0
    assert dev["balanced_accuracy"] == pytest.approx((2 / 3 + 1) / 2)
    assert "dev" in found["rule"] and "balanced accuracy" in found["rule"]


def test_test_questions_never_move_the_cutoff():
    questions, tops = _dataset([0.9, 0.8, 0.4], [0.3, 0.5])
    more_questions, more_tops = _dataset([0.1], [0.99], split="test", prefix="t")
    found = best_cutoff(_rows(tops | more_tops), questions + more_questions)
    assert found["cutoff"] == pytest.approx(0.65)
    assert (found["dev"]["answerable"], found["dev"]["unanswerable"]) == (3, 2)


def test_a_question_without_passages_is_always_refused():
    questions, tops = _dataset([0.9, 0.7], [None, 0.2])
    found = best_cutoff(_rows(tops), questions)
    assert found["dev"]["unanswerable_refused"] == 1.0
    assert 0.2 < found["cutoff"] <= 0.7


def test_equally_good_cutoffs_go_to_the_higher_one():
    # Cutting at 0.25 or at 0.75 each gets one question of each kind wrong.
    questions, tops = _dataset([0.8, 0.2], [0.3, 0.7])
    assert best_cutoff(_rows(tops), questions)["cutoff"] == pytest.approx(0.75)


def test_the_cutoff_is_rounded_but_stays_between_its_neighbours():
    questions, tops = _dataset([0.1236], [0.1234])
    cutoff = best_cutoff(_rows(tops), questions)["cutoff"]
    assert 0.1234 < cutoff <= 0.1236
    assert len(f"{cutoff}".split(".")[1]) <= 4


def test_calibration_needs_both_kinds_on_dev():
    questions, tops = _dataset([0.9, 0.8], [])
    with pytest.raises(ValueError, match="unanswerable"):
        best_cutoff(_rows(tops), questions)


def test_main_prints_the_cutoff_and_records_it(tmp_path, capsys):
    questions, tops = _dataset([0.9, 0.8, 0.4], [0.3, 0.5])
    lines = [
        json.dumps(
            {
                "id": q.id,
                "question": q.question,
                "kind": q.kind,
                "gold": [{"path": g.path, "headings": list(g.headings)} for g in q.gold],
                "split": q.split,
            }
        )
        for q in questions
    ]
    questions_file = tmp_path / "questions.jsonl"
    questions_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = {
        "config": "hybrid_rerank",
        "created_at": "2026-11-27T00:00:00+00:00",
        "per_question": _rows(tops),
    }
    (tmp_path / "hybrid_rerank.json").write_text(json.dumps(result), encoding="utf-8")
    (tmp_path / "calibration.json").write_text(json.dumps({"other": {"cutoff": 0.1}}), "utf-8")

    args = ["--config", "hybrid_rerank", "--results", str(tmp_path)]
    assert main([*args, "--questions", str(questions_file)]) == 0

    assert "best_cutoff 0.65" in capsys.readouterr().out
    saved = json.loads((tmp_path / "calibration.json").read_text(encoding="utf-8"))
    assert saved["other"] == {"cutoff": 0.1}
    assert saved["hybrid_rerank"]["cutoff"] == pytest.approx(0.65)
    assert saved["hybrid_rerank"]["result_created_at"] == "2026-11-27T00:00:00+00:00"
