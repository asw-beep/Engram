"""Split Markdown into one section per heading, with 1-based inclusive line ranges.

Headings come from markdown-it tokens, so a `#` inside a code fence is never a heading.
A section's text runs from its heading line to the line before the next heading.
"""

import re
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token

from app.ingestion.types import ParsedDocument, ParsedSection, ParseError

_MARKDOWN = MarkdownIt("commonmark")
# The same line breaks markdown-it normalises, so line numbers agree with its token maps.
_LINE_BREAK = re.compile(r"\r\n?|\n")


@dataclass(frozen=True)
class _Heading:
    path: tuple[str, ...]
    line: int
    body_start: int


def parse_markdown(content: bytes) -> ParsedDocument:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ParseError("not valid UTF-8") from error

    lines = _blank_front_matter(_LINE_BREAK.split(text))
    headings = _headings(lines)
    first_heading = headings[0].line if headings else len(lines)
    sections = [_section((), lines, 0, 0, first_heading)]
    for index, heading in enumerate(headings):
        end = headings[index + 1].line if index + 1 < len(headings) else len(lines)
        sections.append(_section(heading.path, lines, heading.line, heading.body_start, end))
    return ParsedDocument([section for section in sections if section is not None])


def _blank_front_matter(lines: list[str]) -> list[str]:
    """Blank a leading `---` block rather than removing it, so later line numbers hold."""
    if not lines or lines[0].rstrip() != "---":
        return lines
    for index in range(1, len(lines)):
        if lines[index].rstrip() in ("---", "..."):
            return [""] * (index + 1) + lines[index + 1 :]
    return lines


def _headings(lines: list[str]) -> list[_Heading]:
    tokens = _MARKDOWN.parse("\n".join(lines))
    stack: list[tuple[int, str]] = []
    headings = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.map is None:
            continue
        level = int(token.tag[1:])
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, _plain_text(tokens[index + 1])))
        headings.append(_Heading(tuple(title for _, title in stack), token.map[0], token.map[1]))
    return headings


def _plain_text(inline: Token) -> str:
    parts = [
        " " if child.type == "softbreak" else child.content
        for child in inline.children or []
        if child.type in ("text", "code_inline", "softbreak")
    ]
    return "".join(parts).strip() or inline.content.strip()


def _section(
    path: tuple[str, ...], lines: list[str], start: int, body_start: int, end: int
) -> ParsedSection | None:
    """Lines [start, end) as a section, or None when nothing follows the heading."""
    if not any(line.strip() for line in lines[body_start:end]):
        return None
    while not lines[start].strip():
        start += 1
    while not lines[end - 1].strip():
        end -= 1
    return ParsedSection(path, "\n".join(lines[start:end]), start + 1, end, None, None)
