"""Split parsed sections into chunks of at most `max_tokens`.

A section that fits becomes one chunk. A longer one is packed from its paragraphs, and a
paragraph that is too long by itself is packed word by word. Each later piece of the same
section starts up to `overlap_tokens` earlier, at a word boundary. Pieces are character
ranges of the section text, so their line ranges come from counting newlines.
"""

import re
from collections.abc import Callable

from app.ingestion.types import ChunkDraft, ParsedDocument, ParsedSection

CountTokens = Callable[[str], int]
Span = tuple[int, int]

_WORD = re.compile(r"\S+")


def chunk_document(
    doc: ParsedDocument, count_tokens: CountTokens, max_tokens: int, overlap_tokens: int
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    for section in doc.sections:
        pieces = _section_pieces(section.text, count_tokens, max_tokens, overlap_tokens)
        for start, end in pieces:
            content = section.text[start:end]
            chunks.append(
                ChunkDraft(
                    position=len(chunks),
                    content=content,
                    heading_path=section.heading_path,
                    start_line=_line_at(section, start),
                    end_line=_line_at(section, end),
                    page_start=section.page_start,
                    page_end=section.page_end,
                    token_count=count_tokens(content),
                )
            )
    return chunks


def _section_pieces(
    text: str, count_tokens: CountTokens, max_tokens: int, overlap_tokens: int
) -> list[Span]:
    paragraphs = _paragraph_spans(text)
    if not paragraphs:
        return []
    whole = (paragraphs[0][0], paragraphs[-1][1])
    if count_tokens(text[whole[0] : whole[1]]) <= max_tokens:
        return [whole]

    units: list[Span] = []
    for start, end in paragraphs:
        if count_tokens(text[start:end]) <= max_tokens:
            units.append((start, end))
        else:
            units.extend((match.start(), match.end()) for match in _WORD.finditer(text, start, end))
    return _pack(text, units, count_tokens, max_tokens, overlap_tokens)


def _paragraph_spans(text: str) -> list[Span]:
    """Runs of non-blank lines, from the start of the first line to the end of the last."""
    spans: list[Span] = []
    start: int | None = None
    last_end = offset = 0
    for line in text.split("\n"):
        if line.strip():
            if start is None:
                start = offset
            last_end = offset + len(line)
        elif start is not None:
            spans.append((start, last_end))
            start = None
        offset += len(line) + 1
    if start is not None:
        spans.append((start, last_end))
    return spans


def _pack(
    text: str, units: list[Span], count_tokens: CountTokens, max_tokens: int, overlap_tokens: int
) -> list[Span]:
    pieces: list[Span] = []
    first = 0
    while first < len(units):
        unit_start = units[first][0]
        overlap = _overlap_start(text, pieces[-1], count_tokens, overlap_tokens) if pieces else None
        start = unit_start if overlap is None else overlap
        last = _last_fitting(text, start, units, first, count_tokens, max_tokens)
        if last < first and start != unit_start:
            start = unit_start
            last = _last_fitting(text, start, units, first, count_tokens, max_tokens)
        # A single word longer than the limit still has to go somewhere.
        last = max(last, first)
        pieces.append((start, units[last][1]))
        first = last + 1
    return pieces


def _last_fitting(
    text: str,
    start: int,
    units: list[Span],
    first: int,
    count_tokens: CountTokens,
    max_tokens: int,
) -> int:
    """The last unit index whose end keeps text[start:end] within the limit, or first - 1."""
    low, high, best = first, len(units) - 1, first - 1
    while low <= high:
        middle = (low + high) // 2
        if count_tokens(text[start : units[middle][1]]) <= max_tokens:
            best, low = middle, middle + 1
        else:
            high = middle - 1
    return best


def _overlap_start(
    text: str, piece: Span, count_tokens: CountTokens, overlap_tokens: int
) -> int | None:
    """The earliest word start in the piece whose tail fits in overlap_tokens, if any."""
    if overlap_tokens <= 0:
        return None
    starts = [match.start() for match in _WORD.finditer(text, piece[0], piece[1])]
    low, high, best = 0, len(starts) - 1, None
    while low <= high:
        middle = (low + high) // 2
        if count_tokens(text[starts[middle] : piece[1]]) <= overlap_tokens:
            best, high = starts[middle], middle - 1
        else:
            low = middle + 1
    return best


def _line_at(section: ParsedSection, offset: int) -> int | None:
    if section.start_line is None:
        return None
    return section.start_line + section.text.count("\n", 0, offset)
