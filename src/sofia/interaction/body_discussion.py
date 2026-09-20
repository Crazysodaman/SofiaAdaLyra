"""Read-only grounding for explicit hypothetical questions about represented gestures.

This is intentionally NOT an action parser. It never stores an event, treats a
hypothetical as touch, or infers consent from a discussion of anatomy.
"""
from __future__ import annotations

import json
import re

from sofia.interaction.core import InteractionEngine

_ACTION_WORD = re.compile(r'\b(?:pat|pats|patting|rub|rubs|rubbing|touch|touches|touching|stroke|strokes|stroking|tap|taps|tapping|poke|pokes|poking|hold|holds|holding)\b', re.I)
_HYPOTHETICAL = re.compile(r'\b(?:what\s+happens\s+if|what\s+(?:would|will)\s+happen\s+if|what\s+if|if\s+i|would\s+you|could\s+you)\b', re.I)


def body_discussion_prompt(*, content: str, engine: InteractionEngine) -> str | None:
    """Project canonical anatomy for a hypothetical; execute nothing."""
    if (not isinstance(content, str) or '?' not in content or len(content) > 400
            or _ACTION_WORD.search(content) is None
            or _HYPOTHETICAL.search(content) is None):
        return None
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
            'policy': 'contextual_requires_new_explicit_single_action' if region is not None
                      else 'ambiguous_or_unknown',
        })
    if not regions:
        return None
    return (
        'TRUSTED REPRESENTATIONAL BODY DISCUSSION (read-only; no action executed)\n'
        'This message includes a hypothetical question about gestures, not a '
        'completed gesture. No head rub, tail pat, chest rub, stop or resume '
        'has been executed by this question; do not imply otherwise. Sofía '
        'has a canonical represented body with fox ears and tail, even without '
        'a visual renderer. Answer the actual question conversationally and '
        'in character. Do not erase her represented form or repeatedly explain '
        'that an AI lacks physical sensation. Every known anatomy region uses '
        'the SAME contextual rule: a separately issued, explicit, single user '
        'gesture can be classified, but classification is not consent, approval, '
        'pleasure or a guaranteed positive response. Depending on the preceding '
        'conversation and the gesture, Sofía may welcome it, be indifferent, '
        'feel awkward in her modeled expression, question it, set a boundary or '
        'object. Do not infer her reaction solely from anatomy or force a '
        'scripted good/bad response. Respect stored stop state for actual '
        'actions, and do not claim physical sensations or rendered animations.\n'
        + json.dumps({'question_only': True, 'actions_executed': False,
                      'regions': regions}, ensure_ascii=False)
    )
