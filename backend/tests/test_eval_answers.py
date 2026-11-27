import json
from types import SimpleNamespace
from uuid import uuid4

from app.generation.citations import Citation
from eval.answers import main, record, sample
from eval.dataset import Gold, Question


def _q(qid, kind="conceptual", split="test"):
    gold = () if kind == "unanswerable" else (Gold("a.md", ("A",)),)
    return Question(qid, f"question {qid}", kind, gold, split)


def _citation(marker, path, headings):
    return Citation(marker, path, "Kubernetes", headings, 1, 2, None, None, "df4b759", "s", None)


def test_the_sample_is_every_eighth_answerable_test_question():
    questions = [_q(f"t{n}") for n in range(20)]
    questions[3:3] = [_q("dev", split="dev"), _q("none", kind="unanswerable")]
    assert [q.id for q in sample(questions)] == ["t0", "t8", "t16"]


def test_the_sample_holds_at_most_fifteen_questions():
    assert len(sample([_q(f"t{n}") for n in range(400)])) == 15


def test_a_record_has_the_answer_its_citations_and_the_stage_timings():
    result = SimpleNamespace(
        id=uuid4(),
        outcome="answered",
        answer="Pods share a network namespace [1].",
        citations=[_citation(1, "pods.md", ("Pods", "Networking"))],
    )
    log = SimpleNamespace(
        model="m", retrieve_ms=50, rerank_ms=800, generate_ms=3000, latency_ms=3900
    )
    assert record(_q("t0"), result, log) == {
        "id": "t0",
        "query_log": str(result.id),
        "question": "question t0",
        "kind": "conceptual",
        "outcome": "answered",
        "answer": "Pods share a network namespace [1].",
        "model": "m",
        "citations": [
            {
                "marker": 1,
                "path": "pods.md",
                "headings": ["Pods", "Networking"],
                "review": {"verdict": "", "reason": ""},
            }
        ],
        "timings_ms": {"retrieve": 50, "rerank": 800, "generate": 3000, "total": 3900},
    }


def test_a_review_in_progress_is_never_overwritten(tmp_path, capsys):
    out = tmp_path / "answer_review.json"
    reviewed = {
        "answers": [
            {"citations": [{"review": {"verdict": "supports", "reason": "says so"}}]},
        ]
    }
    out.write_text(json.dumps(reviewed), encoding="utf-8")
    assert main(["--out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8")) == reviewed
    assert "already reviewed" in capsys.readouterr().err
