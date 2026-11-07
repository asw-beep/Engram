"""OpenRouter chat completions, returning a validated {status, answer} result."""

import logging
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.generation.base import GenerationRequest, GenerationResult, LLMError, LLMQuotaExhausted

logger = logging.getLogger(__name__)

URL = "https://openrouter.ai/api/v1/chat/completions"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
_SCHEMA = {
    "name": "grounded_answer",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["answered", "insufficient_evidence"]},
            "answer": {"type": "string"},
        },
        "required": ["status", "answer"],
        "additionalProperties": False,
    },
}


class _Output(BaseModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: str


class OpenRouterProvider:
    def __init__(
        self, api_key: str, model: str, structured: bool, client: httpx.Client, timeout: float
    ):
        self._api_key = api_key
        self.model = model
        self._structured = structured
        self._client = client
        self._timeout = timeout

    def generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            response = self._client.post(
                URL,
                json=self._body(request),
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as failure:
            raise LLMError(f"{self.model}: request failed ({type(failure).__name__})") from failure

        try:
            payload = response.json()
        except ValueError:
            raise LLMError(f"{self.model}: HTTP {response.status_code} without JSON") from None
        error = payload.get("error") if isinstance(payload, dict) else None
        error = error if isinstance(error, dict) else ({} if error is None else {"message": error})
        code = error.get("code")

        if response.status_code == 429 or code == 429:
            # Logged so the quota rule can be checked against real responses. Bodies hold no key.
            logger.warning("OpenRouter 429 for %s: %s", self.model, response.text[:2000])
            if _is_daily_quota(error):
                raise LLMQuotaExhausted(f"{self.model}: free-model daily limit reached")
            raise LLMError(f"{self.model}: rate limited")
        # OpenRouter can report a generation error inside an HTTP 200.
        if error or response.status_code >= 400:
            raise LLMError(f"{self.model}: HTTP {response.status_code}, error code {code}")

        try:
            content = payload["choices"][0]["message"]["content"]
            output = _Output.model_validate_json(_FENCE.sub("", content.strip()))
        except (KeyError, IndexError, TypeError, AttributeError, ValidationError) as failure:
            raise LLMError(f"{self.model}: invalid output") from failure
        usage = payload.get("usage") or {}
        return GenerationResult(
            status=output.status,
            answer=output.answer,
            model=self.model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def _body(self, request: GenerationRequest) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": request.messages}
        if self._structured:
            body["response_format"] = {"type": "json_schema", "json_schema": _SCHEMA}
            body["provider"] = {"require_parameters": True}
        else:
            body["response_format"] = {"type": "json_object"}
        return body


def _is_daily_quota(error: dict[str, Any]) -> bool:
    """Whether a 429 is OpenRouter's own free-model daily limit (spec section 7).

    OpenRouter doesn't document the shapes, so the rule is inferred. The daily limit is named
    in the message. Otherwise a 429 that names an upstream provider, or the per-minute limit,
    is temporary and the fallback should be tried. Anything else is treated as the daily limit.
    """
    message = str(error.get("message", ""))
    if "free-models-per-day" in message:
        return True
    metadata = error.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    # A null provider name, as in the reported daily-limit body, names no provider.
    names_upstream = (
        metadata.get("provider_code") is not None
        or bool(metadata.get("provider_name"))
        or str(metadata.get("limit_source", "")).startswith("upstream")
    )
    return not names_upstream and "per-min" not in message
