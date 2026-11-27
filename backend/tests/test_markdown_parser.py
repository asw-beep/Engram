import pytest

from app.ingestion.parsers import parse_file
from app.ingestion.parsers.markdown import parse_markdown
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


def test_heading_anchor_is_left_out_of_the_title():
    doc = parse_file("a.md", b"# Pod phase {#pod-phase}\nx\n## `Waiting` {#waiting}\ny\n")
    assert [s.heading_path for s in doc.sections] == [("Pod phase",), ("Pod phase", "Waiting")]


def test_braces_inside_a_title_are_kept():
    doc = parse_file("a.md", b"# Using {name} in templates\nx\n")
    assert doc.sections[0].heading_path == ("Using {name} in templates",)


def test_shortcode_with_text_keeps_the_text():
    doc = parse_markdown(b'# T\n\nA {{< glossary_tooltip text="Pod" term_id="pod" >}} runs.\n')
    assert doc.sections[-1].text.endswith("A Pod runs.")


def test_shortcode_without_text_is_removed():
    doc = parse_markdown(b'# T\n\nVersion {{< param "version" >}} here.\n')
    assert "{{" not in doc.sections[-1].text


def test_paired_shortcode_keeps_inner_content():
    doc = parse_markdown(b"# T\n\n{{< note >}}\nKeep this.\n{{< /note >}}\n")
    assert "Keep this." in doc.sections[-1].text and "note" not in doc.sections[-1].text


def test_percent_shortcodes_are_removed():
    doc = parse_markdown(b"# T\n\n{{% alert %}}Careful{{% /alert %}}\n")
    assert doc.sections[-1].text.endswith("Careful")


def test_shortcode_in_a_code_fence_stays():
    doc = parse_markdown(b"# T\n\n```\n{{< note >}}\n```\n")
    assert "{{< note >}}" in doc.sections[-1].text


def test_shortcode_in_a_tilde_fence_stays():
    doc = parse_markdown(b"# T\n\n~~~yaml\n{{< note >}}\n~~~\n\n{{< note >}}after\n")
    text = doc.sections[-1].text
    assert "~~~yaml\n{{< note >}}\n~~~" in text and text.endswith("after")


def test_line_numbers_are_unchanged_by_shortcodes():
    doc = parse_markdown(b"# A\n\n{{< note >}}\nx\n{{< /note >}}\n\n# B\n\ny\n")
    assert (doc.sections[-1].start_line, doc.sections[-1].end_line) == (7, 9)


def test_shortcode_in_a_heading_keeps_its_text():
    doc = parse_markdown(b'# The {{< glossary_tooltip text="Pod" term_id="pod" >}} lifecycle\nx\n')
    assert doc.sections[0].heading_path == ("The Pod lifecycle",)
