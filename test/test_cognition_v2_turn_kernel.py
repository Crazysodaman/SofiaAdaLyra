"""Production-path tests for the Cognition v2 Turn Kernel and focus store."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.v2 import (
    ConversationFocusConflict,
    EntityCandidate,
    ProductionTurnKernel,
    SQLiteConversationFocusStore,
    TurnKernelInput,
)
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


PROJECT_ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _turn(content: str, number: int, *, audience: str = "private:sparks"):
    return TurnKernelInput(
        turn_id=f"turn:{number}",
        session_id="session:focus",
        content=content,
        created_at=NOW + timedelta(seconds=number),
        channel="desktop",
        principal_id="sparks",
        audience_id=audience,
    )


def _kernel(path: Path) -> ProductionTurnKernel:
    return ProductionTurnKernel(
        SQLiteConversationFocusStore(path),
        entity_provider=lambda: (
            EntityCandidate("fleet-node:artemis", "fleet-node", ("Artemis",)),
            EntityCandidate("fleet-node:venus", "fleet-node", ("Venus",)),
        ),
    )


def _coordinate(kernel, content: str, number: int, *, events=None, audience=None):
    observed = [] if events is None else events
    return kernel.coordinate(
        _turn(content, number, audience=audience or "private:sparks"),
        planning_callback=lambda turn: observed.append(("plan", turn)),
        attention_callback=lambda turn: observed.append(("attention", turn)),
    )


def test_kernel_preserves_reference_across_required_elliptical_sequence(tmp_path):
    kernel = _kernel(tmp_path / "sofia.db")
    sequence = (
        "Can you see Artemis?",
        "What are her stats?",
        "What's her CPU?",
        "Do it.",
        "Give me the figures.",
        "Well?",
    )

    turns = [
        _coordinate(kernel, content, index)
        for index, content in enumerate(sequence, start=1)
    ]

    assert {
        turn.focus.primary_reference.subject_id for turn in turns
    } == {"fleet-node:artemis"}
    assert turns[-1].resolution.source == "focused-reference"
    assert turns[3].focus.pending_actions[-1].source_turn_id == "turn:4"
    # A question beginning with "Can" must not become an execution request.
    assert all(
        action.source_turn_id != "turn:1"
        for action in turns[-1].focus.pending_actions
    )


def test_kernel_sequences_planning_before_attention(tmp_path):
    events = []
    coordinated = _coordinate(
        _kernel(tmp_path / "sofia.db"),
        "Can you see Artemis?",
        1,
        events=events,
    )

    assert [name for name, _ in events] == ["plan", "attention"]
    assert all(turn is coordinated for _, turn in events)


def test_typo_switch_correction_and_multiple_topics_are_structured(tmp_path):
    kernel = _kernel(tmp_path / "sofia.db")
    _coordinate(kernel, "Can you see Artemis?", 1)
    typo = _coordinate(kernel, "What are Artemsi's stats?", 2)
    switched = _coordinate(kernel, "Now check Venus.", 3)
    corrected = _coordinate(
        kernel,
        "Those stats belong to Artemis, not Venus.",
        4,
    )

    assert typo.resolution.source == "fuzzy-alias"
    assert typo.focus.primary_reference.subject_id == "fleet-node:artemis"
    assert switched.focus.primary_reference.subject_id == "fleet-node:venus"
    assert corrected.focus.primary_reference.subject_id == "fleet-node:artemis"
    assert corrected.resolution.corrected_subject_id == "fleet-node:venus"
    assert {topic.subject_ids[0] for topic in corrected.focus.topics} == {
        "fleet-node:artemis",
        "fleet-node:venus",
    }


def test_focus_is_restart_durable_and_audience_isolated(tmp_path):
    path = tmp_path / "sofia.db"
    first = _kernel(path)
    _coordinate(first, "Can you see Artemis?", 1)
    _coordinate(
        first,
        "Can you see Venus?",
        2,
        audience="private:someone-else",
    )

    restarted = _kernel(path)
    sparks = _coordinate(restarted, "Well?", 3)
    other = _coordinate(
        restarted,
        "Well?",
        4,
        audience="private:someone-else",
    )

    assert sparks.focus.primary_reference.subject_id == "fleet-node:artemis"
    assert other.focus.primary_reference.subject_id == "fleet-node:venus"


def test_store_rejects_stale_compare_and_swap(tmp_path):
    store = SQLiteConversationFocusStore(tmp_path / "sofia.db")
    empty = store.load(session_id="session:focus", audience_id="private:sparks")
    store.commit(replace(empty, revision=1), expected_revision=0)

    with pytest.raises(ConversationFocusConflict):
        store.commit(replace(empty, revision=1), expected_revision=0)


def test_settlement_requires_typed_evidence_and_matches_subject(tmp_path):
    kernel = _kernel(tmp_path / "sofia.db")
    _coordinate(kernel, "What's Artemis's CPU?", 1)
    action = _coordinate(kernel, "Do it.", 2)

    unchanged = kernel.settle(action, evidence_refs=("conversation:claim",))
    assert unchanged.unresolved_requests
    assert unchanged.pending_actions

    factual = kernel.settle(action, evidence_refs=("capability:fleet.inspect",))
    assert all(
        request.request_kind != "information"
        for request in factual.unresolved_requests
    )
    assert factual.pending_actions

    executed = kernel.settle(
        action,
        evidence_refs=("execution-receipt:operation-1",),
    )
    assert executed.unresolved_requests == ()
    assert executed.pending_actions == ()


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
        '{"name":"Sofía","traits":["direct"],'
        '"communication_style":"Clear and direct."}',
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=PROJECT_ROOT / "src/sofia/constitution/constitution.md",
        constitution_hash_path=(
            PROJECT_ROOT / "src/sofia/constitution/constitution.sha256"
        ),
        identity_path=PROJECT_ROOT / "src/sofia/identity/identity.json",
        personality_path=personality_path,
        avatar_path=PROJECT_ROOT / "src/sofia/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def test_application_composes_kernel_and_restores_focus_after_restart(tmp_path):
    configuration = _configuration(tmp_path)
    first = SofiaApplication(configuration)
    first.start()
    session_id = first.conversation.session_id

    first.conversation.respond("Can you see Artemis?")
    first.conversation.respond("What's her CPU?")
    focus = first.conversation.conversation_focus
    assert focus.primary_reference.aliases == ("Artemis",)
    assert "hardware.inspect" not in (
        first.conversation._current_tool_exposure_plan.capabilities
    )
    first.shutdown()

    restarted = SofiaApplication(configuration)
    restarted.start(session_id=session_id)
    restarted.conversation.respond("Well?")

    assert (
        restarted.conversation.conversation_focus.primary_reference.aliases
        == ("Artemis",)
    )
    restarted.shutdown()
