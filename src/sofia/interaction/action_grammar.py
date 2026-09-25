"""Reviewed, non-executing whole-body/social action language classifier.

Only a complete first-person sentence from a saved user turn qualifies.
The resulting intent describes what the USER wrote, not a performed action,
Sofía's consent, physical presence or a user-authorized tool operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.interaction.registry import ACTION_DEFINITIONS, CATALOG_VERSION

_ACTIONS = frozenset(item.id for item in ACTION_DEFINITIONS)
_DISCUSSION = re.compile(r"\b(?:not|never|don't|would|could|should|if|imagine|pretend|hypothetically)\b", re.I)
_COMPOSITE = re.compile(r"\b(?:and|then|while|before|after|plus)\b|[;&]", re.I)
_ADDRESS = re.compile(r"^sof[ií]a,\s+", re.I)
# Each phrase is reviewed independently. No catchall `I <verb> you` fallback.
_PHRASES: dict[str, tuple[str, str]] = {
    'hug you': ('hug', 'described'),
    'embrace you': ('hug', 'described'),
    'cuddle you': ('cuddle', 'described'),
    'snuggle with you': ('cuddle', 'described'),
    'lean against you': ('lean-on', 'described'),
    'sit beside you': ('sit-beside', 'described'),
    'sit next to you': ('sit-beside', 'described'),
    'sit in your lap': ('sit-in-lap', 'described'),
    'move closer': ('move-closer', 'described'),
    'step closer': ('move-closer', 'described'),
    'move away': ('move-away', 'described'),
    'step away': ('move-away', 'described'),
    'give you space': ('give-space', 'described'),
    'offer you my hand': ('offer-hand', 'offered'),
    'offer my hand': ('offer-hand', 'offered'),
    'hold hands with you': ('hold-hands', 'described'),
    'offer you a tool': ('offer-tool', 'offered'),
    'help you in the lab': ('help-in-lab', 'offered'),
    'ask to hug you': ('hug', 'offered'),
    'ask to cuddle you': ('cuddle', 'offered'),
}
if any(action not in _ACTIONS for action, _ in _PHRASES.values()):
    raise RuntimeError('Action grammar refers to a missing catalog definition.')


@dataclass(frozen=True)
class ActionIntent:
    message_id: str
    actor: str
    target: str
    action_id: str
    modality: str  # described or offered; neither means executed
    registry_version: str = CATALOG_VERSION


def parse_user_action(content: str, *, message_id: str) -> ActionIntent | None:
    """Return None when language is not an exactly reviewed user action."""
    if not isinstance(content, str):
        raise TypeError('Action message must be text.')
    if not isinstance(message_id, str) or not message_id.strip() or len(message_id) > 120:
        raise ValueError('A bounded saved-message ID is required.')
    text = content.strip()
    if (not text or len(text) > 160 or any(c in text for c in ('\n', '\r', '`', '"', '?'))
            or text.startswith("'") or text.endswith("'") or _DISCUSSION.search(text)):
        return None
    if text.startswith('*') and text.endswith('*'):
        text = text[1:-1].strip()
    text = _ADDRESS.sub('', text)
    if _COMPOSITE.search(text):
        return None
    match = re.fullmatch(r'i\s+(.+?)[.!]?', text, re.I)
    if match is None:
        return None
    normalized = re.sub(r'\s+', ' ', match.group(1).casefold()).strip()
    resolved = _PHRASES.get(normalized)
    if resolved is None:
        return None
    action_id, modality = resolved
    return ActionIntent(message_id, 'user', 'sofia', action_id, modality)
