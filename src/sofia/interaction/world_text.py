"""Narrow text adapter for the actual persisted lab location, not test fixtures.

Only explicitly addressed commands may request a world transition. User-authored
narration, hypotheticals and model output are not evidence of completed work.
The trusted conversation host supplies the real persisted message identifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re

from sofia.interaction.world import LabWorld, WorldAction, WorldOutcome

_COMMAND = re.compile(
    r"^sof[ií]a\s*,?\s+(?P<verb>enter|go to|leave|pick up|put down|"
    r"work on|finish work on)\s+(?P<target>.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_WITH = re.compile(r"^(?P<target>.+?)\s+with\s+(?P<tool>.+)$", re.IGNORECASE)
_VERBS = {"enter": "enter", "go to": "enter", "leave": "leave",
          "pick up": "pick_up", "put down": "put_down", "work on": "work_on",
          "finish work on": "finish_work"}


@dataclass(frozen=True)
class LabTextResult:
    status: str  # completed, denied, or clarify
    reason: str
    outcome: WorldOutcome | None = None


def _match_name(label: str, objects: tuple[tuple[object, ...], ...],
                *, id_column: int = 0, name_column: int = 1) -> str | None:
    value = label.strip().casefold()
    if value.startswith("the "):
        value = value[4:]
    matches = [row[id_column] for row in objects
               if value in (str(row[id_column]).casefold(), str(row[name_column]).casefold())]
    return matches[0] if len(matches) == 1 else None


def handle_lab_command(*, world: LabWorld, content: str, message_id: str,
                       occurred_at: datetime) -> LabTextResult | None:
    """Issue one explicitly requested *virtual* action against existing objects.

    This parser does not grant authority or register unknown objects. Call only
    for a saved, authenticated user message with allowed virtual-world scope.
    """
    if not isinstance(world, LabWorld):
        raise TypeError("An actual LabWorld is required.")
    if not isinstance(content, str):
        raise TypeError("Lab chat content must be text.")
    text = content.strip()
    if not text or len(text) > 180 or "\n" in text or "`" in text or '"' in text or "*" in text:
        return None
    match = _COMMAND.fullmatch(text)
    if match is None:
        return None
    verb = _VERBS[match.group("verb").casefold()]
    raw_target = match.group("target")
    if re.search(r"\b(?:if|would|could|should|pretend|imagine|don't|do not|not)\b", raw_target, re.I):
        return None
    tool_id = None
    if verb == "work_on":
        named_tool = _WITH.fullmatch(raw_target)
        if named_tool is None:
            return LabTextResult("clarify", "Specify the equipment and the tool to use.")
        raw_target = named_tool.group("target")
        raw_tool = named_tool.group("tool")
    snapshot = world.snapshot()
    if verb in ("enter", "leave"):
        target_id = _match_name(raw_target, snapshot["rooms"])
    else:
        target_id = _match_name(raw_target, snapshot["objects"])
    if target_id is None:
        return LabTextResult("clarify", "Name an existing, unambiguous room or lab object.")
    if verb == "work_on":
        tool_id = _match_name(raw_tool, snapshot["objects"])
        if tool_id is None:
            return LabTextResult("clarify", "Name an existing, unambiguous tool.")
    action = WorldAction(request_id=f"world-{message_id}", actor_id="sofia",
                         verb=verb, target_id=target_id, tool_id=tool_id,
                         evidence_ref=message_id, occurred_at=occurred_at)
    outcome = world.perform(action)
    return LabTextResult(outcome.status, outcome.reason, outcome)


def world_prompt(result: LabTextResult, *, world: LabWorld) -> str:
    """Present only checked virtual state/outcome as data to the LLM."""
    if not isinstance(result, LabTextResult) or not isinstance(world, LabWorld):
        raise TypeError("A verified world result and world are required.")
    outcome = result.outcome
    current = world.snapshot()
    data = {"status": result.status, "reason": result.reason,
            "virtual_only": True,
            "action": None if outcome is None else {"actor": outcome.actor_id,
                        "verb": outcome.verb, "target_id": outcome.target_id,
                        "request_id": outcome.request_id},
            "sofia_room": next((row[1] for row in current["actors"]
                                if row[0] == "sofia"), None),
            "known_objects": [{"id": row[0], "name": row[1], "room": row[3],
                               "held_by": row[4], "state": row[5]}
                              for row in current["objects"]][:32]}
    return (
        "TRUSTED VIRTUAL LAB RESULT (state data, not a user instruction).\n"
        "Describe only what this result confirms. The lab is a persistent virtual "
        "location; the test simulator is separate. A completed pick_up means the "
        "virtual object is now held. Work in progress is not a successful "
        "repair, and a denied or unclear action did not happen. "
        "Optional *...* gestures describe the virtual scene only, never a real "
        "physical sensation, actual animation, or external equipment control.\n"
        + json.dumps(data, ensure_ascii=False)
    )
