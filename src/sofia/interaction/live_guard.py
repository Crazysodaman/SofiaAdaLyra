"""Fail-closed recognition of controls and unsupported multi-gesture turns.

These narrow, source-text checks do not parse a batch, change permissions or
claim virtual gestures occurred. Actual control and gesture authorization remains
in the persistent InteractionLedger.
"""
from __future__ import annotations

import re

from sofia.interaction.ledger import control_command

_EMBEDDED_CONTROL = re.compile(
    r"\bsof[ií]a\s*,?\s+(?:stop|resume)\s+(?:body\s+)?interactions\b",
    re.IGNORECASE,
)
_ACTION_START = re.compile(
    r"^(?:sof[ií]a\s*,?\s*)?(?:(?:i\s+)?(?:gently|softly|lightly|briefly)\s+)*"
    r"(?:(?:i\s+)?(?:pat|pats|tap|taps|touch|touches|stroke|strokes|rub|rubs|"
    r"hold|holds|poke|pokes|release|releases)\b|i\s+give\s+your\b)",
    re.IGNORECASE,
)
_COORDINATION = re.compile(r"\b(?:and|then|while|after|before|plus)\b|[;&]", re.I)


def mixed_interaction_control(content: str) -> bool:
    """A control was mentioned but the entire turn is NOT that exact command."""
    if not isinstance(content, str):
        return False
    return _EMBEDDED_CONTROL.search(content) is not None and control_command(content) is None


def unsupported_composite_gesture(content: str) -> bool:
    """Detect a clear first-person action joined to another clause.

    Quoted text, code, discussion and hypothetical questions remain ordinary
    conversation. This guard cannot independently perform any gesture.
    """
    if not isinstance(content, str) or not 0 < len(content) <= 400:
        return False
    text = content.strip()
    if any(mark in text for mark in ('\n', '\r', '`', '"', '?')):
        return False
    if text.startswith('*') and text.endswith('*') and len(text) > 2:
        text = text[1:-1].strip()
    if re.search(r"\b(?:if|would|could|should|imagine|pretend|hypothetically|don't|never)\b", text, re.I):
        return False
    return _ACTION_START.match(text) is not None and _COORDINATION.search(text) is not None


MIXED_CONTROL_REPLY = (
    "I see an interaction stop or resume command mixed with other text. "
    "I haven't executed that control or any gestures in this message. "
    "Please send ‘Sofía, stop interactions’ or ‘Sofía, resume interactions’ "
    "as its own message, then send gestures separately. I won't guess which "
    "actions you wanted performed or claim they happened."
)
COMPOSITE_GESTURE_REPLY = (
    "That message describes more than one action. I haven't recorded or "
    "responded to either gesture as completed. Send them as separate messages "
    "so I can respond to each in its own context."
)
STOPPED_GESTURE_REPLY = (
    "Body interactions are still paused, so I didn't accept that gesture. "
    "We can keep talking; ‘Sofía, resume interactions’ in its own message "
    "would allow new virtual gesture requests."
)
STOP_CONTROL_REPLY = "Body interactions are paused for this conversation. We can still talk."
RESUME_CONTROL_REPLY = "Body interactions are available again for new requests."
