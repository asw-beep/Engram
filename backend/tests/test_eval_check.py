from eval.check import label_problems
from eval.dataset import Gold, Question
from tests.tenants import DEFAULT_SCOPE


def _question(qid, *gold):
    kind = "multi_section" if len(gold) > 1 else "conceptual"
    return Question(qid, f"question {qid}", kind, tuple(gold), "dev")


def _publish(session, make_document, make_version, make_chunk, path, *heading_paths):
    document = make_document(path=path)
    version = make_version(document)
    for position, headings in enumerate(heading_paths):
        make_chunk(version, position, heading_path=list(headings))
    document.current_version_id = version.id
    session.commit()
    return document


def test_labels_that_match_a_current_chunk_have_no_problems(
    session, make_document, make_version, make_chunk
):
    _publish(session, make_document, make_version, make_chunk, "pods.md", ("Pods", "Using Pods"))
    questions = [
        _question("k-1", Gold("pods.md", ("Pods",))),
        _question("k-2", Gold("pods.md", ("Pods", "Using Pods"))),
        _question("k-3", Gold("pods.md", ())),
    ]
    assert label_problems(session, DEFAULT_SCOPE, questions) == []


def test_a_missing_document_or_section_is_named_with_its_question(
    session, make_document, make_version, make_chunk
):
    _publish(session, make_document, make_version, make_chunk, "pods.md", ("Pods", "Using Pods"))
    questions = [
        _question("k-1", Gold("nodes.md", ("Nodes",))),
        _question("k-2", Gold("pods.md", ("Pods", "Pod phases"))),
        _question("k-3", Gold("pods.md", ("Using Pods",))),
    ]
    problems = label_problems(session, DEFAULT_SCOPE, questions)
    assert problems == [
        "k-1: no current document nodes.md",
        "k-2: no chunk of pods.md under Pods > Pod phases",
        "k-3: no chunk of pods.md under Using Pods",
    ]


def test_only_the_current_version_counts(session, make_document, make_version, make_chunk):
    document = _publish(session, make_document, make_version, make_chunk, "pods.md", ("Pods",))
    old = make_version(document)
    make_chunk(old, 0, heading_path=["Pods", "Removed section"])
    questions = [_question("k-1", Gold("pods.md", ("Pods", "Removed section")))]
    assert label_problems(session, DEFAULT_SCOPE, questions) == [
        "k-1: no chunk of pods.md under Pods > Removed section"
    ]
