"""Real virtual location state tests, separate from synthetic InteractionLab."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.interaction.world import LabWorld, WorldAction

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def action(verb, target, *, request_id=None, tool_id=None, actor="sofia"):
    return WorldAction(
        request_id=request_id or f"request-{verb}-{target}",
        actor_id=actor, verb=verb, target_id=target,
        tool_id=tool_id, evidence_ref="trusted-controller-1", occurred_at=NOW,
    )


@pytest.fixture
def world(tmp_path: Path) -> LabWorld:
    lab = LabWorld(tmp_path / "world.sqlite3")
    lab.add_room("lab", "Sofía's lab")
    lab.add_room("hall", "Hallway")
    lab.add_actor("sofia")
    lab.add_actor("visitor")
    lab.add_object("screwdriver", "Precision screwdriver", "tool", "lab")
    lab.add_object("scope", "Bench oscilloscope", "equipment", "lab")
    lab.add_object("hall-tool", "Hallway tool", "tool", "hall")
    return lab


def _object(world: LabWorld, object_id: str):
    return next(row for row in world.snapshot()["objects"] if row[0] == object_id)


def test_lab_is_a_location_with_real_persisted_inventory_not_a_fixture(world: LabWorld):
    assert world.snapshot()["actors"] == (("sofia", None), ("visitor", None))
    assert world.perform(action("pick_up", "screwdriver")).status == "denied"
    assert world.perform(action("enter", "lab")).status == "completed"
    assert world.perform(action("pick_up", "screwdriver")).status == "completed"
    assert _object(world, "screwdriver")[4:] == ("sofia", "held")
    assert world.perform(action("leave", "lab")).status == "denied"
    assert world.perform(action("put_down", "screwdriver")).status == "completed"
    assert _object(world, "screwdriver")[4:] == (None, "available")
    assert world.perform(action("leave", "lab", request_id="leave-after-putdown")).status == "completed"
    reopened = LabWorld(world.path)
    assert reopened.snapshot() == world.snapshot()
    assert reopened.snapshot()["actors"][0] == ("sofia", None)


def test_work_on_equipment_is_evidenced_state_not_invented_repair(world: LabWorld):
    world.perform(action("enter", "lab"))
    denied = world.perform(action("work_on", "scope", tool_id="screwdriver"))
    assert denied.status == "denied"
    assert _object(world, "scope")[-1] == "idle"
    world.perform(action("pick_up", "screwdriver"))
    started = world.perform(action("work_on", "scope", request_id="work-2", tool_id="screwdriver"))
    assert started.status == "completed"
    assert "no repair is claimed" in started.reason
    assert _object(world, "scope")[-1] == "work_in_progress"
    assert world.perform(action("finish_work", "scope")).status == "completed"
    assert _object(world, "scope")[-1] == "work_finished"
    reopened = LabWorld(world.path)
    assert _object(reopened, "scope")[-1] == "work_finished"


def test_same_event_is_idempotent_and_changed_payload_is_rejected(world: LabWorld):
    world.perform(action("enter", "lab"))
    original = action("pick_up", "screwdriver", request_id="same-message")
    first = world.perform(original)
    assert first.status == "completed"
    assert world.perform(original) == first
    with pytest.raises(ValueError, match="cannot be reused"):
        world.perform(action("pick_up", "hall-tool", request_id="same-message"))
    assert _object(world, "screwdriver")[4] == "sofia"
    assert _object(world, "hall-tool")[4] is None
    assert world.perform(action("pick_up", "screwdriver", request_id="another-message")).status == "denied"


def test_actor_scope_unavailable_objects_and_missing_room_fail_without_mutation(world: LabWorld):
    before = world.snapshot()
    assert world.perform(action("enter", "missing-room")).status == "denied"
    assert world.perform(action("enter", "lab", actor="unknown", request_id="unknown-actor")).status == "denied"
    assert world.snapshot() == before
    world.perform(action("enter", "lab"))
    assert world.perform(action("pick_up", "hall-tool")).status == "denied"
    assert world.perform(action("pick_up", "missing-object")).status == "denied"
    assert world.perform(action("pick_up", "scope")).status == "denied"
    assert world.perform(action("finish_work", "scope")).status == "denied"
    assert _object(world, "scope")[-1] == "idle"


def test_content_is_not_executed_and_invalid_event_fails_visibly(world: LabWorld):
    assert world.snapshot()["actors"][0][1] is None
    with pytest.raises(ValueError, match="Unsupported"):
        action("execute_shell", "scope")
    with pytest.raises(ValueError, match="requires a specific held tool"):
        action("work_on", "scope")
    with pytest.raises(ValueError, match="bounded ASCII"):
        action("pick_up", "scope; DROP TABLE lab_rooms")
    with pytest.raises(ValueError, match="aware timestamp"):
        WorldAction("some-request", "sofia", "enter", "lab", "source-id",
                    datetime(2026, 9, 20))
    assert world.snapshot()["actors"][0][1] is None


def test_authoring_does_not_silently_seed_objects_or_rewrite_existing_state(tmp_path: Path):
    path = tmp_path / "empty.sqlite3"
    world = LabWorld(path)
    assert world.snapshot() == {"rooms": (), "actors": (), "objects": ()}
    with pytest.raises(ValueError, match="existing on-disk"):
        LabWorld(":memory:")
    with pytest.raises(ValueError, match="existing on-disk"):
        LabWorld(tmp_path / "missing" / "world.sqlite3")
