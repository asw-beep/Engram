from uuid import uuid4

from app.generation.context import select_passages
from app.types import Passage


def words(text):
    return len(text.split())


def passage(content, score=0.5):
    return Passage(
        chunk_id=uuid4(),
        content=content,
        score=score,
        document_id=uuid4(),
        document_path="a.md",
        source_name="Uploads",
        source_type="upload",
        source_config={},
        heading_path=(),
        start_line=1,
        end_line=1,
        page_start=None,
        page_end=None,
        revision=None,
    )


def test_select_removes_duplicate_content():
    picked = select_passages([passage("same"), passage("Same "), passage("other")], words, 8, 4000)
    assert [p.content for p in picked] == ["same", "other"]


def test_select_stops_at_eight_passages():
    assert len(select_passages([passage(f"p{i}") for i in range(20)], words, 8, 4000)) == 8


def test_select_respects_token_budget():
    picked = select_passages([passage("w " * 3000), passage("w " * 3000)], words, 8, 4000)
    assert len(picked) == 1


def test_select_keeps_rank_order_and_fills_the_budget_after_a_large_passage():
    first, large, small = passage("w " * 3000), passage("x " * 3000), passage("y")
    assert select_passages([first, large, small], words, 8, 4000) == [first, small]
