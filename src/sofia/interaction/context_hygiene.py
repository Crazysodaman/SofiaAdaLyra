"""Keep legacy automatically labeled gesture cues out of live model context.

Older cue events remain in the user's SQLite history. They described USER input
but were automatically assigned Sofía's affection/appreciation/playfulness.
That assignment is not evidence of her response, preference, or consent.
This filter changes only provider-bound SYSTEM projections, never stored data,
user messages, evidence-backed manually reviewed events, or permissions.
"""
from __future__ import annotations

import json

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole

_LEGACY_DESCRIPTION = 'User initiated an affectionate or playful conversational cue.'
_TRUSTED_HEADINGS = (
    'MODELED EMOTIONAL CONTEXT (',
    'RECORDED REFLECTIONS (',
)


def without_legacy_auto_affection(request: CognitiveRequest) -> CognitiveRequest:
    """Omit only identified unreviewed auto-cues from generated SYSTEM context.

    Reflection summaries mentioning a legacy cue are omitted as a unit because
    the aggregated labels cannot reliably be separated from other events.
    Malformed or unknown records remain untouched; no general text filtering.
    """
    if not isinstance(request, CognitiveRequest):
        raise TypeError('CognitiveRequest required.')
    cleaned = []
    changed = False
    for message in request.messages:
        if (message.role is not CognitiveRole.SYSTEM
                or not any(heading in message.content for heading in _TRUSTED_HEADINGS)):
            cleaned.append(message)
            continue
        kept = []
        for line in message.content.splitlines(keepends=True):
            if not line.lstrip().startswith('{'):
                kept.append(line)
                continue
            try:
                data = json.loads(line)
            except (TypeError, ValueError):
                kept.append(line)
                continue
            if (isinstance(data, dict)
                    and (data.get('event') == _LEGACY_DESCRIPTION
                         or (isinstance(data.get('reflection'), str)
                             and _LEGACY_DESCRIPTION in data['reflection']))):
                changed = True
                continue
            kept.append(line)
        content = ''.join(kept)
        if content != message.content:
            cleaned.append(CognitiveMessage(role=CognitiveRole.SYSTEM, content=content))
        else:
            cleaned.append(message)
    if not changed:
        return request
    return CognitiveRequest(messages=tuple(cleaned), tools=request.tools)
