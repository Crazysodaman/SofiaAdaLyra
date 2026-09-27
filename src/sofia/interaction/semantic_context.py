"""Shared interaction-context classification.

This classifies represented interaction semantics only. It does not establish
consent, preference, arousal, relationship status, physical sensation, or any
real-world action.
"""
from __future__ import annotations

from enum import Enum


class InteractionClass(str, Enum):
    NEUTRAL = "neutral"
    AFFECTIONATE = "affectionate"
    ROMANTIC = "romantic"
    INTIMATE = "intimate"
    SEXUAL = "sexual"


_PRIVATE_REGION_TOKENS = (
    "breast",
    "chest",
    "buttocks",
    "groin",
    "genitals",
    "inner-thigh",
)

_AFFECTIONATE = frozenset({
    "hug",
    "cuddle",
    "nuzzle",
    "hold-hands",
    "hold-close",
    "arm-around",
    "rest-head-on-shoulder",
    "sit-in-lap",
})

_ROMANTIC = frozenset({
    "kiss",
    "flirt",
    "dance-with",
})

_INTIMATE = frozenset({
    "intimate-touch",
    "intimate-contact",
})

_SEXUAL = frozenset({
    "sexual-contact",
})

_INTIMATE_GESTURES = frozenset({
    "caress",
    "cup",
    "grab",
    "intimate-touch",
    "kiss",
    "massage",
    "rub",
    "squeeze",
    "stroke",
    "touch",
})


def interaction_class(
    semantic_id: str,
    *,
    region_id: str | None = None,
) -> InteractionClass:
    if not isinstance(semantic_id, str) or not semantic_id.strip():
        raise ValueError("semantic_id must be nonempty")
    if region_id is not None and (
        not isinstance(region_id, str) or not region_id.strip()
    ):
        raise ValueError("region_id must be nonempty or None")

    semantic = semantic_id.strip()
    if semantic in _SEXUAL:
        return InteractionClass.SEXUAL
    if semantic in _INTIMATE:
        return InteractionClass.INTIMATE
    if semantic in _ROMANTIC:
        return InteractionClass.ROMANTIC
    if semantic in _AFFECTIONATE:
        return InteractionClass.AFFECTIONATE

    if (
        region_id is not None
        and any(token in region_id for token in _PRIVATE_REGION_TOKENS)
        and semantic in _INTIMATE_GESTURES
    ):
        # Private anatomy plus a contact gesture is intimate context, but never
        # automatically sexual and never evidence of desire or consent.
        return InteractionClass.INTIMATE

    return InteractionClass.NEUTRAL


_NONCONTACT_ACTIONS = frozenset({
    "move-away",
    "give-space",
    "decline",
    "offer-hand",
    "offer-tool",
    "ask-permission",
})


def requires_contact_permission(semantic_id: str) -> bool:
    """Conservative initiative gate for Sofía-originated represented actions."""
    if not isinstance(semantic_id, str) or not semantic_id.strip():
        raise ValueError("semantic_id must be nonempty")
    return semantic_id not in _NONCONTACT_ACTIONS
