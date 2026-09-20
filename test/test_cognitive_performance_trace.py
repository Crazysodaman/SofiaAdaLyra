"""Performance traces distinguish actual provider counters from unknown data."""
from types import SimpleNamespace

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.cognition.performance import emit_performance, ollama_metric
from sofia.cognition.provider import LLMProviderError
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration


class FakeClient:
    def __init__(self, *, metrics=True, fail=False):
        self.metrics = metrics
        self.fail = fail

    def chat(self, **kwargs):
        if self.fail:
            raise RuntimeError("canary-error-containing-sensitive-text")
        counters = dict(
            load_duration=2_000_000_000,
            prompt_eval_duration=3_000_000_000,
            eval_duration=4_000_000_000,
            total_duration=9_000_000_000,
            prompt_eval_count=300,
            eval_count=30,
        ) if self.metrics else {}
        return SimpleNamespace(
            message=SimpleNamespace(content="canary-model-output", tool_calls=None),
            **counters,
        )


def _provider(*, metrics=True, fail=False):
    return OllamaProvider(
        configuration=ProviderConfiguration(
            provider="ollama", model="test-model", context_size=20000,
        ),
        client=FakeClient(metrics=metrics, fail=fail),
    )


def _request():
    return CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.USER, content="canary-private-prompt"),
    ))


def test_opt_in_reports_provider_counters_but_never_content(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    assert _provider().respond(_request()).content == "canary-model-output"
    log = capsys.readouterr().err
    assert "[sofia-perf] ollama" in log
    for field in ("load_ms=2000.0", "prompt_eval_ms=3000.0",
                  "generation_ms=4000.0", "provider_total_ms=9000.0",
                  "prompt_tokens=300", "generated_tokens=30", "context_tokens=20000"):
        assert field in log
    assert "elapsed_ms=" in log
    assert "canary" not in log and "test-model" not in log


def test_missing_metrics_are_unknown_not_zero(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    _provider(metrics=False).respond(_request())
    log = capsys.readouterr().err
    assert "load_ms=unknown" in log
    assert "prompt_tokens=unknown" in log
    assert "generation_ms=unknown" in log
    assert "context_tokens=20000" in log


def test_disabled_trace_is_silent(monkeypatch, capsys):
    monkeypatch.delenv("SOFIA_PERF_TRACE", raising=False)
    _provider().respond(_request())
    assert capsys.readouterr().err == ""


def test_failed_call_reports_elapsed_time_not_exception_content(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    with pytest.raises(LLMProviderError):
        _provider(fail=True).respond(_request())
    log = capsys.readouterr().err
    assert "[sofia-perf] ollama elapsed_ms=" in log
    assert "canary" not in log


def test_malformed_metrics_are_unknown_and_unsupported_fields_fail(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    assert ollama_metric(SimpleNamespace(load_duration=True), "load_duration", duration=True) is None
    assert ollama_metric(SimpleNamespace(eval_count="30"), "eval_count") is None
    with pytest.raises(ValueError, match="Unsupported performance trace field"):
        emit_performance("ollama", content="canary-private-prompt")
    with pytest.raises(ValueError, match="nonnegative"):
        emit_performance("ollama", elapsed_ms=-1)
    assert capsys.readouterr().err == ""
