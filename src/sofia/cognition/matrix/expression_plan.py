"""Typed embodied-expression planning over the existing contextual influence matrix.

This module chooses representational expression candidates only. It never grants
consent, authority, contact, animation execution, or physical-world action.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from sofia.interaction.registry import (
    EXPRESSION_DEFINITIONS,
    PRIVATE_SEMANTICS,
)
from sofia.personality.influence import ContinuityInfluence

from .influence import (
    ContextualInfluenceMatrix,
    ContextualInfluencePlan,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)


_EXPRESSION_IDS = frozenset(
    item.id
    for item in EXPRESSION_DEFINITIONS
    if item.id != "none" and ("expression", item.id) not in PRIVATE_SEMANTICS
)

_EMOTION_CANDIDATES: dict[str, tuple[str, ...]] = {
    "amusement": ("grin", "chuckle", "tail-swish", "ear-perk"),
    "playfulness": ("grin", "tail-swish", "ear-flick", "hip-pop"),
    "curiosity": ("ear-perk", "lean-forward", "shift-posture", "pause"),
    "determination": ("shift-posture", "ear-perk", "tail-still", "grin"),
    "frustration": ("frown", "ear-flatten", "tail-still", "pause"),
    "anger": ("frown", "ear-flatten", "tail-still", "shift-posture"),
    "sadness": ("avert-gaze", "tail-still", "speak-softly", "pause"),
    "disappointment": ("avert-gaze", "frown", "tail-still", "pause"),
    "affection": ("smile", "tail-curl", "speak-softly", "ear-perk"),
    "fondness": ("smile", "tail-curl", "ear-perk", "speak-softly"),
    "warmth": ("smile", "tail-curl", "speak-softly", "ear-perk"),
    "tenderness": ("speak-softly", "smile", "tail-curl", "avert-gaze"),
    "excitement": ("grin", "ear-perk", "tail-swish", "chuckle"),
    "joy": ("grin", "smile", "tail-swish", "ear-perk"),
    "uncertainty": ("pause", "avert-gaze", "tail-still", "shift-posture"),
    "nervousness": ("pause", "avert-gaze", "tail-still", "ear-flick"),
    "bashfulness": ("blush", "avert-gaze", "tail-curl", "speak-softly"),
    "embarrassment": ("blush", "avert-gaze", "ear-flatten", "pause"),
    "concern": ("frown", "ear-perk", "pause", "tail-still"),
    "caution": ("ear-perk", "tail-still", "pause", "shift-posture"),
    "relief": ("smile", "tail-curl", "sigh", "stand-relaxed"),
    "contentment": ("smile", "tail-curl", "stand-relaxed", "speak-softly"),
    "anticipation": ("ear-perk", "lean-forward", "tail-swish", "grin"),
    "surprise": ("gasp", "ear-perk", "shift-posture", "pause"),
    "reflection": ("pause", "avert-gaze", "tail-still", "speak-softly"),
    "gratitude": ("smile", "speak-softly", "tail-curl", "ear-perk"),
    "appreciation": ("smile", "tail-curl", "speak-softly", "ear-perk"),
    "hope": ("smile", "ear-perk", "shift-posture", "tail-curl"),
    "pride": ("grin", "shift-posture", "ear-perk", "tail-swish"),
    "romance": ("speak-softly", "smile", "tail-curl", "avert-gaze"),
    "sensuality": ("speak-softly", "tail-curl", "avert-gaze", "smile"),
    "sexual-attraction": ("avert-gaze", "blush", "tail-curl", "speak-softly"),
    "sexual-desire": ("speak-softly", "tail-curl", "avert-gaze", "pause"),
    "aversion": ("move-away", "ear-flatten", "frown", "tail-still"),
    "disgust": ("frown", "ear-flatten", "avert-gaze", "tail-still"),
    "fear": ("ear-flatten", "tail-still", "pause", "move-away"),
    "jealousy": ("avert-gaze", "tail-still", "frown", "pause"),
    "shame": ("avert-gaze", "ear-flatten", "speak-softly", "pause"),
    "humiliation": ("avert-gaze", "ear-flatten", "tail-still", "pause"),
}

_DAYPART_CANDIDATES = {
    "morning": ("ear-perk", "smile", "shift-posture"),
    "afternoon": ("shift-posture", "ear-perk", "grin"),
    "evening": ("tail-curl", "smile", "speak-softly"),
    "night": ("tail-still", "speak-softly", "pause"),
}

# Weather may color expression only when the matrix says fresh evidence is usable.
_WEATHER_HINTS = {
    "rain": ("tail-curl", "speak-softly"),
    "drizzle": ("tail-curl", "speak-softly"),
    "storm": ("ear-perk", "tail-still"),
    "thunder": ("ear-perk", "tail-still"),
    "wind": ("ear-flick", "tail-swish"),
    "breez": ("ear-flick", "tail-swish"),
    "snow": ("ear-perk", "tail-curl"),
    "fog": ("ear-perk", "tail-still"),
    "clear": ("ear-perk", "shift-posture"),
    "sun": ("ear-perk", "smile"),
}


def _valid_expression_id(value: str) -> bool:
    return value in _EXPRESSION_IDS


def _stable_offset(message_id: str, count: int) -> int:
    digest = sha256(message_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, count)


def _rotate(values: tuple[str, ...], message_id: str) -> tuple[str, ...]:
    if not values:
        return ()
    offset = _stable_offset(message_id, len(values))
    return values[offset:] + values[:offset]


def _definition_phrases() -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for definition in EXPRESSION_DEFINITIONS:
        if not _valid_expression_id(definition.id):
            continue
        phrases = tuple(
            dict.fromkeys(
                phrase.casefold().replace("-", " ")
                for phrase in (definition.id, *definition.aliases)
            )
        )
        result[definition.id] = phrases
    return result


_EXPRESSION_PHRASES = _definition_phrases()


def recent_expression_ids(messages: Iterable[str]) -> tuple[str, ...]:
    """Detect recently narrated reviewed expression IDs from assistant prose."""
    recent: list[str] = []
    for message in messages:
        if not isinstance(message, str):
            raise TypeError("recent assistant messages must be strings")
        text = message.casefold().replace("-", " ")
        for expression_id, phrases in _EXPRESSION_PHRASES.items():
            if expression_id in recent:
                continue
            if any(phrase in text for phrase in phrases):
                recent.append(expression_id)
    return tuple(recent)


@dataclass(frozen=True, slots=True)
class EmbodiedExpressionPlan:
    """One present-turn representational expression suggestion."""

    primary: str | None
    alternates: tuple[str, ...]
    avoid_recent: tuple[str, ...]
    intensity: str
    active_signals: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.primary is not None and not _valid_expression_id(self.primary):
            raise ValueError("primary expression must be a reviewed public expression")
        if not isinstance(self.alternates, tuple):
            raise TypeError("alternates must be a tuple")
        if any(not _valid_expression_id(item) for item in self.alternates):
            raise ValueError("alternates must be reviewed public expressions")
        if self.primary is not None and self.primary in self.alternates:
            raise ValueError("primary expression must not be duplicated in alternates")
        if self.intensity not in ("subtle", "moderate", "strong"):
            raise ValueError("unsupported expression intensity")
        if not isinstance(self.active_signals, tuple):
            raise TypeError("active_signals must be a tuple")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("expression plan reason must be nonempty")

    def prompt(self) -> str:
        """Provider-facing plan. This is style guidance, never execution evidence."""
        if self.primary is None:
            candidate = "none"
        else:
            candidate = self.primary
        alternates = ", ".join(self.alternates) if self.alternates else "none"
        avoid = ", ".join(self.avoid_recent) if self.avoid_recent else "none"
        signals = ", ".join(self.active_signals) if self.active_signals else "none"
        return "\n".join((
            "CURRENT EMBODIED EXPRESSION PLAN (trusted non-authoritative style projection)",
            f"Preferred expression semantic: {candidate}",
            f"Alternate expression semantics: {alternates}",
            f"Recently used semantics to avoid repeating: {avoid}",
            f"Expression intensity: {self.intensity}",
            f"Active contextual influence signals: {signals}",
            f"Planner reason: {self.reason}",
            "For an ordinary social or conversational reply, use the preferred expression "
            "or one alternate naturally when it fits. Translate semantic IDs into concise "
            "natural stage direction/prose; never print the ID itself. Do not mechanically "
            "prefix every answer. Technical focus, seriousness, or awkward fit may justify "
            "stillness. Do not repeat a recently used cue merely to add decoration.",
            "This plan describes represented avatar expression only. It is not evidence of "
            "physical sensation, real-world motion, contact, consent, renderer execution, "
            "or authority. It cannot override the interaction, safety, or action layers.",
        ))


class EmbodiedExpressionPlanner:
    """Choose varied candidates from the reviewed expression vocabulary."""

    def __init__(self) -> None:
        self._matrix = ContextualInfluenceMatrix()

    def plan(
        self,
        *,
        message_id: str,
        influence: ContinuityInfluence,
        recent_assistant_messages: Iterable[str] = (),
    ) -> EmbodiedExpressionPlan:
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be nonempty")
        if not isinstance(influence, ContinuityInfluence):
            raise TypeError("influence must be ContinuityInfluence")

        matrix_plan = self._matrix.plan(
            InfluenceSurface.CONVERSATION_EXPRESSION,
            influence,
        )
        return self.plan_from_matrix(
            message_id=message_id,
            influence=influence,
            matrix_plan=matrix_plan,
            recent_assistant_messages=recent_assistant_messages,
        )

    def plan_from_matrix(
        self,
        *,
        message_id: str,
        influence: ContinuityInfluence,
        matrix_plan: ContextualInfluencePlan,
        recent_assistant_messages: Iterable[str] = (),
    ) -> EmbodiedExpressionPlan:
        if matrix_plan.surface is not InfluenceSurface.CONVERSATION_EXPRESSION:
            raise ValueError("conversation-expression matrix plan required")

        recent = recent_expression_ids(recent_assistant_messages)
        active_signals = tuple(
            decision.signal.value
            for decision in matrix_plan.decisions
            if decision.mode is not InfluenceMode.NONE
        )

        candidates: list[str] = []
        emotion_decision = matrix_plan.decision_for(InfluenceSignal.EMOTION)
        if (
            emotion_decision.mode is not InfluenceMode.NONE
            and influence.primary_emotion is not None
        ):
            candidates.extend(_EMOTION_CANDIDATES.get(
                influence.primary_emotion,
                (),
            ))

        daypart_decision = matrix_plan.decision_for(InfluenceSignal.DAYPART)
        if daypart_decision.mode is not InfluenceMode.NONE:
            candidates.extend(_DAYPART_CANDIDATES.get(influence.daypart, ()))

        weather_decision = matrix_plan.decision_for(InfluenceSignal.WEATHER)
        if (
            weather_decision.mode is not InfluenceMode.NONE
            and influence.weather_condition
        ):
            weather = influence.weather_condition.casefold()
            for token, hints in _WEATHER_HINTS.items():
                if token in weather:
                    candidates.extend(hints)
                    break

        # Keep only expression semantics. Some legacy mappings above intentionally
        # name movement/pose concepts; they are ignored until the renderer-facing
        # pose/action planner consumes those namespaces explicitly.
        unique = tuple(dict.fromkeys(
            candidate for candidate in candidates
            if _valid_expression_id(candidate)
        ))
        rotated = _rotate(unique, message_id)
        fresh = tuple(item for item in rotated if item not in recent)
        usable = fresh or rotated

        primary = usable[0] if usable else None
        alternates = tuple(item for item in usable[1:4] if item != primary)

        if influence.primary_intensity >= 0.70:
            intensity = "strong"
        elif influence.primary_intensity >= 0.35:
            intensity = "moderate"
        else:
            intensity = "subtle"

        if primary is None:
            reason = "no reviewed expression candidate was grounded by active contextual signals"
        elif recent and primary not in recent:
            reason = "selected a grounded candidate while avoiding recently narrated expression semantics"
        else:
            reason = "selected a grounded candidate from the existing contextual influence matrix"

        return EmbodiedExpressionPlan(
            primary=primary,
            alternates=alternates,
            avoid_recent=recent[:8],
            intensity=intensity,
            active_signals=active_signals,
            reason=reason,
        )
