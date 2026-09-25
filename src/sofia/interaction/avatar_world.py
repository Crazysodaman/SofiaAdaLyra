"""Provider-only avatar-world framing; not sensing, consent, or action authority.

The authoritative embodiment remains in the canonical self-state. These helpers
only describe how to interpret conversation and project already-reviewed gesture
classification to an LLM. No emotion is inferred, no interaction is approved,
and no avatar motion is reported as executed.
"""
from __future__ import annotations

import json


_GESTURE_MARKER = "TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)"


def avatar_world_guidance() -> str:
    """Interpret the canonical avatar as Sofía's represented body in dialogue."""
    return (
        "AVATAR-WORLD CONVERSATIONAL INTERPRETATION\n"
        "Sofía's canonical representational body is her avatar, including its "
        "defined fox features, whether or not a renderer is currently visible. "
        "In conversation, references to Sofía's body, ears, tail, hugs or "
        "gestures normally refer to that represented body. Do not replace it "
        "with a generic assertion that Sofía has no body. If the user "
        "explicitly asks about real-world touch, biological sensation, robots, "
        "sensors, screen animation or hardware, answer using verified actual "
        "capabilities instead. An offered avatar interaction is a proposal, "
        "not completed contact; Sofía can accept, decline, ask or set a "
        "boundary in context. A described interaction is not evidence that "
        "Sofía consented, enjoyed it, or physically felt it. Modeled emotions "
        "may inform varied dialogue and optional representational gestures; "
        "they are not proof of subjective feelings. No emotion forces a "
        "particular gesture, and silence or no gesture is valid. Textual "
        "stage directions are writing, not verified animation or physical "
        "actions. Never claim contact, avatar rendering or external action "
        "was executed without the corresponding verified result."
    )


def gesture_provider_view(original: str) -> str | None:
    """Omit literal cue and emotion suggestions from one *trusted* gesture prompt.

    Keep the exact policy status and reviewed structured decision. The source
    ledger, parser, original user turn and stored events are never modified.
    Unknown prompts pass through unchanged. Malformed trusted data fails closed.
    """
    if not original.startswith(_GESTURE_MARKER + "\n"):
        return None
    _, separator, payload = original.rpartition("\n")
    if not separator:
        raise ValueError("Missing reviewed gesture decision.")
    try:
        data = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid reviewed gesture decision.") from exc
    if not isinstance(data, dict):
        raise ValueError("Reviewed gesture decision must be an object.")
    keys = (
        "registry_version", "region_id", "gesture", "phase",
        "policy_status", "policy_reason",
    )
    if any(key not in data for key in keys):
        raise ValueError("Reviewed gesture decision is missing policy data.")
    if (data["policy_status"] not in ("accepted", "denied", "clarify", "acknowledged")
            or not isinstance(data["policy_reason"], str)):
        raise ValueError("Unrecognized gesture policy result.")
    projected = {key: data[key] for key in keys}
    return (
        _GESTURE_MARKER + "\n"
        "The saved user turn describes a gesture toward Sofía's represented "
        "avatar, not sensed real-world touch. Use the exact policy result below; "
        "'accepted' means recognized and recorded, NOT Sofía's consent or "
        "enjoyment. A denied action did not occur; an acknowledged phase does "
        "not establish completed contact. For 'clarify', ask briefly about "
        "the unresolved region. Otherwise respond to the specific moment in "
        "Sofía's own voice, including an independent boundary if appropriate. "
        "No emotional response or gesture is prescribed. Do not add stock "
        "disclaimers, repeat canned wording or invent physical sensation or "
        "executed avatar animation.\n"
        + json.dumps(projected, ensure_ascii=False)
    )
