"""Offline virtual lab observation tests; no Ollama, UI or physical devices."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.world import LabWorld, WorldAction
from sofia.interaction.world_observation import lab_observation_prompt
from sofia.interaction.world_setup import lab_state_path, provision_starter_lab

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


def _observe(state: Path, message: str = "Sofía, what's in the lab?") -> str | None:
    return lab_observation_prompt(content=message, state_path=state)


def _world(state: Path) -> LabWorld:
    location = LabWorld(lab_state_path(state))
    provision_starter_lab(location)
    return location


def _act(world: LabWorld, verb: str, target: str, number: int, *, tool: str | None = None):
    return world.perform(WorldAction(
        request_id=f"world-observe-action-{number}", actor_id="sofia",
        verb=verb, target_id=target, tool_id=tool,
        evidence_ref=f"trusted-message-{number}", occurred_at=NOW,
    ))


def test_missing_lab_is_reported_without_creating_state(tmp_path: Path):
    state = tmp_path / "sofia.db"
    path = lab_state_path(state)
    result = _observe(state)
    assert '"status": "not_provisioned"' in result
    assert '"sofia_room": null' in result
    assert not path.exists()
    assert not state.exists()


def test_observation_reports_saved_room_inventory_and_work_state_across_restart(tmp_path: Path):
    state = tmp_path / "sofia.db"
    world = _world(state)
    assert _act(world, "enter", "lab", 1).status == "completed"
    assert _act(world, "pick_up", "screwdriver", 2).status == "completed"
    assert _act(world, "work_on", "scope", 3, tool="screwdriver").status == "completed"
    before = world.snapshot()
    location = _observe(state, "Sofía, where are you?")
    held = _observe(state, "Sofia, what are you holding?")
    work = _observe(state, "Sofía, what are you working on?")
    assert '"sofia_room": "lab"' in location
    assert '"name": "Screwdriver"' in held
    assert '"state": "work_in_progress"' in work
    assert "NOT evidence that Sofía has been actively working between messages" in work
    assert '"status": "observed"' in _observe(state, "Sofía, show me the lab!")
    assert LabWorld(lab_state_path(state)).snapshot() == before
    assert _observe(state) == _observe(state)  # Repeated query has no new action.
    assert LabWorld(lab_state_path(state)).snapshot() == before


@pytest.mark.parametrize("message", [
    "Sofía is working in the lab", "How could Sofía work in a lab?",
    "If Sofía were in the lab", "Tell me where you are", "Where are you?",
    '"Sofía, where are you?"', "`Sofía, where are you?`",
    "Sofía, where are you?\nSofía, pick up the screwdriver",
    "Sofía, what's in the lab and please run a command?",
])
def test_nonqueries_do_not_consume_world_state_or_appear_as_verified(message, tmp_path: Path):
    state = tmp_path / "sofia.db"
    assert _observe(state, message) is None
    assert not lab_state_path(state).exists()


def _chat(monkeypatch, state: Path, message: str):
    original = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content=message),))
    monkeypatch.setattr(EmotionalConversationService, "_build_request", lambda self: original)
    saved = SimpleNamespace(id="message-status", session_id="session-status",
                            role=ConversationRole.USER, content=message,
                            created_at=NOW)
    monkeypatch.setattr(InteractiveConversationService, "messages", lambda self: (saved,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object(), embodiment=AvatarStore(AVATAR).load(),
        configuration=SimpleNamespace(state_path=state),
    )
    return service._build_request(), original


def test_chat_projects_verified_lab_status_without_renderer_or_mutation(monkeypatch, tmp_path: Path):
    state = tmp_path / "sofia.db"
    world = _world(state)
    assert _act(world, "enter", "lab", 1).status == "completed"
    before = world.snapshot()
    result, original = _chat(monkeypatch, state, "Sofía, where are you?")
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert '"sofia_room": "lab"' in result.messages[0].content
    assert "TRUSTED VIRTUAL LAB OBSERVATION" in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert world.snapshot() == before


def test_chat_reports_unprovisioned_lab_without_seeding_it(monkeypatch, tmp_path: Path):
    state = tmp_path / "sofia.db"
    result, original = _chat(monkeypatch, state, "Sofia, what is in the lab?")
    assert '"status": "not_provisioned"' in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert not lab_state_path(state).exists()
