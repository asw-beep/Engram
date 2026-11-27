import json

import pytest

from eval.dataset import Gold, Question
from eval.report import render
from eval.run import run_questions, summarise
from tests.tenants import DEFAULT_SCOPE


def _q(qid, kind, split, *gold):
    return Question(qid, f"question {qid}", kind, tuple(gold), split)


def _row(qid, top, *ranked, latency=10):
    return {
        "id": qid,
        "ranked": [{"path": p, "headings": list(h), "score": top} for p, h in ranked],
        "top_score": top,
        "latency_ms": latency,
        "outside": [],
    }


QUESTIONS = [
    _q("k-1", "conceptual", "test", Gold("a.md", ("A",))),
    _q("k-2", "exact_term", "test", Gold("b.md", ("B",))),
    _q("k-3", "unanswerable", "test"),
    _q("k-4", "conceptual", "dev", Gold("a.md", ("A",))),
]
PER_QUESTION = [
    _row("k-1", 0.9, ("a.md", ("A",)), latency=10),
    _row("k-2", 0.3, ("x.md", ()), latency=30),
    _row("k-3", 0.2, ("x.md", ()), latency=20),
    _row("k-4", 0.95, ("a.md", ("A",)), latency=999),
]


def test_summary_counts_only_the_test_split():
    summary = summarise(PER_QUESTION, QUESTIONS, cutoff=0.5)
    assert (summary["answerable"], summary["unanswerable"]) == (2, 1)
    assert summary["overall"]["recall@5"] == pytest.approx(0.5)
    assert summary["overall"]["mrr@10"] == pytest.approx(0.5)
    assert summary["latency_ms"] == {"median": 20, "p95": 30}


def test_summary_breaks_metrics_down_by_kind():
    by_kind = summarise(PER_QUESTION, QUESTIONS, cutoff=0.5)["by_kind"]
    assert by_kind["conceptual"]["recall@5"] == 1.0 and by_kind["conceptual"]["count"] == 1
    assert by_kind["exact_term"]["recall@5"] == 0.0
    assert "unanswerable" not in by_kind


def test_summary_reports_the_evidence_gate_at_the_cutoff():
    gate = summarise(PER_QUESTION, QUESTIONS, cutoff=0.5)["evidence_gate"]
    assert gate == {
        "cutoff": 0.5,
        "answerable_passed": 0.5,
        "unanswerable_refused": 1.0,
        "balanced_accuracy": 0.75,
    }


def test_a_question_with_no_passages_is_refused_by_the_gate():
    per_question = [_row("k-1", None), _row("k-3", None)]
    gate = summarise(per_question, QUESTIONS[:1] + QUESTIONS[2:3], cutoff=0.5)["evidence_gate"]
    assert (gate["answerable_passed"], gate["unanswerable_refused"]) == (0.0, 1.0)


def test_run_records_each_question_ranking(session, settings, seed_chunk, retriever):
    seed_chunk("question k-1 about pods", path="pods.md")
    rows = run_questions(
        session,
        [_q("k-1", "conceptual", "test", Gold("pods.md", ()))],
        DEFAULT_SCOPE,
        retriever,
        settings,
    )
    assert [r["id"] for r in rows] == ["k-1"]
    assert rows[0]["ranked"][0]["path"] == "pods.md" and rows[0]["top_score"] > 0
    assert rows[0]["latency_ms"] >= 0


def test_report_lists_missing_configurations_as_not_run(tmp_path):
    result = {
        "config": "dense",
        "corpus": {"documents": 3, "chunks": 9},
        "summary": summarise(PER_QUESTION, QUESTIONS, cutoff=0.5),
    }
    text = render({"dense": result}, QUESTIONS, reviewed=False)
    assert "| dense | 0.500 |" in text
    assert "| hybrid | not run |" in text and "| hybrid_rerank | not run |" in text
    assert "Provisional" in text
    json.dumps(result)  # result files must stay plain JSON


def _result(recall=0.5, corpus=None, settings=None, cutoff_from="configured"):
    summary = summarise(PER_QUESTION, QUESTIONS, cutoff=0.5)
    summary["overall"]["recall@5"] = recall
    return {
        "config": "dense",
        "corpus": corpus or {"documents": 3, "chunks": 9},
        "settings": settings or {},
        "cutoff_from": cutoff_from,
        "summary": summary,
    }


def test_a_target_is_not_called_met_before_the_owner_review():
    provisional = render({"dense": _result(recall=0.9)}, QUESTIONS, reviewed=False)
    reviewed = render({"dense": _result(recall=0.9)}, QUESTIONS, reviewed=True)
    assert "met (" not in provisional and "provisional (0.900)" in provisional
    assert "met (0.900)" in reviewed


def test_the_report_says_whether_the_cutoff_was_calibrated():
    configured = render({"dense": _result()}, QUESTIONS, reviewed=False)
    calibrated = render({"dense": _result(cutoff_from="calibrated on dev")}, QUESTIONS, False)
    assert "| dense | 0.500 | configured |" in configured
    assert "| dense | 0.500 | calibrated on dev |" in calibrated


def test_the_report_computes_the_exact_term_share_and_review_state():
    provisional = render({"dense": _result()}, QUESTIONS, reviewed=False)
    reviewed = render({"dense": _result()}, QUESTIONS, reviewed=True)
    assert "33% of the answerable questions use exact terms" in provisional
    assert "hasn't reviewed" in provisional and "The owner reviewed a sample" in reviewed
    assert "echoes a heading" in provisional and "page's introduction" in provisional


def test_the_report_names_the_recorded_device():
    text = render({"dense": _result(settings={"embedding_device": "cuda"})}, QUESTIONS, False)
    assert "| `cuda` |" in text
    assert "not recorded" in render({"dense": _result()}, QUESTIONS, reviewed=False)


def test_the_report_flags_runs_made_on_different_corpora():
    results = {
        "dense": _result(corpus={"documents": 3, "chunks": 9}),
        "hybrid": {**_result(corpus={"documents": 3, "chunks": 12}), "config": "hybrid"},
    }
    assert "different corpora" in render(results, QUESTIONS, reviewed=False)
    assert "different corpora" not in render({"dense": _result()}, QUESTIONS, reviewed=False)


def test_a_row_without_its_outside_set_is_rejected():
    stale = [{k: v for k, v in row.items() if k != "outside"} for row in PER_QUESTION]
    with pytest.raises(ValueError, match="k-1"):
        summarise(stale, QUESTIONS, cutoff=0.5)
