import json
import logging

import httpx
import pytest

from app.generation.base import GenerationRequest, LLMError, LLMQuotaExhausted
from app.generation.openrouter import OpenRouterProvider

API_KEY = "test-key-not-real"
BODY_OK = {
    "choices": [{"message": {"content": '{"status":"answered","answer":"Yes [1]."}'}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}
# The body OpenRouter returned for the fallback model on 2026-11-07 (docs/phase-1-early-checks.md).
UPSTREAM_429 = {
    "error": {
        "message": "Provider returned error",
        "code": 429,
        "metadata": {
            "raw": "google/gemma-4-31b-it:free is temporarily rate-limited upstream.",
            "provider_name": "Google AI Studio",
            "limit_source": "upstream_provider_shared_pool",
        },
    }
}


def provider(handler, structured=True):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenRouterProvider(API_KEY, "m", structured=structured, client=client, timeout=1.0)


def capture(body, structured=True):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json=body)

    provider(handler, structured).generate(GenerationRequest([{"role": "user", "content": "q"}]))
    return sent[0]


def capture_request(body, structured=True):
    return json.loads(capture(body, structured).content)


def call(body, status=200):
    return provider(lambda request: httpx.Response(status, json=body)).generate(
        GenerationRequest([])
    )


def body_with(content):
    return {"choices": [{"message": {"content": content}}]}


def raise_timeout(request):
    raise httpx.ReadTimeout("timed out", request=request)


def test_structured_request_uses_strict_schema():
    sent = capture_request(BODY_OK, structured=True)
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["provider"]["require_parameters"] is True


def test_fallback_request_uses_json_mode():
    assert capture_request(BODY_OK, structured=False)["response_format"] == {"type": "json_object"}


def test_request_sends_the_api_key_as_a_bearer_token():
    assert capture(BODY_OK).headers["authorization"] == f"Bearer {API_KEY}"


def test_result_is_parsed_with_usage():
    result = call(BODY_OK)
    assert (result.status, result.input_tokens, result.output_tokens) == ("answered", 10, 5)


def test_fenced_json_is_accepted():
    assert call(body_with('```json\n{"status":"answered","answer":"x"}\n```')).answer == "x"


@pytest.mark.parametrize(
    "content", ["not json", '{"answer":"x"}', '{"status":"maybe","answer":"x"}', None]
)
def test_invalid_output_raises_llm_error(content):
    with pytest.raises(LLMError):
        call(body_with(content))


def test_error_inside_http_200_raises_llm_error_even_with_content():
    with pytest.raises(LLMError):
        call({**BODY_OK, "error": {"code": 502, "message": "boom"}})


DAILY = "Rate limit exceeded: free-models-per-day"
# The daily-limit shape reported publicly for OpenRouter; not yet observed in this project.
REPORTED_HEADERS = {"X-RateLimit-Limit": "50", "X-RateLimit-Remaining": "0"}


@pytest.mark.parametrize(
    "metadata, message",
    [
        (None, DAILY),
        ({"headers": REPORTED_HEADERS, "provider_name": None}, DAILY),
        ({"provider_name": None}, "Rate limit exceeded"),
        ({"provider_name": "Google AI Studio"}, DAILY),
    ],
    ids=["plain", "reported-shape", "null-provider", "message-wins"],
)
def test_free_daily_limit_raises_quota_exhausted(metadata, message):
    error = {"code": 429, "message": message}
    if metadata is not None:
        error["metadata"] = metadata
    with pytest.raises(LLMQuotaExhausted):
        call({"error": error}, status=429)


@pytest.mark.parametrize(
    "metadata",
    [
        {"provider_code": 429},
        {"provider_name": "Google AI Studio"},
        {"limit_source": "upstream_provider_shared_pool"},
    ],
    ids=["provider_code", "provider_name", "limit_source"],
)
def test_upstream_429_raises_llm_error(metadata):
    body = {"error": {"code": 429, "message": "busy", "metadata": metadata}}
    with pytest.raises(LLMError) as caught:
        call(body, status=429)
    assert not isinstance(caught.value, LLMQuotaExhausted)


def test_observed_upstream_429_without_provider_code_raises_llm_error():
    with pytest.raises(LLMError) as caught:
        call(UPSTREAM_429, status=429)
    assert not isinstance(caught.value, LLMQuotaExhausted)


def test_per_minute_limit_raises_llm_error():
    body = {"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-min."}}
    with pytest.raises(LLMError) as caught:
        call(body, status=429)
    assert not isinstance(caught.value, LLMQuotaExhausted)


def test_429_body_is_logged_without_the_api_key(caplog):
    with caplog.at_level(logging.WARNING), pytest.raises(LLMError):
        call(UPSTREAM_429, status=429)
    assert "upstream_provider_shared_pool" in caplog.text and API_KEY not in caplog.text


@pytest.mark.parametrize("status", [402, 500, 502, 503])
def test_server_errors_raise_llm_error(status):
    with pytest.raises(LLMError):
        call({"error": {"code": status, "message": "x"}}, status=status)


def test_timeout_raises_llm_error():
    with pytest.raises(LLMError):
        provider(raise_timeout).generate(GenerationRequest([]))
