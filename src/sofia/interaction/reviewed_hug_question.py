"""Narrow, non-executing classification for ambiguous hug QUESTIONS.

A question about a possible hug is not the same as a reviewed avatar
ACTION, permission, consent, a claim of physical contact or a sensor query.
Only these complete, independently reviewed sentences are in scope.
"""
from __future__ import annotations

import re

_QUESTION = re.compile(
    r'(?:could|can|may) i (?:hug you|give you a hug)\?', re.IGNORECASE,
)


def is_reviewed_hug_question(content: str) -> bool:
    """Accept only one full question; reject compounds and qualified actions."""
    return isinstance(content, str) and _QUESTION.fullmatch(content) is not None


CLARIFICATION = (
    'Do you mean a hug in our avatar scene, or are you asking about '
    'real-world contact?'
)
