"""Conservative v2 grammar over the canonical representational body engine.

Only one complete user-described action can be classified. Discussion, quotes,
negation, unrecognized verbs and composites abstain. This is neither physical
sensing nor consent; the durable ledger remains the authority for stop/replay.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from sofia.interaction.core import (
    InteractionEngine, InteractionEvent, _DISCUSSION,
)
from sofia.interaction.registry import (
    CATALOG_VERSION, GESTURE_DEFINITIONS, catalog_for_engine,
    normalize_alias,
)

_ADDRESS = re.compile(r"^sof[ií]a,\s+(?=i\s)", re.I)
_GIVE = re.compile(
    r"^i\s+give\s+(?:your|sofia's)\s+(?P<region>[a-z -]+?)\s+"
    r"a\s+(?:(?:gentle|soft|light|brief)\s+)?(?P<verb>pat|tap|rub|poke)[.!]?$", re.I,
)
_VERBS = frozenset({'pat', 'tap', 'touch', 'stroke', 'rub', 'hold', 'release', 'poke'})
_COMPOSITE = re.compile(r'\b(?:and|then|while|after|before|plus)\b|[;&]', re.I)
# This is a spoken preface, not a second gesture. Require an immediately
# following, explicitly addressed single gesture; do not strip arbitrary prose.
_PRAISE_PREFIX = re.compile(
    r'^good\s+girl,\s+(?=(?:(?:gently|softly|lightly|briefly)\s+)?'
    r'(?:pats?|taps?|touch(?:es)?|strokes?|rubs?|holds?|pokes?)\s+'
    r'(?:your|her|sofia\'s|the)\s+)', re.I,
)
# The standalone shorthand is intentionally restricted to this explicit verb.
# It is never a generic unknown-verb or intimate-action fallback.
_TELEGRAPHIC_GROPE = re.compile(
    r'^(?:grope|gropes|groping)\s+(?:your|her|sofia\'s|the)\s+'
    r'(?P<region>[a-z -]+?)[.!]?$', re.I,
)
_NEW_VERB_ALIASES = {
    normalize_alias(alias): definition.id
    for definition in GESTURE_DEFINITIONS if definition.id not in _VERBS
    for alias in (definition.id, *definition.aliases)
    if ' ' not in normalize_alias(alias)
}
# Reviewed explicit language: map to the existing intimate-touch semantic ID,
# not to generic touch or physical execution. No new registry ID is inferred.
_NEW_VERB_ALIASES.update({'grope': 'intimate-touch',
                          'gropes': 'intimate-touch',
                          'groping': 'intimate-touch'})
_NEW_ACTION = re.compile(
    r"^i\s+(?:(?:gently|softly|lightly|briefly)\s+)?"
    r"(?P<verb>" + '|'.join(re.escape(v) for v in sorted(_NEW_VERB_ALIASES, key=len, reverse=True)) + r")\s+"
    r"(?:(?:your|her|sofia's|the)\s+)?(?P<region>[a-z -]+?)"
    r"(?:\s+(?:gently|softly|lightly|briefly))?[.!]?$",
    re.IGNORECASE,
)


class NaturalInteractionEngine(InteractionEngine):
    """Expanded recognized names/verbs, unchanged v1 storage and stop gate."""

    def resolve_region(self, description: str) -> str | None:
        name = re.sub(r'\s+', ' ', description.casefold().strip())
        if name.startswith('the '):
            name = name[4:]
        aliases = {
            'fox tail': 'tail', 'your fox tail': 'tail',
            'butt': 'buttocks',
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
        old = super().resolve_region(aliases.get(name, name))
        if old is not None:
            return old
        try:
            resolution = catalog_for_engine(self).resolve_region(name)
        except ValueError:
            return None
        return resolution.canonical_id if resolution.status == 'resolved' else None

    def from_text(self, *, content: str, message_id: str, session_id: str,
                  occurred_at: datetime, stopped: bool = False):
        if not isinstance(content, str):
            raise TypeError('Text must be a string.')
        text = content.strip()
        if (not text or len(text) > 160 or '\n' in text or '`' in text or '"' in text
                or text.startswith("'") or text.endswith("'")
                or '?' in text or _DISCUSSION.search(text)):
            return None
        if text.startswith('*') and text.endswith('*') and len(text) > 2:
            text = text[1:-1].strip()
        text = _ADDRESS.sub('', text)
        if _COMPOSITE.search(text):
            return None
        text = _PRAISE_PREFIX.sub('', text, count=1)
        grope = _TELEGRAPHIC_GROPE.fullmatch(text)
        if grope is not None:
            text = f"i grope your {grope.group('region')}"
        match = _GIVE.fullmatch(text)
        if match:
            if match.group('verb').casefold() not in _VERBS:
                return None
            text = f"{match.group('verb')} your {match.group('region')}"
        # Explicit character possessives denote the same virtual recipient;
        # normalize BEFORE the legacy regex (which excludes apostrophes).
        text = re.sub(r"\bsof[ií]a['’]s\s+", 'your ', text, flags=re.I)
        legacy = super().from_text(content=text, message_id=message_id,
                                   session_id=session_id, occurred_at=occurred_at,
                                   stopped=stopped)
        if legacy is not None:
            return legacy
        match = _NEW_ACTION.fullmatch(text)
        if match is None:
            return None
        gesture = _NEW_VERB_ALIASES[normalize_alias(match.group('verb'))]
        region_id = self.resolve_region(match.group('region'))
        for name, value in (('message_id', message_id), ('session_id', session_id)):
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError(f'{name} needs a bounded identifier.')
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError('An aware event timestamp is required.')
        event = InteractionEvent(
            event_id=f'interaction:{message_id}', session_id=session_id,
            evidence_ref=message_id, source='user_text', actor='user',
            region_id=region_id, gesture=gesture, phase='end',
            occurred_at=occurred_at.astimezone(timezone.utc),
            registry_version=CATALOG_VERSION,
        )
        return self._decide(event, stopped=stopped)

    def from_lab_pointer(self, *, fixture_id: str, session_id: str,
                         region_id: str | None, gesture: str,
                         occurred_at: datetime, phase: str = 'end',
                         stopped: bool = False):
        """Synthetic fixtures use the same v2 IDs; NOT authenticated avatar input."""
        if gesture not in frozenset(_NEW_VERB_ALIASES.values()):
            return super().from_lab_pointer(
                fixture_id=fixture_id, session_id=session_id, region_id=region_id,
                gesture=gesture, occurred_at=occurred_at, phase=phase,
                stopped=stopped)
        for name, value in (('fixture_id', fixture_id), ('session_id', session_id)):
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError(f'{name} needs a bounded identifier.')
        if phase not in ('begin', 'update', 'end', 'cancel'):
            raise ValueError('Unknown gesture phase.')
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError('An aware event timestamp is required.')
        event = InteractionEvent(
            event_id=f'lab:{fixture_id}', session_id=session_id,
            evidence_ref=fixture_id, source='virtual_lab', actor='user',
            region_id=region_id, gesture=gesture, phase=phase,
            occurred_at=occurred_at.astimezone(timezone.utc),
            registry_version=CATALOG_VERSION,
        )
        return self._decide(event, stopped=stopped)
