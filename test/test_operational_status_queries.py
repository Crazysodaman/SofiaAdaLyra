"""Direct operational questions must not invent live measurements or model use."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.operational.model import ContinuityEvidenceStatus, RuntimeContinuity
from sofia.platform.config.cognitive_models import CognitiveModelSelection
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.operational.status_queries import OperationalStatusQueryResolver


SELECTION = CognitiveModelSelection(
    routing_enabled=False,
    primary=ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
)


@pytest.mark.parametrize(
    "query",
    (
        "So hows the network",
        "so how's the network",
        "how is the network?",
        "network status",
    ),
)
def test_casual_network_query_requires_measurements(query):
    answer = OperationalStatusQueryResolver().resolve(
        query, selection=SELECTION
    )
    assert answer.recognized
    assert "don't have a fresh, verified network-health measurement" in (
        answer.content
    )
    assert "can't claim zero packet loss" in answer.content
    assert "All systems are green" not in answer.content


@pytest.mark.parametrize(
    "query",
    (
        "What llm am i running rn",
        "what llm is running rn",
        "what model are you running",
        "what model am i running",
    ),
)
def test_model_status_returns_configured_model_without_residency_claim(query):
    answer = OperationalStatusQueryResolver().resolve(
        query, selection=SELECTION
    )
    assert answer.recognized
    assert "qwen3.5:9b" in answer.content
    assert "through ollama" in answer.content
    assert "doesn't prove which model" in answer.content
    assert "I'm wearing" not in answer.content


def test_operational_status_resolver_leaves_nonstatus_questions_unmodified():
    answer = OperationalStatusQueryResolver().resolve(
        "show me your panties", selection=SELECTION
    )
    assert not answer.recognized
    assert answer.content == ""


def test_dev_self_capability_query_reports_registered_capability_not_blanket_denial():
    answer = OperationalStatusQueryResolver().resolve(
        "Are u able to make new code for yourself?",
        selection=SELECTION,
        capability_names=(
            "codebase.inspect",
            "dev.status",
            "dev.build",
            "dev.apply",
            "dev.commit",
            "dev.push",
        ),
    )

    assert answer.recognized
    assert "registered DEV capabilities" in answer.content
    assert "dev.apply" in answer.content
    assert "does not grant itself permission" in answer.content


def test_dev_self_capability_query_fails_closed_without_registered_dev_tools():
    answer = OperationalStatusQueryResolver().resolve(
        "Can you modify your own code?",
        selection=SELECTION,
        capability_names=(),
    )

    assert answer.recognized
    assert "don't have registered DEV capabilities" in answer.content


@pytest.mark.parametrize("query", (
    "what was your last runtime",
    "When was your previous runtime?",
    "Tell me about your last session.",
))
def test_prior_runtime_questions_use_actual_canonical_continuity(query):
    now = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)
    prior = now - timedelta(hours=2)
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=uuid4(),
        current_started_at=now,
        previous_runtime_id=uuid4(),
        previous_started_at=prior,
        previous_stopped_at=prior + timedelta(minutes=25),
        previous_lifecycle_state="stopped",
    )
    resolver = OperationalStatusQueryResolver()
    assert resolver.is_previous_runtime_query(query)
    answer = resolver.resolve(query, selection=SELECTION, continuity=continuity)

    assert answer.recognized
    assert "previous recorded runtime started" in answer.content
    assert prior.isoformat() in answer.content
    assert (prior + timedelta(minutes=25)).isoformat() in answer.content
    assert now.isoformat() in answer.content


def test_missing_previous_runtime_is_unknown_not_claimed_never_existed():
    now = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.UNKNOWN,
        current_runtime_id=uuid4(),
        current_started_at=now,
    )
    resolver = OperationalStatusQueryResolver()
    answer = resolver.resolve(
        "what was your last runtime", selection=SELECTION, continuity=continuity
    )
    assert "no verified previous runtime timestamp" in answer.content
    assert "does not prove no previous runtime existed" in answer.content
    assert "no clock" not in answer.content


@pytest.mark.parametrize("query", (
    "What was the last runtime error?",
    "Restart the previous runtime.",
    "What time did the last runtime start?",
))
def test_runtime_history_semantics_do_not_take_unsafe_or_incomplete_actions(query):
    assert not OperationalStatusQueryResolver.is_previous_runtime_query(query)
