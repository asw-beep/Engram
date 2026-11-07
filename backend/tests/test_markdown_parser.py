import pytest

from app.ingestion.parsers import parse_file
from app.ingestion.types import ParseError


def test_heading_paths_follow_nesting():
    doc = parse_file("a.md", b"# A\nx\n## B\ny\n# C\nz\n")
    assert [s.heading_path for s in doc.sections] == [("A",), ("A", "B"), ("C",)]


def test_line_ranges_are_one_based_and_inclusive():
    section = parse_file("a.md", b"intro\n\n# A\nx\ny\n").sections[1]
    assert (section.start_line, section.end_line) == (3, 5)


def test_text_before_first_heading_has_empty_path():
    assert parse_file("a.md", b"intro\n# A\nx\n").sections[0].heading_path == ()


def test_hash_inside_code_fence_is_not_a_heading():
    doc = parse_file("a.md", b"# A\n```\n# not heading\n```\n")
    assert [s.heading_path for s in doc.sections] == [("A",)]


def test_front_matter_is_excluded_and_lines_stay_correct():
    doc = parse_file("a.md", b"---\ntitle: Overview\nweight: 20\n---\n# A\nx\n")
    assert [s.heading_path for s in doc.sections] == [("A",)]
    assert "weight" not in doc.sections[0].text
    assert doc.sections[0].start_line == 5


def test_uppercase_extension_is_supported():
    assert parse_file("NOTES.MD", b"# A\nx\n").sections


def test_invalid_utf8_raises_parse_error():
    with pytest.raises(ParseError, match="not valid UTF-8"):
        parse_file("a.md", b"\xff\xfe\x00bad")


def test_empty_file_raises_parse_error():
    with pytest.raises(ParseError, match="no text"):
        parse_file("a.md", b"  \n\n")


def test_unsupported_extension_raises_parse_error():
    with pytest.raises(ParseError, match="unsupported"):
        parse_file("a.txt", b"x")
