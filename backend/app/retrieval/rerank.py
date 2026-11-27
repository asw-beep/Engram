"""Cross-encoder reranking (spec section 5): BGE-reranker-v2-m3 scores each question and
passage pair, and its score, from 0 to 1, replaces the passage's retrieval score.

Importing this module loads nothing: torch and sentence-transformers are imported only when
the model is first needed.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol

from app.config import Settings

logger = logging.getLogger(__name__)

# Tokens per question and passage pair. Longer passages are cut, as the model was trained.
MAX_LENGTH = 512


class RerankError(Exception):
    """The reranker couldn't load or score, so there are no comparable scores to gate on."""


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]:
        """One score in [0, 1] per passage, in the passages' order."""
        ...


class BgeReranker:
    def __init__(self, settings: Settings):
        self.model_id = settings.reranker_model_id
        self.model_revision = settings.reranker_model_revision
        self._device = settings.embedding_device
        self._batch_size = settings.reranker_batch_size
        self._model: Any = None
        # Questions run on several threads and the model isn't safe to share, so calls take
        # turns, as the embedder's do.
        self._lock = threading.RLock()

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        import torch

        pairs = [(query, passage) for passage in passages]
        with self._lock:
            try:
                model = self._get_model()
            except Exception as error:
                raise RerankError(f"could not load {self.model_id}") from error
            batch_size = self._batch_size
            while True:
                try:
                    scores = model.predict(
                        pairs,
                        batch_size=batch_size,
                        activation_fn=torch.nn.Sigmoid(),
                        show_progress_bar=False,
                    )
                    return [float(score) for score in scores]
                except torch.cuda.OutOfMemoryError as error:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    if batch_size == 1:
                        raise RerankError("out of memory reranking one passage") from error
                    batch_size //= 2
                    logger.warning("Reranker out of memory; retrying at batch size %d", batch_size)
                except Exception as error:
                    raise RerankError(f"{self.model_id} could not score the passages") from error

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._from_cache_or_hub(self._load_model)
        return self._model

    def _load_model(self, local_files_only: bool) -> Any:
        import torch
        from sentence_transformers import CrossEncoder

        on_gpu = self._device.startswith("cuda")
        return CrossEncoder(
            self.model_id,
            revision=self.model_revision,
            device=self._device,
            max_length=MAX_LENGTH,
            model_kwargs={"dtype": torch.float16 if on_gpu else torch.float32},
            local_files_only=local_files_only,
        )

    def _from_cache_or_hub(self, load: Callable[[bool], Any]) -> Any:
        """Load from the local cache without contacting the Hub, downloading only if missing."""
        try:
            return load(True)
        except (OSError, ValueError):
            logger.info("Downloading %s at %s", self.model_id, self.model_revision)
            return load(False)
