import json

import pytest

from eval.dataset import Gold, Question
from eval.report import render
from eval.run import (
    CONFIGS,
    configure,
    cutoff_source,
    gate_cutoff,
    require_mode,
    run_questions,
    summarise,
)
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


def test_unreranked_hybrid_scores_get_no_evidence_gate():
    assert summarise(PER_QUESTION, QUESTIONS, cutoff=None)["evidence_gate"] is None


@pytest.mark.parametrize(
    ("config", "cutoff"),
    [
        ("dense", "dense_min_score"),
        ("hybrid", None),
        ("dense_rerank", "rerank_min_score"),
        ("hybrid_rerank", "rerank_min_score"),
    ],
)
def test_each_configuration_is_gated_at_its_own_cutoff(settings, config, cutoff):
    settings = settings.model_copy(update={"dense_min_score": 0.4, "rerank_min_score": 0.7})
    expected = None if cutoff is None else getattr(settings, cutoff)
    assert gate_cutoff(configure(settings, config)) == expected


def test_the_configurations_cover_both_retrievers_with_and_without_reranking():
    assert {(c["retrieval_mode"], c["rerank_enabled"]) for c in CONFIGS.values()} == {
        ("dense", False),
        ("hybrid", False),
        ("dense", True),
        ("hybrid", True),
    }


def test_a_cutoff_is_called_calibrated_only_when_it_is_the_calibrated_value():
    calibration = {"hybrid_rerank": {"cutoff": 0.62}}
    assert cutoff_source(0.62, "hybrid_rerank", calibration) == "calibrated on dev"
    assert cutoff_source(0.62, "dense_rerank", calibration) == (
        "calibrated on dev for hybrid_rerank"
    )
    assert cutoff_source(0.5, "hybrid_rerank", calibration) == "configured"
    assert cutoff_source(0.5, "dense", {}) == "configured"
    assert cutoff_source(None, "hybrid", calibration) == "not applicable"


def test_a_run_that_fell_back_to_dense_is_not_saved_as_hybrid():
    rows = [{"id": "k-1", "mode": "hybrid"}, {"id": "k-2", "mode": "dense_fallback"}]
    with pytest.raises(ValueError, match="k-2"):
        require_mode(rows, "hybrid")
    require_mode(rows[:1], "hybrid")


def test_the_report_marks_the_unreranked_hybrid_gate_not_applicable():
    hybrid = _result(cutoff_from="not applicable")
    hybrid["config"] = "hybrid"
    hybrid["summary"]["evidence_gate"] = None
    text = render({"dense": _result(), "hybrid": hybrid}, QUESTIONS, reviewed=False)
    assert "| hybrid | – | not applicable | – | – | – |" in text
    assert "RRF" in text


def test_the_report_states_the_calibration_rule_and_its_accuracy_on_dev_and_test():
    reranked = _result(cutoff_from="calibrated on dev")
    reranked["config"] = "hybrid_rerank"
    calibration = {
        "hybrid_rerank": {
            "cutoff": 0.5,
            "rule": "the midpoint that maximises balanced accuracy on dev",
            "dev": {
                "answerable": 49,
                "unanswerable": 8,
                "answerable_passed": 48 / 49,
                "unanswerable_refused": 7 / 8,
                "balanced_accuracy": (48 / 49 + 7 / 8) / 2,
            },
        }
    }
    text = render({"hybrid_rerank": reranked}, QUESTIONS, False, calibration=calibration)
    assert "the midpoint that maximises balanced accuracy on dev" in text
    assert "0.927 on `dev`" in text
    test_accuracy = reranked["summary"]["evidence_gate"]["balanced_accuracy"]
    assert f"{test_accuracy:.3f} on `test`" in text
    assert "| dense_rerank | not run |" in text


def test_the_report_names_both_cutoff_settings():
    text = render({"dense": _result()}, QUESTIONS, reviewed=False)
    assert "`dense_min_score`" in text and "`rerank_min_score`" in text
    assert "evidence_min_score" not in text


def _paired_result(config, rows, cutoff):
    return {
        "config": config,
        "cutoff_from": "configured",
        "per_question": rows,
        "summary": summarise(rows, QUESTIONS, cutoff=cutoff),
    }


