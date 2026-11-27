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
# A heading ID such as "## Pod phase {#pod-phase}", used by Hugo and kramdown.
_HEADING_ANCHOR = re.compile(r"\s*\{#[\w.:-]+\}$")
# The same line breaks markdown-it normalises, so line numbers agree with its token maps.
_LINE_BREAK = re.compile(r"\r\n?|\n")
# A Hugo shortcode tag, {{< name args >}}, {{% name args %}} or a closing tag, which may run
# over several lines. The body never contains another "{{" or "}}", so a stray opening
# can't swallow the text up to some later tag.
_SHORTCODE = re.compile(
    r"\{\{<((?:(?!\{\{|\}\}).)*?)>\}\}|\{\{%((?:(?!\{\{|\}\}).)*?)%\}\}", re.DOTALL
)
_SHORTCODE_NAME = re.compile(r"\s*([\w-]+)")
_TEXT_ATTRIBUTE = re.compile(r"""\btext=(?:"([^"]*)"|'([^']*)')""")
_TERM_ATTRIBUTE = re.compile(r"""\bterm_id=(?:"([^"]*)"|'([^']*)')""")
_FIRST_ARGUMENT = re.compile(r"""^\s*[\w-]+\s+(?:"([^"]*)"|'([^']*)')""")
# The Kubernetes site's labels for {{% heading "..." %}}; others fall back to the argument.
_HEADING_LABELS = {
    "whatsnext": "What's next",
    "prerequisites": "Before you begin",
    "objectives": "Objectives",
    "cleanup": "Clean up",
    "seealso": "See also",
    "synopsis": "Synopsis",
    "options": "Options",
}
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


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

    lines = _strip_shortcodes(_blank_front_matter(_LINE_BREAK.split(text)))
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


def _strip_shortcodes(lines: list[str]) -> list[str]:
    """Replace Hugo shortcode tags outside code fences with the text they stand for.

    Each run of lines between fences is rewritten as one block, so a tag split over
    several lines is found too. A replacement keeps the newlines of the tag it replaces,
    so line numbers still refer to the original file. Shortcodes inside a fence are the
    content being shown, so they stay.
    """
    result: list[str] = []
    prose: list[str] = []
    fence = ""

    def flush() -> None:
        if prose:
            result.extend(_SHORTCODE.sub(_shortcode_text, "\n".join(prose)).split("\n"))
            prose.clear()

    for line in lines:
        marker = _FENCE.match(line)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                if not line.strip().lstrip(fence[0]):
                    fence = ""
            result.append(line)
        elif marker:
            flush()
            fence = marker.group(1)
            result.append(line)
        else:
            prose.append(line)
    flush()
    return result


def _shortcode_text(match: re.Match[str]) -> str:
    body = match.group(1) if match.group(1) is not None else match.group(2)
    return _shortcode_value(body) + "\n" * body.count("\n")


def _shortcode_value(body: str) -> str:
    """The text a tag stands for: its `text` attribute, a heading label, a glossary term."""
    text = _quoted(_TEXT_ATTRIBUTE.search(body))
    if text is not None:
        return text
    name = _SHORTCODE_NAME.match(body)
    if name is None:
        return ""
    if name.group(1) == "heading":
        argument = _quoted(_FIRST_ARGUMENT.match(body))
        if argument:
            label = argument.replace("-", " ").replace("_", " ").capitalize()
            return _HEADING_LABELS.get(argument, label)
    if name.group(1) == "glossary_tooltip":
        term = _quoted(_TERM_ATTRIBUTE.search(body))
        if term:
            return term.replace("-", " ").replace("_", " ")
    return ""


def _quoted(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


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
        stack.append((level, _HEADING_ANCHOR.sub("", _plain_text(tokens[index + 1]))))
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
