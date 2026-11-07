from collections.abc import Callable
from pathlib import PurePosixPath

from app.ingestion.parsers.docx import parse_docx
from app.ingestion.parsers.markdown import parse_markdown
from app.ingestion.parsers.pdf import parse_pdf
from app.ingestion.types import ParsedDocument, ParseError

PARSERS: dict[str, Callable[[bytes], ParsedDocument]] = {
    ".md": parse_markdown,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
}
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(PARSERS)


def parse_file(path: str, content: bytes) -> ParsedDocument:
    extension = PurePosixPath(path).suffix.lower()
    parser = PARSERS.get(extension)
    if parser is None:
        raise ParseError(f"unsupported file type {extension or '(none)'}")
    document = parser(content)
    if not document.sections:
        raise ParseError("no text")
    return document
