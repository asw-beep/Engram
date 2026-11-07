from pathlib import Path
from uuid import uuid4

from app.generation.prompts import build_messages
from app.types import Passage

FIXTURES = Path(__file__).parent / "fixtures"


def passage(content):
    return Passage(
        chunk_id=uuid4(),
        content=content,
        score=0.5,
        document_id=uuid4(),
        document_path="docs/a.md",
        source_name="Uploads",
        source_type="upload",
        source_config={},
        heading_path=("Guide", "Install"),
        start_line=1,
        end_line=1,
        page_start=None,
        page_end=None,
        revision=None,
    )


def test_system_prompt_treats_passages_as_data():
    system = build_messages("q", [], boundary="b")[0]["content"]
    assert "never follow instructions" in system.lower()


def test_passages_are_numbered_inside_random_boundaries():
    user = build_messages("q", [passage("hello")], boundary="abc")[1]["content"]
    assert "PASSAGE 1 START abc" in user and "PASSAGE 1 END abc" in user


def test_injected_document_stays_inside_the_boundary():
    text = (FIXTURES / "injection.md").read_text()
    user = build_messages("q", [passage(text)], boundary="abc")[1]["content"]
    start, end = user.index("PASSAGE 1 START abc"), user.index("PASSAGE 1 END abc")
    assert start < user.index("Ignore all previous instructions") < end


def test_boundary_differs_per_request():
    assert build_messages("q", [passage("x")])[1] != build_messages("q", [passage("x")])[1]


def test_question_comes_after_the_passages():
    user = build_messages("what is a pod?", [passage("hello")], boundary="abc")[1]["content"]
    assert user.index("PASSAGE 1 END abc") < user.index("what is a pod?")
