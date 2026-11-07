"""Fakes for the slow or external parts: the embedding model, source connectors and the LLM."""

import hashlib
import math
import re

from app.generation.base import GenerationRequest, GenerationResult
from app.ingestion.connectors.base import ConnectorError, FileTooLarge
from app.ingestion.types import FetchedFile, SourceItem

_PUNCTUATION = re.compile(r"[^\w\s]")


class FakeEmbedder:
    """Bag-of-words vectors: each lower-cased word, without punctuation, hashes to one of
    1024 dimensions, and the vector is normalised. Shared words give high similarity."""

    model_id = "BAAI/bge-m3"
    model_revision = "5617a9f61b028005a4858fdac845db406aefb181"
    dimension = 1024

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed_passages(self, texts: list[str], batch_size: int) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in _PUNCTUATION.sub("", text.lower()).split():
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class FailingConnector:
    """Fails to list its items with a message meant for the user."""

    def __init__(self, message: str):
        self.message = message
        self.closed = False

    def list_items(self) -> list[SourceItem]:
        raise ConnectorError(self.message)

    def fetch(self, item: SourceItem) -> FetchedFile:
        raise AssertionError("fetch is never reached")

    def close(self) -> None:
        self.closed = True


class ExplodingConnector:
    """Lists one file, then fails with an error the pipeline doesn't expect."""

    def __init__(self):
        self.closed = False

    def list_items(self) -> list[SourceItem]:
        return [SourceItem(path="a.md")]

    def fetch(self, item: SourceItem) -> FetchedFile:
        raise RuntimeError("unexpected")

    def close(self) -> None:
        self.closed = True


class OversizedFileConnector:
    """Lists a file too large to fetch, then a good one."""

    def list_items(self) -> list[SourceItem]:
        return [SourceItem(path="big.md"), SourceItem(path="good.md")]

    def fetch(self, item: SourceItem) -> FetchedFile:
        if item.path == "big.md":
            raise FileTooLarge("file is over 25 MB")
        return FetchedFile(item, b"# A\nx\n")

    def close(self) -> None:
        pass


class FakeLLM:
    """Returns a set result or raises a set error, recording every request."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def returns(self, status, answer):
        self.result = GenerationResult(
            status=status, answer=answer, model="fake-model", input_tokens=10, output_tokens=5
        )
        self.error = None
        return self

    def raises(self, error):
        self.error = error
        return self

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("FakeLLM was called without a result or an error set")
        return self.result
