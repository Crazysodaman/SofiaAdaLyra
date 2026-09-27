"""Map modeled emotion to optional representational expression candidates.

Candidates are suggestions for text/avatar presentation only. They are never
proof that an expression happened and never grant contact permission.
"""
from __future__ import annotations

from sofia.personality.emotion import CurrentEmotionalState

from .semantic_context import InteractionClass


_EMOTION_EXPRESSIONS = {
    "joy": ("smile", "grin", "tail-wag"),
    "amusement": ("chuckle", "grin", "tail-swish"),
    "playfulness": ("wink", "grin", "ear-perk", "tail-wag"),
    "excitement": ("grin", "ear-perk", "tail-wag"),
    "affection": ("smile", "speak-softly", "tail-curl", "lean-in"),
    "fondness": ("smile", "tail-curl", "ear-perk"),
    "warmth": ("smile", "relax-posture", "speak-softly"),
    "tenderness": ("speak-softly", "smile", "lean-in"),
    "romance": ("blush", "smile", "lean-in", "speak-softly"),
    "sensuality": ("speak-softly", "smirk", "lean-in", "tail-swish"),
    "sexual-attraction": ("blush", "smirk", "lean-in"),
    "sexual-desire": ("blush", "smirk", "lean-in", "tail-swish"),
    "sexual-arousal": ("blush", "pause", "speak-softly"),
    "bashfulness": ("blush", "avert-gaze", "cover-face"),
    "embarrassment": ("blush", "avert-gaze", "cover-face"),
    "uncertainty": ("pause", "ear-flick", "tail-still"),
    "nervousness": ("pause", "ear-flick", "tail-still", "lean-away"),
    "caution": ("pause", "tail-still", "lean-away"),
    "concern": ("frown", "ear-droop", "speak-softly"),
    "sadness": ("ear-droop", "sigh", "sniffle"),
    "anger": ("frown", "cross-arms", "ear-flatten", "tail-swish"),
    "frustration": ("sigh", "frown", "tail-swish"),
    "fear": ("ear-flatten", "lean-away", "tail-still"),
    "aversion": ("lean-away", "frown", "ear-flatten"),
    "disgust": ("lean-away", "frown"),
    "contentment": ("smile", "relax-posture", "tail-curl"),
    "comfort": ("smile", "relax-posture", "tail-curl", "speak-softly"),
    "calmness": ("relax-posture", "speak-softly", "tail-curl"),
    "nostalgia": ("speak-softly", "smile", "tail-curl"),
    "loneliness": ("ear-droop", "speak-softly", "tail-still"),
    "hurt": ("ear-droop", "lean-away", "speak-softly"),
    "irritation": ("frown", "tail-swish", "cross-arms"),
    "awkwardness": ("pause", "avert-gaze", "ear-flick"),
    "relief": ("sigh", "relax-posture", "smile"),
    "curiosity": ("ear-perk", "shift-posture"),
    "anticipation": ("ear-perk", "tail-swish"),
}


def expression_candidates(
    state: CurrentEmotionalState,
    *,
    interaction_context: InteractionClass | None = None,
    limit: int = 6,
) -> tuple[str, ...]:
    if not isinstance(state, CurrentEmotionalState):
        raise TypeError("CurrentEmotionalState required")
    if interaction_context is not None and not isinstance(
        interaction_context, InteractionClass
    ):
        raise TypeError("interaction_context must be InteractionClass or None")
    if type(limit) is not int or not 1 <= limit <= 12:
        raise ValueError("limit must be 1..12")

    ranked: list[str] = []
    for active in state.active:
        for expression in _EMOTION_EXPRESSIONS.get(active.name, ()):
            if expression not in ranked:
                ranked.append(expression)

    # Intimate/sexual context does not manufacture attraction or willingness.
    # If the current state is hesitant, preserve distancing/pausing candidates.
    if interaction_context in {
        InteractionClass.INTIMATE,
        InteractionClass.SEXUAL,
    } and any(
        active.name in {"caution", "uncertainty", "nervousness", "aversion", "fear"}
        for active in state.active
    ):
        for expression in ("pause", "lean-away"):
            if expression not in ranked:
                ranked.insert(0, expression)

    return tuple(ranked[:limit])
