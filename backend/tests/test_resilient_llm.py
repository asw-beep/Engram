import pytest

from app.generation.base import GenerationRequest, GenerationResult, LLMError, LLMQuotaExhausted
from app.generation.resilient import ResilientLLM
from tests.fakes import FakeLLM

REQUEST = GenerationRequest([{"role": "user", "content": "q"}])
OK = GenerationResult(
    status="answered", answer="Yes [1].", model="fallback", input_tokens=1, output_tokens=1
)


def test_primary_result_is_used_without_the_fallback():
    fallback = FakeLLM(result=OK)
    primary = FakeLLM().returns("answered", "From primary [1].")
    assert ResilientLLM(primary, fallback).generate(REQUEST).answer == "From primary [1]."
    assert fallback.calls == []


def test_fallback_runs_once_after_primary_fails():
    primary, fallback = FakeLLM(error=LLMError("x")), FakeLLM(result=OK)
    assert ResilientLLM(primary, fallback).generate(REQUEST) == OK
    assert len(fallback.calls) == 1


def test_quota_does_not_use_fallback():
    fallback = FakeLLM(result=OK)
    with pytest.raises(LLMQuotaExhausted):
        ResilientLLM(FakeLLM(error=LLMQuotaExhausted("x")), fallback).generate(REQUEST)
    assert fallback.calls == []


def test_fallback_failure_is_raised():
    with pytest.raises(LLMError):
        ResilientLLM(FakeLLM(error=LLMError("a")), FakeLLM(error=LLMError("b"))).generate(REQUEST)
