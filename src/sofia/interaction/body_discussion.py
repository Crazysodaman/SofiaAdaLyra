"""Read-only grounding for explicit questions about represented body gestures.

This is intentionally NOT an action parser. It never stores an event, treats a
hypothetical as touch, or infers consent from a discussion of anatomy.
"""
from __future__ import annotations

import json
import re

from sofia.interaction.core import InteractionEngine

_ACTION_WORD = re.compile(r'\b(?:pat|pats|patting|rub|rubs|rubbing|touch|touches|touching|stroke|strokes|stroking|tap|taps|tapping|poke|pokes|poking|hold|holds|holding)\b', re.I)


def body_discussion_prompt(*, content: str, engine: InteractionEngine) -> str | None:
    """Project canonical region policy for a question; execute nothing."""
    if not isinstance(content, str) or '?' not in content or len(content) > 400:
        return None
    if _ACTION_WORD.search(content) is None:
        return None
    # Match verified canonical names, longest first, and an explicitly
    # unresolved ear. Never derive body regions from free-form model text.
    names = sorted((region_id.replace('-', ' ') for region_id in engine.regions),
                   key=len, reverse=True)
    options = '|'.join(re.escape(name) for name in [*names, 'ear'])
    pattern = re.compile(r'\byour\s+(?:fox\s+)?(?P<region>' + options + r')\b', re.I)
    seen: set[str] = set()
    regions = []
    for match in pattern.finditer(content):
        named = match.group('region')
        resolved = engine.resolve_region(named)
        key = resolved or named.casefold()
        if key in seen:
            continue
        seen.add(key)
        region = engine.regions.get(resolved)
        regions.append({
            'region_id': resolved,
            'policy': 'restricted' if region is not None and region.private else
                      ('ordinary_requires_new_explicit_single_action' if region is not None
                       else 'ambiguous_or_unknown'),
        })
    if not regions:
        return None
    return (
        'TRUSTED REPRESENTATIONAL BODY DISCUSSION (read-only; no action executed)\n'
        'This message includes a question about gestures, not a completed gesture. '
        'No head rub, tail pat, chest rub, stop or resume has been executed by '
        'this question; do not imply otherwise. Sofía has a canonical represented '
        'body with fox ears and tail, even without a visual renderer. Answer '
        'the actual question conversationally and in character. Do not erase '
        'her represented form or repeatedly explain that an AI lacks physical '
        'sensation. Ordinary-region interactions need a NEW separately issued '
        'explicit action, and no positive emotion is guaranteed. Restricted '
        'regions are denied with current policy, even hypothetically discussed. '
        'No physical sensations or rendered animations can be claimed.\n'
        + json.dumps({'question_only': True, 'actions_executed': False,
                      'regions': regions}, ensure_ascii=False)
    )
