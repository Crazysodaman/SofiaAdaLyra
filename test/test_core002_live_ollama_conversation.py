"""CORE-002 operator-only REAL-Ollama conversation acceptance probe.

This intentionally does not fake model output. It is skipped unless the owner
explicitly opts in with SOFIA_CORE002_LIVE=1 on a disposable test host.
A skip is NOT inference evidence and must not be promoted to release PASS.
"""
from dataclasses import replace
import json
import os
from time import monotonic

import pytest

from sofia.core.cognition.providers.ollama_provider import OllamaProvider
from sofia.core.conversation.model import ConversationRole
from sofia.platform.application.bootstrap import SofiaApplication
from sofia.platform.config.defaults import create_default_configuration
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


@pytest.mark.integration
def test_core002_real_provider_multiturn_and_persistence(monkeypatch, tmp_path):
    if os.getenv("SOFIA_CORE002_LIVE") != "1":
        pytest.skip("OWNER OPT-IN REQUIRED; skipped is NOT genuine inference PASS")
    model = os.getenv("SOFIA_OLLAMA_MODEL", "").strip()
    if not model:
        pytest.fail("Set SOFIA_OLLAMA_MODEL to an installed model before live QA")

    # The canonical personal runtime and model-management hooks must stay off.
    # This test only uses disposable SQLite, normal application composition
    # and the already-running, explicitly approved Ollama endpoint.
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_MANAGE", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_INSTALL", "0")
    monkeypatch.setenv("SOFIA_CORE_WORKER_ENABLED", "0")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_ENABLED", "0")

    configuration = replace(
        create_default_configuration(),
        provider=ProviderConfiguration(provider="ollama", model=model),
        state_path=tmp_path / "core002-disposable.db",
        filesystem_root=tmp_path,
    )
    bootstrap_canonical_sqlite(configuration.state_path)

    # Instrument the genuine transport without replacing or simulating it.
    original_respond_once = OllamaProvider._respond_once
    provider_calls = []

    def observed_real_inference(self, request):
        began = monotonic()
        receipt = {"provider": "ollama", "model": self.configuration.model,
                   "endpoint": self.endpoint, "real_client_path": True}
        try:
            result = original_respond_once(self, request)
            receipt["status"] = "generated"
            receipt["output_characters"] = len(result.content)
            receipt["tool_calls"] = len(result.tool_calls)
            return result
        except Exception as error:
            receipt["status"] = "error"
            receipt["exception_type"] = type(error).__name__
            raise
        finally:
            receipt["latency_ms"] = round((monotonic() - began) * 1000, 1)
            provider_calls.append(receipt)

    monkeypatch.setattr(OllamaProvider, "_respond_once", observed_real_inference)

    application = SofiaApplication(configuration)
    label = "cobalt-otter-472"
    prompts = (
        f"For this disposable test session, remember the label {label}. "
        "Acknowledge it briefly.",
        "What exact label did I just give you?",
        "Switch topics: explain in one sentence what a circuit breaker does.",
        "Now return to the earlier label. What was it?",
    )
    turns = []
    began = monotonic()
    try:
        application.start()
        for prompt in prompts:
            turn_start = monotonic()
            response = application.conversation.respond(prompt)
            turns.append((prompt, response.content, round(
                (monotonic() - turn_start) * 1000, 1,
            )))

        assert len(turns) == 4
        assert all(content.strip() for _, content, _ in turns)
        assert all(content != "Test cognitive response." for _, content, _ in turns)
        assert label in turns[1][1].casefold(), "Second turn lost recent user context"
        assert label in turns[3][1].casefold(), "Topic switch lost earlier label"
        assert sum(call["status"] == "generated" for call in provider_calls) >= 4

        saved = application.conversation.messages()
        for prompt, response, _ in turns:
            assert any(
                item.role is ConversationRole.USER and item.content == prompt
                for item in saved
            ), "User input was not persisted"
            assert any(
                item.role is ConversationRole.ASSISTANT and item.content == response
                for item in saved
            ), "Generated assistant response was not persisted"
    finally:
        print("CORE002_LIVE_RECEIPT=" + json.dumps({
            "real_ollama_probes": provider_calls,
            "turn_latencies_ms": [duration for _, _, duration in turns],
            "total_elapsed_ms": round((monotonic() - began) * 1000, 1),
            "disposable_state": True,
            "model_output_in_receipt": False,
        }, sort_keys=True))
        application.shutdown()
