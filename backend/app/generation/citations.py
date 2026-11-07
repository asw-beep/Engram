"""Structural citation checks: a marker must name a passage that was actually sent.

Phase 1 doesn't check that the passage supports the claim. Phase 2 measures that.
"""

import re
from dataclasses import dataclass
from urllib.parse import quote

from app.types import Passage

SNIPPET_LENGTH = 240

# A marker such as [1] or [1, 2], not preceded by a word character, so items[1] is code.
# Spaces before a marker are matched too, so removing an invalid marker leaves none behind.
_MARKER = re.compile(r"(?P<space>[ \t]*)(?<!\w)\[(?P<numbers>\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class CitationCheck:
    answer: str
    markers: list[int]


@dataclass(frozen=True)
class Citation:
    marker: int
    document_path: str
    source_name: str
    heading_path: tuple[str, ...]
    start_line: int | None
    end_line: int | None
    page_start: int | None
    page_end: int | None
    revision: str | None
    snippet: str
    url: str | None


def validate_citations(answer: str, passage_count: int) -> CitationCheck:
    """Drop markers that don't match a passage, and split lists like [1, 2] into [1] [2]."""
    markers: list[int] = []

    def replace(match: re.Match[str]) -> str:
        numbers = [int(n) for n in match["numbers"].split(",")]
        valid = [n for n in numbers if 1 <= n <= passage_count]
        markers.extend(n for n in valid if n not in markers)
        if not valid:
            return ""
        return match["space"] + " ".join(f"[{n}]" for n in valid)

    return CitationCheck(answer=_MARKER.sub(replace, answer).strip(), markers=markers)


def build_citation(marker: int, passage: Passage) -> Citation:
    return Citation(
        marker=marker,
        document_path=passage.document_path,
        source_name=passage.source_name,
        heading_path=passage.heading_path,
        start_line=passage.start_line,
        end_line=passage.end_line,
        page_start=passage.page_start,
        page_end=passage.page_end,
        revision=passage.revision,
        snippet=_snippet(passage.content),
        url=_github_url(passage),
    )


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= SNIPPET_LENGTH:
        return text
    return text[: SNIPPET_LENGTH - 1] + "…"


def _github_url(passage: Passage) -> str | None:
    """A link to the exact commit and lines. Only the backend builds links."""
    repository = passage.source_config.get("repository")
    if passage.source_type != "github" or not repository or not passage.revision:
        return None
    url = f"https://github.com/{repository}/blob/{passage.revision}/{quote(passage.document_path)}"
    if passage.start_line is not None:
        url += f"#L{passage.start_line}"
        if passage.end_line is not None and passage.end_line != passage.start_line:
            url += f"-L{passage.end_line}"
    return url