def test_the_report_compares_configurations_question_by_question():
    # dense finds k-1, hybrid_rerank finds k-2. At 0.5, dense's gate is right on k-1 and
    # k-3; hybrid_rerank's is right on k-2 only.
    reranked_rows = [
        _row("k-1", 0.3, ("x.md", ())),
        _row("k-2", 0.9, ("b.md", ("B",))),
        _row("k-3", 0.9, ("x.md", ())),
        _row("k-4", 0.9, ("a.md", ("A",))),
    ]
    results = {
        "dense": _paired_result("dense", PER_QUESTION, 0.5),
        "hybrid": _paired_result("hybrid", PER_QUESTION, None),
        "hybrid_rerank": _paired_result("hybrid_rerank", reranked_rows, 0.5),
    }
    text = render(results, QUESTIONS, reviewed=False)
    assert "| `hybrid_rerank` vs `dense` | 1 | 1 | 1.000 | 1 | 2 | 1.000 |" in text
    assert "| `hybrid` vs `dense` | 0 | 0 | 1.000 | – | – | – |" in text
    assert "| `dense_rerank` vs `dense` | not run |" in text
    assert "McNemar" in text


def test_the_report_states_a_shared_calibration_rule_once():
    entry = {
        "cutoff": 0.5,
        "rule": "the midpoint that maximises balanced accuracy on dev",
        "dev": {
            "answerable": 49,
            "unanswerable": 8,
            "answerable_passed": 1.0,
            "unanswerable_refused": 1.0,
            "balanced_accuracy": 1.0,
        },
    }
    calibration = {"dense_rerank": entry, "hybrid_rerank": entry}
    text = render({"dense": _result()}, QUESTIONS, False, calibration=calibration)
    assert text.count("the midpoint that maximises balanced accuracy on dev") == 1
    assert "`dense_rerank`: 0.5" in text and "`hybrid_rerank`: 0.5" in text


def _answer(qid, answer, *verdicts, outcome="answered"):
    return {
        "id": qid,
        "question": f"question {qid}",
        "kind": "conceptual",
        "outcome": outcome,
        "answer": answer,
        "citations": [
            {
                "marker": n,
                "path": "a.md",
                "headings": ["A"],
                "review": {"verdict": v, "reason": "r"},
            }
            for n, v in enumerate(verdicts, 1)
        ],
    }


def test_the_report_shows_the_answer_review_as_a_manual_sample():
    review = {
        "reviewer": "the project's author",
        "rule": "a citation supports its sentence when the passage states it",
        "sampled": ["k-1", "k-2", "k-9"],
        "answers": [
            _answer("k-1", "Pods share a network [1] and storage [2].", "supports", "partly"),
            _answer("k-2", "As Passage 2 says, it restarts [1].", "does not support"),
        ],
    }
    review["settings"] = {"retrieval_mode": "hybrid", "rerank_enabled": True, "llm_model": "cfg"}
    for answer in review["answers"]:
        answer["model"] = "fallback-model"
    text = render({"dense": _result()}, QUESTIONS, False, answer_review=review)
    assert "## Answer review (manual sample)" in text
    # The models that answered, not the configured one, which may have fallen back.
    assert "`fallback-model`" in text and "`cfg`" not in text
    assert "| k-1 | answered | 2 | 1 | 1 | 0 | no |" in text
    assert "| k-2 | answered | 1 | 0 | 0 | 1 | yes |" in text
    assert "1 of 2 answers name a passage" in text
    assert "2 of 3 sampled questions were asked" in text
    assert "the project's author" in text
    assert "a citation supports its sentence when the passage states it" in text


def test_unreviewed_citations_are_reported_as_not_reviewed():
    review = {"reviewer": "", "sampled": ["k-1"], "answers": [_answer("k-1", "x [1].", "")]}
    text = render({"dense": _result()}, QUESTIONS, False, answer_review=review)
    assert "| k-1 | answered | 1 | not reviewed |" in text


def test_without_an_answer_review_the_report_says_none_was_made():
    text = render({"dense": _result()}, QUESTIONS, reviewed=False)
    assert "No answer review has been made" in text
