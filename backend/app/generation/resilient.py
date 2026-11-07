import logging

from app.generation.base import (
    GenerationRequest,
    GenerationResult,
    LLMError,
    LLMProvider,
    LLMQuotaExhausted,
)

logger = logging.getLogger(__name__)


class ResilientLLM:
    """Try the primary model, then the fallback once.

    A used-up daily quota skips the fallback, because that limit covers every free model.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self._primary = primary
        self._fallback = fallback

    def generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            return self._primary.generate(request)
        except LLMQuotaExhausted:
            raise
        except LLMError as error:
            logger.warning("Primary model failed, trying the fallback: %s", error)
            return self._fallback.generate(request)
