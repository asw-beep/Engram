import pytest

from app.ingestion.parsers.docx import parse_docx
from app.ingestion.types import ParseError
from tests.documents import docx_of, docx_with_table


def test_docx_headings_build_paths():
    doc = parse_docx(
        docx_of(("Heading 1", "A"), ("Normal", "x"), ("Heading 2", "B"), ("Normal", "y"))
    )
    assert [s.heading_path for s in doc.sections] == [("A",), ("A", "B")]


def test_docx_section_text_starts_with_its_heading():
    doc = parse_docx(docx_of(("Heading 1", "Install"), ("Normal", "Run the installer.")))
    section = doc.sections[0]
    assert section.text == "Install\nRun the installer."
    assert (section.start_line, section.page_start) == (None, None)


def test_docx_without_headings_is_one_section():
    assert parse_docx(docx_of(("Normal", "x"), ("Normal", "y"))).sections[0].heading_path == ()


def test_docx_heading_without_body_makes_no_section():
    doc = parse_docx(docx_of(("Heading 1", "A"), ("Heading 2", "B"), ("Normal", "y")))
    assert [s.heading_path for s in doc.sections] == [("A", "B")]


def test_docx_table_text_is_kept_in_order():
    text = parse_docx(docx_with_table("cell value")).sections[0].text
    assert text.index("before the table") < text.index("cell value") < text.index("after")
    assert "name\tcell value" in text


def test_corrupt_docx_is_rejected():
    with pytest.raises(ParseError, match="could not read"):
        parse_docx(b"not a docx")


def test_docx_heading_of_the_same_level_replaces_the_last():
    doc = parse_docx(
        docx_of(("Heading 1", "A"), ("Normal", "x"), ("Heading 1", "C"), ("Normal", "y"))
    )
    assert [s.heading_path for s in doc.sections] == [("A",), ("C",)]
