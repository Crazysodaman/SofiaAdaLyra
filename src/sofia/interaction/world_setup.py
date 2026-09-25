"""Reviewed starter assets for Sofía's *virtual* location, not physical inventory.

Called by the trusted application when an addressed lab command is received.
Existing objects/states are preserved; incompatible definitions fail visibly.
The world database is separate from Sofia's conversation SQLite file.
"""
from __future__ import annotations

from pathlib import Path

from sofia.interaction.world import LabWorld


def lab_state_path(sofia_state_path: str | Path) -> Path:
    path = Path(sofia_state_path)
    if not path.name or path.name in (".", ".."):
        raise ValueError("A valid Sofia state-file path is required.")
    return path.with_name(f"{path.stem}-lab.db")


def provision_starter_lab(world: LabWorld) -> None:
    """Author an opt-in starter room, actor, tool and equipment only.

    No actor is placed in the room without an explicit enter operation.
    This does not spawn real objects, grant actions or run the test simulator.
    """
    if not isinstance(world, LabWorld):
        raise TypeError("A real persistent LabWorld is required.")
    existing = world.snapshot()
    room_map = {row[0]: row[1] for row in existing["rooms"]}
    actor_map = {row[0]: row[1] for row in existing["actors"]}
    objects = {row[0]: row for row in existing["objects"]}
    if "lab" in room_map and room_map["lab"] != "Lab":
        raise ValueError("The lab room ID already has a different definition.")
    if "sofia" not in actor_map:
        world.add_actor("sofia")
    if "lab" not in room_map:
        world.add_room("lab", "Lab")
    for object_id, name, kind in (
        ("screwdriver", "Screwdriver", "tool"),
        ("scope", "Oscilloscope", "equipment"),
    ):
        if object_id in objects:
            row = objects[object_id]
            if row[1:4] != (name, kind, "lab"):
                raise ValueError(f"Existing virtual object {object_id} conflicts with starter layout.")
        else:
            world.add_object(object_id, name, kind, "lab")
