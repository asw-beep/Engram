"""Small PDF and DOCX files built in memory for parser and upload tests."""

from io import BytesIO

from docx import Document
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas


def pdf_of(*pages: str) -> bytes:
    """One PDF page per string; an empty string makes a page with no text."""
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for text in pages:
        if text:
            canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def blank_pdf() -> bytes:
    return pdf_of("")


def encrypted_pdf(user_password: str = "secret", owner_password: str = "owner") -> bytes:
    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf_of("hidden text"))))
    writer.encrypt(user_password, owner_password, algorithm="RC4-128")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def sample_pdf() -> bytes:
    return pdf_of("Pods run one or more containers.")


def docx_of(*paragraphs: tuple[str, str]) -> bytes:
    """Paragraphs as (style, text) pairs, such as ("Heading 1", "Install")."""
    document = Document()
    for style, text in paragraphs:
        document.add_paragraph(text, style=style)
    return _save(document)


def docx_with_table(cell: str) -> bytes:
    document = Document()
    document.add_paragraph("before the table")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "name"
    table.cell(0, 1).text = cell
    document.add_paragraph("after the table")
    return _save(document)


def sample_docx() -> bytes:
    return docx_of(("Heading 1", "Pods"), ("Normal", "Pods run one or more containers."))


def _save(document) -> bytes:
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
