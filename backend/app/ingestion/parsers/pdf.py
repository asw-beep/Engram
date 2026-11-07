"""PDF text, one section per page that has text. Scanned pages have none and are skipped."""

import logging
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.types import ParsedDocument, ParsedSection, ParseError

logger = logging.getLogger(__name__)


def parse_pdf(content: bytes) -> ParsedDocument:
    try:
        reader = PdfReader(BytesIO(content))
    except (PdfReadError, ValueError, OSError) as error:
        raise ParseError("could not read PDF file") from error

    if reader.is_encrypted:
        # A PDF with only an owner password opens with an empty user password.
        try:
            opened = reader.decrypt("")
        except Exception as error:  # pypdf raises several types, e.g. for unsupported AES
            raise ParseError("PDF is encrypted") from error
        if not opened:
            raise ParseError("PDF is encrypted")

    sections = []
    try:
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                sections.append(
                    ParsedSection(
                        heading_path=(),
                        text=text,
                        start_line=None,
                        end_line=None,
                        page_start=number,
                        page_end=number,
                    )
                )
    except Exception as error:  # malformed content streams fail in many ways inside pypdf
        logger.warning("PDF text extraction failed", exc_info=True)
        raise ParseError("could not read PDF file") from error

    if not sections:
        raise ParseError("PDF has no extractable text, for example a scanned document")
    return ParsedDocument(sections)
