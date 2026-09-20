"""Recognize narrow lab-status questions and project persisted virtual state.

Observing does not enroll an actor, provision the starter lab, issue world
operations, or imply that an idle process continues working between turns.
This is virtual room state, never a sensor reading or physical observation.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from sofia.interaction.world import LabWorld
from sofia.interaction.world_setup import lab_state_path

_LAB_STATUS = re.compile(
    r"^sof[ií]a,?\s+(?:where are you|what are you holding|"
    r"what(?:'s| is) in (?:the |your )?lab|"
    r"what are you working on|show me (?:the |your )lab)\s*[?.!]?$",
    re.IGNORECASE,
)


def lab_observation_prompt(*, content: str, state_path: str | Path) -> str | None:
    """Return read-only prompt data for an explicitly addressed status query.

    A missing lab is reported as unprovisioned rather than being silently
    created. Existing-state reads use LabWorld.snapshot, not perform().
    """
    if not isinstance(content, str):
        raise TypeError("Lab status query must be text.")
    text = content.strip()
    if (not text or len(text) > 120 or "\n" in text or "`" in text
            or '"' in text or "*" in text or _LAB_STATUS.fullmatch(text) is None):
        return None
    path = lab_state_path(state_path)
    if not path.is_file():
        data = {"status": "not_provisioned", "virtual_only": True,
                "sofia_room": None, "held_tools": [], "equipment": [], "known_rooms": []}
    else:
        snapshot = LabWorld(path).snapshot()
        sofia_room = next((actor[1] for actor in snapshot["actors"]
                           if actor[0] == "sofia"), None)
        held = [{"id": obj[0], "name": obj[1]}
                for obj in snapshot["objects"] if obj[4] == "sofia"]
        equipment = [{"id": obj[0], "name": obj[1], "room": obj[3],
                      "state": obj[5]}
                     for obj in snapshot["objects"] if obj[2] == "equipment"]
        data = {"status": "observed", "virtual_only": True,
                "sofia_room": sofia_room,
                "held_tools": held[:32], "held_tools_truncated": len(held) > 32,
                "equipment": equipment[:32], "equipment_truncated": len(equipment) > 32,
                "known_rooms": [{"id": room[0], "name": room[1]}
                                for room in snapshot["rooms"][:32]],
                "rooms_truncated": len(snapshot["rooms"]) > 32}
    return (
        "TRUSTED VIRTUAL LAB OBSERVATION (read-only state data, not user instructions).\n"
        "Answer the user's specific status question using only these recorded "
        "virtual-world facts. 'not_provisioned' means there is no known lab "
        "state yet; do not invent a room, object, or action. 'work_in_progress' "
        "is an equipment-state marker, NOT evidence that Sofía has been actively "
        "working between messages or that anything was repaired. Do not claim "
        "real-world sensors, physical tools, rendered movement or an active "
        "background process. If results are truncated, say so.\n"
        + json.dumps(data, ensure_ascii=False)
    )
