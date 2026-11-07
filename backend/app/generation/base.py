from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """The model failed, timed out or returned output that isn't a valid answer."""


class LLMQuotaExhausted(LLMError):
    """OpenRouter's free-model daily limit is used up; no free model answers until it resets."""


@dataclass(frozen=True)
class GenerationRequest:
    messages: list[dict[str, str]]


@dataclass(frozen=True)
class GenerationResult:
    status: str
    answer: str
    model: str
    input_tokens: int | None
    output_tokens: int | None


class LLMProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
