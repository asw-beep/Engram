from dataclasses import dataclass


class ParseError(Exception):
    """A file can't be turned into text. The message is shown to the user as the reason."""


@dataclass(frozen=True)
class SourceItem:
    path: str
    revision: str | None = None
    storage_key: str | None = None


@dataclass(frozen=True)
class FetchedFile:
    item: SourceItem
    content: bytes


@dataclass(frozen=True)
class ParsedSection:
    heading_path: tuple[str, ...]
    text: str
    start_line: int | None
    end_line: int | None
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class ParsedDocument:
    sections: list[ParsedSection]


@dataclass(frozen=True)
class ChunkDraft:
    position: int
    content: str
    heading_path: tuple[str, ...]
    start_line: int | None
    end_line: int | None
    page_start: int | None
    page_end: int | None
    token_count: int
