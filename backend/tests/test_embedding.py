import subprocess
import sys
from unittest.mock import Mock

import pytest

from app.embedding.base import EmbeddingOutOfMemory, embedding_text
from app.embedding.batching import embed_in_batches
from app.retrying import retry_transient


class OomAbove:
    """Runs out of memory whenever a batch is larger than `limit`."""

    def __init__(self, limit):
        self.limit = limit
        self.batch_sizes = []

    def embed_passages(self, texts, batch_size):
        self.batch_sizes.append(batch_size)
        if batch_size > self.limit:
            raise EmbeddingOutOfMemory(f"batch of {batch_size}")
        return [[0.0] for _ in texts]


def test_embedding_text_starts_with_heading_path():
    assert embedding_text(("A", "B"), "body") == "A > B\n\nbody"
    assert embedding_text((), "body") == "body"


def test_batch_size_halves_on_out_of_memory():
    embedder = OomAbove(limit=2)
    assert len(embed_in_batches(embedder, ["a"] * 5, 8)) == 5
    assert embedder.batch_sizes == [8, 4, 2, 2, 2]  # attempted batch_size values


def test_out_of_memory_at_batch_size_one_is_raised():
    with pytest.raises(EmbeddingOutOfMemory):
        embed_in_batches(OomAbove(limit=0), ["a"], 8)


def test_importing_bge_m3_does_not_load_the_model():
    code = "import sys, app.embedding.bge_m3; sys.exit('sentence_transformers' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_retry_transient_stops_after_three_retries():
    fn = Mock(side_effect=ConnectionError())
    with pytest.raises(ConnectionError):
        retry_transient(fn, lambda e: True, wait_base=0)
    assert fn.call_count == 4


def test_retry_transient_does_not_retry_other_errors():
    fn = Mock(side_effect=ValueError())
    with pytest.raises(ValueError):
        retry_transient(fn, lambda e: isinstance(e, ConnectionError), wait_base=0)
    assert fn.call_count == 1
