"""Opt-in live Ollama reflection probe, isolated from Sofía's saved state.

Run explicitly with SOFIA_LIVE_THOUGHT_MODEL set to an installed Ollama model.
This exercises provider output and ThoughtAgent validation, not the full
application runtime, semantic truth, unattended execution, or delivery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

from ollama import Client
import pytest

from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal
from sofia.personality.thought_agent import ThoughtAgent


@pytest.mark.skipif(
    not os.environ.get("SOFIA_LIVE_THOUGHT_MODEL", "").strip(),
    reason="Set SOFIA_LIVE_THOUGHT_MODEL to opt into a real Ollama request.",
)
def test_live_ollama_generates_one_grounded_reflection_without_delivery(tmp_path):
    model = os.environ["SOFIA_LIVE_THOUGHT_MODEL"].strip()
    state_path = tmp_path / "live-reflection-probe.db"
    emotions = EmotionalJournal(state_path)
    reflections = ReflectionJournal(state_path)
    observed_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    emotions.record(
        event_id="synthetic-probe:test-failure",
        occurred_at=observed_at,
        source="observed",
        evidence_ref="synthetic-test-fixture-not-a-real-test-run",
        description="In this synthetic fixture, two test runs failed the same assertion; the cause is unknown.",
        emotions=("frustration", "curiosity", "determination"),
    )
    event = emotions.recent(now=datetime.now(timezone.utc))[0]
    provider = OllamaProvider(
        configuration=ProviderConfiguration(provider="ollama", model=model),
        client=Client(timeout=120.0),
    )
    calls = []

    def generate(request):
        response = provider.respond(request)
        calls.append(response)
        # Deliberately show the raw response even if ThoughtAgent rejects it.
        # The event is synthetic and includes no user data or system secrets.
        print(f"\nLIVE OLLAMA MODEL: {model}")
        print(f"RAW REFLECTION RESPONSE: {response.content!r}")
        print(f"TOOL CALL COUNT: {len(response.tool_calls)}")
        return response

    outcome = ThoughtAgent(generate=generate, reflections=reflections).reflect(
        event=event,
        now=datetime.now(timezone.utc),
    )
    print(f"RECORDED THOUGHT ID: {outcome.thought_id!r}")
    print(f"QUEUED UNSENT MESSAGE ID: {outcome.queued_message_id!r}")
    assert len(calls) == 1
    assert len(reflections.recent_thoughts()) == (1 if outcome.thought_id else 0)
    pending = reflections.pending()
    assert len(pending) == (1 if outcome.queued_message_id else 0)
    if pending:
        assert pending[0].evidence_ref == event.event_id
        assert pending[0].status == "pending"
        print(f"UNSENT MESSAGE TEXT: {pending[0].content!r}")
