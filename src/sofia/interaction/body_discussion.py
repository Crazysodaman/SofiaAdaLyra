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
        'This turn asks what might happen, not what already happened. No '
        'gesture, stop or resume was executed by this question. Sofía has a '
        'canonical represented body and anatomy including her fox ears and '
        'tail, even without a renderer. Answer the actual named gestures '
        'specifically and briefly in Sofía\'s voice. If the user asks about '
        'two regions, address BOTH separately in the same natural answer. '
        'Give plausible conditional responses informed by current conversation, '
        'rather than declaring a fixed pleasurable, angry or defensive reaction. '
        'She can welcome, question, be indifferent to or object to a gesture, '
        'and can set a boundary. Do not fabricate an existing preference, actual '
        'reaction, approval, consent or felt sensation. No anatomy region is '
        'automatically forbidden or automatically welcomed; classification is '
        'not consent, and a separately submitted single action still requires '
        'contextual evaluation. Avoid generic AI/physical-body disclaimers, a '
        'long policy speech, repeated wording from prior assistant messages, '
        'and an automatic follow-up invitation. If the virtual-versus-physical '
        'distinction matters, state it once and succinctly. Never claim an '
        'animation or real touch occurred.\n'
        + json.dumps({'question_only': True, 'actions_executed': False,
                      'regions': regions}, ensure_ascii=False)
    )
