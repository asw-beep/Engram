from typing import Protocol


class EmbeddingOutOfMemory(Exception):
    """The device ran out of memory for this batch."""


class Embedder(Protocol):
    model_id: str
    model_revision: str
    dimension: int

    def embed_passages(self, texts: list[str], batch_size: int) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def count_tokens(self, text: str) -> int: ...


def embedding_text(heading_path: tuple[str, ...], content: str) -> str:
    """What gets embedded for a chunk: its heading path, then its text."""
    if not heading_path:
        return content
    return f"{' > '.join(heading_path)}\n\n{content}"
