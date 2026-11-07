"""BGE-M3 dense embeddings through sentence-transformers, loaded on first use.

Importing this module loads nothing: torch, transformers and sentence-transformers are
imported only when the tokenizer or model is first needed.
"""

import logging
import os
import threading
from collections.abc import Callable
from typing import Any

from app.config import Settings
from app.embedding.base import EmbeddingOutOfMemory

logger = logging.getLogger(__name__)

MAX_SEQ_LENGTH = 1024


class BgeM3Embedder:
    def __init__(self, settings: Settings):
        self.model_id = settings.embedding_model_id
        self.model_revision = settings.embedding_model_revision
        self.dimension = settings.embedding_dimension
        self._device = settings.embedding_device
        self._model: Any = None
        self._tokenizer: Any = None
        # Uploads and questions run on different threads, and neither the fast tokenizer
        # nor the model is safe to share between threads, so calls take turns.
        self._lock = threading.RLock()

    def count_tokens(self, text: str) -> int:
        with self._lock:
            return len(self._get_tokenizer().encode(text, add_special_tokens=False))

    def embed_passages(self, texts: list[str], batch_size: int) -> list[list[float]]:
        import torch

        with self._lock:
            model = self._get_model()
            try:
                vectors = model.encode_document(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
            except torch.cuda.OutOfMemoryError as error:
                torch.cuda.empty_cache()
                raise EmbeddingOutOfMemory(f"out of memory at batch size {batch_size}") from error
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        with self._lock:
            vector = self._get_model().encode_query(
                text, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
            )
        return vector.tolist()

    def _get_tokenizer(self) -> Any:
        if self._tokenizer is None:
            self._tokenizer = self._from_cache_or_hub(self._load_tokenizer)
        return self._tokenizer

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._from_cache_or_hub(self._load_model)
        return self._model

    def _load_tokenizer(self, local_files_only: bool) -> Any:
        _disable_hub_conversion()
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(
            self.model_id, revision=self.model_revision, local_files_only=local_files_only
        )

    def _load_model(self, local_files_only: bool) -> Any:
        _disable_hub_conversion()
        import torch
        from sentence_transformers import SentenceTransformer

        on_gpu = self._device.startswith("cuda")
        model = SentenceTransformer(
            self.model_id,
            revision=self.model_revision,
            device=self._device,
            model_kwargs={"dtype": torch.float16} if on_gpu else {},
            local_files_only=local_files_only,
        )
        model.max_seq_length = MAX_SEQ_LENGTH
        return model

    def _from_cache_or_hub(self, load: Callable[[bool], Any]) -> Any:
        """Load from the local cache without contacting the Hub, downloading only if missing."""
        try:
            return load(True)
        except (OSError, ValueError):
            logger.info("Downloading %s at %s", self.model_id, self.model_revision)
            return load(False)


def _disable_hub_conversion() -> None:
    # The pinned revision has only pytorch_model.bin, and transformers would otherwise start
    # a background download of a 2.27 GB safetensors conversion on every load, never used.
    os.environ.setdefault("DISABLE_SAFETENSORS_CONVERSION", "1")
