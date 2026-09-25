"""Narrow real-location text adapter and future-avatar action parity, offline."""
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
from sofia.interaction.world_setup import lab_state_path, provision_starter_lab
from sofia.interaction.world_text import handle_lab_command

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


@pytest.fixture
def world(tmp_path: Path):
    location = LabWorld(tmp_path / "real-lab.db")
    provision_starter_lab(location)
    return location


def handle(world, text, message="m1"):
    return handle_lab_command(world=world, content=text,
                              message_id=message, occurred_at=NOW)


def test_text_commands_act_on_one_persistent_world(world: LabWorld):
    assert handle(world, "Sofía, pick up the screwdriver").status == "denied"
    assert handle(world, "Sofía, enter the lab", "m2").status == "completed"
    pickup = handle(world, "Sofia, pick up the screwdriver", "m3")
    assert pickup.status == "completed"
    assert handle(world, "Sofia, pick up the screwdriver", "m3") == pickup
    assert handle(world, "Sofía, work on the oscilloscope with the screwdriver", "m4").status == "completed"
    assert next(row for row in world.snapshot()["objects"] if row[0] == "scope")[-1] == "work_in_progress"
    assert handle(world, "Sofía, finish work on the scope", "m5").status == "completed"
    restarted = LabWorld(world.path)
    assert next(row for row in restarted.snapshot()["objects"] if row[0] == "scope")[-1] == "work_finished"
    assert next(row for row in restarted.snapshot()["objects"] if row[0] == "screwdriver")[4] == "sofia"


@pytest.mark.parametrize("text", [
    "Sofía is working on some lab equipment", "Sofia picks up a screwdriver",
    "If Sofía picks up the screwdriver", "Could Sofía pick up the screwdriver?",
    "`Sofía, pick up the screwdriver`", '"Sofía, pick up the screwdriver"',
    "Sofía, pick up the screwdriver\nSofía, leave the lab",
])
def test_narration_questions_quotes_and_code_are_not_actions(world: LabWorld, text: str):
    before = world.snapshot()
    assert handle(world, text) is None
    assert world.snapshot() == before


def test_ambiguous_equipment_does_not_invent_an_object(world: LabWorld):
    assert handle(world, "Sofía, work on some lab equipment").status == "clarify"
    assert handle(world, "Sofía, pick up the quantum spanner").status == "clarify"
    assert world.snapshot()["actors"] == (("sofia", None),)


def test_simulated_resolved_avatar_uses_same_world_operation_as_text(tmp_path: Path):
    written = LabWorld(tmp_path / "written.db")
    visual = LabWorld(tmp_path / "visual.db")
    for world in (written, visual):
        provision_starter_lab(world)
        world.perform(WorldAction("enter", "sofia", "enter", "lab", "controller", NOW))
    text_result = handle(written, "Sofía, pick up the screwdriver", "text-message")
    # A future trusted avatar adapter must resolve the object, actor and verb;
    # no coordinates, click-to-pat inference or real renderer is supplied here.
    avatar_result = visual.perform(WorldAction(
        "avatar-gesture", "sofia", "pick_up", "screwdriver", "trusted-ui-fixture", NOW))
    assert text_result.status == avatar_result.status == "completed"
    assert text_result.outcome.verb == avatar_result.verb == "pick_up"
    assert text_result.outcome.target_id == avatar_result.target_id == "screwdriver"
    assert written.snapshot() == visual.snapshot()


def test_chat_uses_actual_world_state_without_changing_original_message(monkeypatch, tmp_path: Path):
    original = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content="Sofía, enter the lab"),))
    monkeypatch.setattr(EmotionalConversationService, "_build_request", lambda self: original)
    message = SimpleNamespace(id="saved-message-1", session_id="session-1",
                              role=ConversationRole.USER, content="Sofía, enter the lab",
                              created_at=NOW)
    monkeypatch.setattr(InteractiveConversationService, "messages", lambda self: (message,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(personality=object(),
                                       embodiment=AvatarStore(AVATAR).load(),
                                       configuration=SimpleNamespace(state_path=tmp_path / "sofia.db"))
    result = service._build_request()
    assert '"status": "completed"' in result.messages[0].content
    assert '"sofia_room": "lab"' in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert service._build_request().messages[0].content == result.messages[0].content
    actual = LabWorld(lab_state_path(tmp_path / "sofia.db"))
    assert actual.snapshot()["actors"] == (("sofia", "lab"),)
    assert next(row for row in actual.snapshot()["objects"] if row[0] == "screwdriver")[4] is None


def test_chat_narration_does_not_create_world_or_claim_work(monkeypatch, tmp_path: Path):
    original = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content="Sofía is working on some lab equipment"),))
    monkeypatch.setattr(EmotionalConversationService, "_build_request", lambda self: original)
    message = SimpleNamespace(id="saved-message-2", session_id="session-1",
                              role=ConversationRole.USER,
                              content="Sofía is working on some lab equipment", created_at=NOW)
    monkeypatch.setattr(InteractiveConversationService, "messages", lambda self: (message,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(personality=object(),
                                       embodiment=AvatarStore(AVATAR).load(),
                                       configuration=SimpleNamespace(state_path=tmp_path / "sofia.db"))
    assert service._build_request() is original
    assert not lab_state_path(tmp_path / "sofia.db").exists()
