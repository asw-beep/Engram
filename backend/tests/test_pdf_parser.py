import pytest

from app.ingestion.parsers.pdf import parse_pdf
from app.ingestion.types import ParseError
from tests.documents import blank_pdf, encrypted_pdf, pdf_of


def test_each_pdf_page_is_a_section_with_its_number():
    doc = parse_pdf(pdf_of("first page", "second page"))
    assert [(s.page_start, s.page_end) for s in doc.sections] == [(1, 1), (2, 2)]


def test_pdf_page_text_is_extracted_without_lines_or_headings():
    section = parse_pdf(pdf_of("first page")).sections[0]
    assert "first page" in section.text
    assert (section.heading_path, section.start_line, section.end_line) == ((), None, None)


def test_pdf_pages_without_text_are_skipped():
    doc = parse_pdf(pdf_of("first page", "", "third page"))
    assert [s.page_start for s in doc.sections] == [1, 3]


def test_pdf_without_text_is_rejected():
    with pytest.raises(ParseError, match="no extractable text"):
        parse_pdf(blank_pdf())


def test_corrupt_pdf_is_rejected():
    with pytest.raises(ParseError, match="could not read"):
        parse_pdf(b"not a pdf")


def test_encrypted_pdf_is_rejected():
    with pytest.raises(ParseError, match="encrypted"):
        parse_pdf(encrypted_pdf())


def test_pdf_with_only_an_owner_password_is_read():
    doc = parse_pdf(encrypted_pdf(user_password=""))
    assert "hidden text" in doc.sections[0].text
