from uuid import uuid4

from app.generation.citations import build_citation, validate_citations
from app.types import Passage


def _passage(**fields):
    defaults = dict(
        chunk_id=uuid4(),
        content="text",
        score=0.5,
        document_id=uuid4(),
        document_path="a.md",
        source_name="Uploads",
        source_type="upload",
        source_config={},
        heading_path=(),
        start_line=None,
        end_line=None,
        page_start=None,
        page_end=None,
        revision=None,
    )
    return Passage(**{**defaults, **fields})


def github_passage(path, revision, lines):
    return _passage(
        document_path=path,
        source_name="o/r",
        source_type="github",
        source_config={"repository": "o/r", "branch": "main", "include_paths": []},
        start_line=lines[0],
        end_line=lines[1],
        revision=revision,
    )


def upload_passage(pages=(None, None), content="text"):
    return _passage(content=content, page_start=pages[0], page_end=pages[1])


def test_valid_markers_are_kept():
    assert validate_citations("A [1] and B [2].", 2).markers == [1, 2]


def test_invalid_markers_are_removed():
    check = validate_citations("A [1] and B [9].", 2)
    assert check.markers == [1] and "[9]" not in check.answer


def test_removed_marker_leaves_no_stray_space():
    assert validate_citations("A [1] and B [9].", 2).answer == "A [1] and B."


def test_marker_list_counts_as_separate_citations():
    check = validate_citations("A [1, 2].", 2)
    assert check.markers == [1, 2] and check.answer == "A [1] [2]."


def test_adjacent_markers_both_count():
    assert validate_citations("A [1][2].", 2).markers == [1, 2]


def test_repeated_marker_is_listed_once():
    assert validate_citations("A [2]. B [1]. C [2].", 2).markers == [2, 1]


def test_code_indexing_is_not_a_citation():
    check = validate_citations("Use items[1] here [2].", 2)
    assert check.markers == [2] and "items[1]" in check.answer


def test_github_citation_links_to_commit_and_lines():
    url = build_citation(
        1, github_passage(path="docs/my file.md", revision="abc", lines=(3, 9))
    ).url
    assert url == "https://github.com/o/r/blob/abc/docs/my%20file.md#L3-L9"


def test_upload_citation_has_no_url_and_keeps_pages():
    citation = build_citation(1, upload_passage(pages=(4, 4)))
    assert citation.url is None and citation.page_start == 4


def test_snippet_is_limited_to_240_characters():
    assert len(build_citation(1, upload_passage(content="x" * 500)).snippet) == 240
