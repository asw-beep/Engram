"""Word documents. "Heading N" paragraphs start sections, and tables stay in reading order."""

import re
from io import BytesIO

from docx import Document
from docx.table import Table

from app.ingestion.types import ParsedDocument, ParsedSection, ParseError

_HEADING_STYLE = re.compile(r"Heading (\d)$")


def parse_docx(content: bytes) -> ParsedDocument:
    try:
        document = Document(BytesIO(content))
        blocks = list(document.iter_inner_content())
    except Exception as error:  # python-docx raises zip, XML and package errors
        raise ParseError("could not read DOCX file") from error

    sections: list[ParsedSection] = []
    stack: list[tuple[int, str]] = []
    lines: list[str] = []

    def close_section() -> None:
        # A heading with no body after it makes no section, as in Markdown.
        body = lines[1:] if stack else lines
        if any(line.strip() for line in body):
            sections.append(
                ParsedSection(
                    heading_path=tuple(title for _, title in stack),
                    text="\n".join(lines).strip(),
                    start_line=None,
                    end_line=None,
                    page_start=None,
                    page_end=None,
                )
            )

    for block in blocks:
        if isinstance(block, Table):
            lines.append(_table_text(block))
            continue
        level = _heading_level(block)
        text = block.text.strip()
        if level is None or not text:
            lines.append(block.text)
            continue
        close_section()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))
        lines = [text]
    close_section()
    return ParsedDocument(sections)


def _heading_level(paragraph) -> int | None:
    style = paragraph.style.name if paragraph.style is not None else ""
    match = _HEADING_STYLE.match(style or "")
    return int(match.group(1)) if match else None


def _table_text(table: Table) -> str:
    """One line per row, with cells separated by tabs."""
    return "\n".join("\t".join(cell.text.strip() for cell in row.cells) for row in table.rows)
