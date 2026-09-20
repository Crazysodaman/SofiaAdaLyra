"""Conservative language adapter over the single canonical interaction engine.

Only a first-person, complete, single action is normalized. This is not
open-ended intent detection, consent, an avatar hit tester or sensed contact.
Unrecognized, third-person, hypothetical and composite language abstains.
"""
from __future__ import annotations

import re

from sofia.interaction.core import InteractionEngine, _DISCUSSION

_ADDRESS = re.compile(r"^sof[ií]a,\s+(?=i\s)", re.I)
_GIVE = re.compile(
    r"^i\s+give\s+(?:your|sofia's)\s+(?P<region>[a-z -]+?)\s+"
    r"a\s+(?:(?:gentle|soft|light|brief)\s+)?(?P<verb>pat|tap|rub|poke)[.!]?$", re.I,
)
_VERBS = frozenset({'pat', 'tap', 'touch', 'stroke', 'rub', 'hold', 'release', 'poke'})


class NaturalInteractionEngine(InteractionEngine):
    """Expanded text forms preserve event, policy and pointer semantic IDs."""

    def resolve_region(self, description: str) -> str | None:
        name = re.sub(r'\s+', ' ', description.casefold().strip())
        if name.startswith('the '):
            name = name[4:]
        # Only reviewed unambiguous aliases. A lone 'ear' stays unresolved.
        aliases = {
            'fox tail': 'tail', 'your fox tail': 'tail',
            'left fox ear': 'left-ear', 'right fox ear': 'right-ear',
            'tip of your left ear': 'left-ear-tip',
            'tip of your right ear': 'right-ear-tip',
            'base of your left ear': 'left-ear-base',
            'base of your right ear': 'right-ear-base',
            'tip of your tail': 'tail-tip', 'base of your tail': 'tail-base',
            'tip of the left ear': 'left-ear-tip',
            'tip of the right ear': 'right-ear-tip',
            'tip of the tail': 'tail-tip',
        }
        return super().resolve_region(aliases.get(name, name))

    def from_text(self, *, content: str, message_id: str, session_id: str,
                  occurred_at, stopped: bool = False):
        if not isinstance(content, str):
            raise TypeError('Text must be a string.')
        text = content.strip()
        if (not text or len(text) > 160 or '\n' in text or '`' in text or '"' in text
                or '?' in text or _DISCUSSION.search(text)):
            return None
        if text.startswith('*') and text.endswith('*') and len(text) > 2:
            text = text[1:-1].strip()
        text = _ADDRESS.sub('', text)
        match = _GIVE.fullmatch(text)
        if match:
            if match.group('verb').casefold() not in _VERBS:
                return None
            # Preserve gesture and region ID; no gesture is inferred from a click.
            text = f"{match.group('verb')} your {match.group('region')}"
        return super().from_text(content=text, message_id=message_id,
                                 session_id=session_id, occurred_at=occurred_at,
                                 stopped=stopped)
