"""Fail-closed recognition of control commands embedded in longer user turns.

This does not parse batches or grant any permissions. A partial mention of an
interaction control cannot be reported as executed by the conversation model.
"""
from __future__ import annotations

import re

from sofia.interaction.ledger import control_command

_EMBEDDED_CONTROL = re.compile(
    r"\bsof[ií]a\s*,?\s+(?:stop|resume)\s+(?:body\s+)?interactions\b",
    re.IGNORECASE,
)


def mixed_interaction_control(content: str) -> bool:
    """A control was mentioned but the entire turn is NOT that exact command."""
    if not isinstance(content, str):
        return False
    return _EMBEDDED_CONTROL.search(content) is not None and control_command(content) is None


MIXED_CONTROL_REPLY = (
    "I see an interaction stop or resume command mixed with other text. "
    "I haven't executed that control or any gestures in this message. "
    "Please send ‘Sofía, stop interactions’ or ‘Sofía, resume interactions’ "
    "as its own message, then send gestures separately. I won't guess which "
    "actions you wanted performed or claim they happened."
)
