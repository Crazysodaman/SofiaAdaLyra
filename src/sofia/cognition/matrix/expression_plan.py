"""Typed embodied-expression planning over the existing contextual influence matrix.

This module chooses representational expression candidates only. It never grants
consent, authority, contact, animation execution, or physical-world action.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Iterable

from sofia.interaction.registry import (
    EXPRESSION_DEFINITIONS,
    POSE_DEFINITIONS,
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

# Only neutral/public poses are eligible for automatic conversational body language.
# More intimate or highly staged poses remain explicit interaction/presentation choices.
_AUTO_POSE_IDS = frozenset({
    "stand-relaxed",
    "lean-forward",
    "look-back",
    "recline",
    "sit-cross-legged",
    "hands-behind-back",
    "hip-pop",
})
_POSE_IDS = frozenset(
    item.id
    for item in POSE_DEFINITIONS
    if item.id in _AUTO_POSE_IDS and ("pose", item.id) not in PRIVATE_SEMANTICS
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
    "longing": ("tail-curl", "tail-swish", "ear-perk", "speak-softly"),
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
    "romance": ("speak-softly", "smile", "tail-curl", "teasing-smile"),
    "sensuality": ("speak-softly", "slow-tail-sway", "sultry-gaze", "teasing-smile"),
    "sexual-attraction": ("sultry-gaze", "blush", "tail-curl", "teasing-smile"),
    "sexual-desire": ("lip-bite", "sultry-gaze", "slow-tail-sway", "pause"),
    "sexual-arousal": ("blush", "lip-bite", "slow-tail-sway", "sultry-gaze"),
    "affectionate-uncertainty": ("avert-gaze", "tail-curl", "ear-flick", "speak-softly"),
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

# Daylight refines the provenanced daypart signal. It does not create emotion;
# it only changes which restrained expression cues are likely to feel natural.
_DAYLIGHT_CANDIDATES = {
    "day": ("ear-perk", "shift-posture"),
    "twilight": ("pause", "tail-curl", "avert-gaze"),
    "night": ("tail-still", "speak-softly", "pause"),
    "polar_day": ("ear-perk", "shift-posture"),
    "polar_night": ("tail-still", "speak-softly", "pause"),
}

_SEASON_CANDIDATES = {
    "spring": ("ear-perk", "tail-swish", "shift-posture"),
    "summer": ("ear-flick", "shift-posture", "grin"),
    "autumn": ("tail-curl", "pause", "speak-softly"),
    "winter": ("tail-curl", "tail-still", "speak-softly"),
}

_EMOTION_POSES: dict[str, tuple[str, ...]] = {
    "amusement": ("hip-pop", "stand-relaxed"),
    "playfulness": ("hip-pop", "look-back", "stand-relaxed"),
    "curiosity": ("lean-forward", "stand-relaxed"),
    "determination": ("stand-relaxed", "lean-forward"),
    "frustration": ("stand-relaxed", "hands-behind-back"),
    "anger": ("stand-relaxed", "hands-behind-back"),
    "sadness": ("recline", "sit-cross-legged"),
    "disappointment": ("recline", "sit-cross-legged"),
    "affection": ("sit-cross-legged", "stand-relaxed"),
    "fondness": ("sit-cross-legged", "stand-relaxed"),
    "warmth": ("sit-cross-legged", "stand-relaxed"),
    "tenderness": ("sit-cross-legged", "recline"),
    "excitement": ("lean-forward", "stand-relaxed"),
    "joy": ("stand-relaxed", "hip-pop"),
    "uncertainty": ("hands-behind-back", "stand-relaxed"),
    "nervousness": ("hands-behind-back", "stand-relaxed"),
    "bashfulness": ("hands-behind-back", "look-back"),
    "embarrassment": ("hands-behind-back", "look-back"),
    "concern": ("lean-forward", "stand-relaxed"),
    "caution": ("stand-relaxed", "lean-forward"),
    "relief": ("recline", "stand-relaxed"),
    "contentment": ("recline", "sit-cross-legged"),
    "anticipation": ("lean-forward", "stand-relaxed"),
    "reflection": ("sit-cross-legged", "recline"),
    "gratitude": ("sit-cross-legged", "stand-relaxed"),
    "appreciation": ("sit-cross-legged", "stand-relaxed"),
    "hope": ("lean-forward", "stand-relaxed"),
    "pride": ("stand-relaxed", "hip-pop"),
    "romance": ("sit-cross-legged", "look-back"),
    "sensuality": ("look-back", "recline"),
    "sexual-attraction": ("look-back", "hands-behind-back"),
    "sexual-desire": ("look-back", "recline"),
    "sexual-arousal": ("hands-behind-back", "look-back"),
    "affectionate-uncertainty": ("hands-behind-back", "sit-cross-legged"),
    "aversion": ("hands-behind-back", "stand-relaxed"),
    "disgust": ("hands-behind-back", "stand-relaxed"),
    "fear": ("hands-behind-back", "recline"),
    "jealousy": ("hands-behind-back", "look-back"),
    "shame": ("hands-behind-back", "look-back"),
    "humiliation": ("hands-behind-back", "recline"),
    "surprise": ("stand-relaxed", "lean-forward"),
    "longing": ("look-back", "sit-cross-legged"),
}

_DAYPART_POSES = {
    "morning": ("stand-relaxed", "lean-forward"),
    "afternoon": ("stand-relaxed", "lean-forward"),
    "evening": ("sit-cross-legged", "recline", "stand-relaxed"),
    "night": ("recline", "sit-cross-legged", "stand-relaxed"),
}

_SEASON_POSES = {
    "spring": ("lean-forward", "stand-relaxed"),
    "summer": ("stand-relaxed", "hip-pop"),
    "autumn": ("sit-cross-legged", "stand-relaxed"),
    "winter": ("recline", "sit-cross-legged", "stand-relaxed"),
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

_NATURAL_EXPRESSION = {
    "laugh": "laugh naturally",
    "chuckle": "give a brief chuckle",
    "giggle": "let out a small giggle",
    "cry": "show tears if the grounded emotion genuinely supports it",
    "tear-up": "eyes well slightly if the grounded emotion supports it",
    "sob": "show stronger crying only when strongly grounded",
    "sniffle": "a small sniffle",
    "sigh": "let out a brief sigh",
    "gasp": "a quick surprised intake of breath",
    "smile": "smile",
    "grin": "flash a crooked or playful grin",
    "frown": "frown slightly",
    "blush": "show a faint representational blush",
    "avert-gaze": "glance aside briefly",
    "pause": "pause for a beat",
    "speak-softly": "let the voice soften a little",
    "tremble": "show a subtle representational tremble only when strongly grounded",
    "ear-perk": "let the fox ears perk with attention",
    "ear-flick": "give one fox ear a small flick",
    "ear-flatten": "let the fox ears flatten slightly",
    "tail-swish": "let the fox tail swish once",
    "tail-curl": "let the fox tail curl in closer",
    "tail-still": "let the fox tail go still",
    "shift-posture": "shift posture or weight naturally",
    "sultry-gaze": "hold a briefly sultry, representational gaze",
    "lip-bite": "give a brief, representational lip bite",
    "teasing-smile": "let a teasing smile show",
    "slow-tail-sway": "let the fox tail sway slowly once",
}

_NATURAL_POSE = {
    "stand-relaxed": "settle into a relaxed stance",
    "lean-forward": "lean forward with interest",
    "look-back": "glance back over a shoulder",
    "recline": "recline a little",
    "sit-cross-legged": "sit cross-legged",
    "hands-behind-back": "rest the hands behind the back",
    "hip-pop": "shift one hip with playful confidence",
}


def _valid_expression_id(value: str) -> bool:
    return value in _EXPRESSION_IDS


def _valid_pose_id(value: str) -> bool:
    return value in _POSE_IDS


def _expression_text(value: str | None) -> str:
    if value is None:
        return "none"
    return _NATURAL_EXPRESSION.get(value, value.replace("-", " "))


def _pose_text(value: str | None) -> str:
    if value is None:
        return "none"
    return _NATURAL_POSE.get(value, value.replace("-", " "))


def _list_text(values: tuple[str, ...], renderer) -> str:
    return ", ".join(renderer(value) for value in values) if values else "none"


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

# Naturalized replies do not always preserve registry alias word order.
# These patterns map common prose/morphological forms back to the same
# reviewed expression family so anti-repeat survives provider naturalization.
_NATURAL_EXPRESSION_PATTERNS: dict[str, re.Pattern[str]] = {
    "ear-perk": re.compile(
        r"\b(?:ears?\s+perk(?:ed|ing)?(?:\s+up)?|"
        r"perk(?:ed|ing)?\s+(?:of\s+)?(?:my|her|the)?\s*ears?)\b",
        re.IGNORECASE,
    ),
    "ear-flick": re.compile(
        r"\b(?:ears?\s+flick(?:ed|ing)?|"
        r"flick(?:ed|ing)?\s+(?:of\s+)?(?:my|her|the)?\s*ears?)\b",
        re.IGNORECASE,
    ),
    "ear-flatten": re.compile(
        r"\b(?:ears?\s+flatten(?:ed|ing)?|"
        r"flatten(?:ed|ing)?\s+(?:my|her|the)?\s*ears?)\b",
        re.IGNORECASE,
    ),
    "tail-swish": re.compile(
        r"\b(?:tail\s+swish(?:es|ed|ing)?|"
        r"swish(?:es|ed|ing)?\s+(?:of\s+)?(?:my|her|the)?\s*tail)\b",
        re.IGNORECASE,
    ),
    "tail-curl": re.compile(
        r"\b(?:tail\s+curl(?:s|ed|ing)?|"
        r"curl(?:s|ed|ing)?\s+(?:of\s+)?(?:my|her|the)?\s*tail)\b",
        re.IGNORECASE,
    ),
    "tail-still": re.compile(
        r"\b(?:tail\s+(?:goes?|went|falls?|fell|is|stays?)\s+still|"
        r"stillness\s+(?:in|of)\s+(?:my|her|the)?\s*tail)\b",
        re.IGNORECASE,
    ),
    "shift-posture": re.compile(
        r"\b(?:shift(?:s|ed|ing)?\s+(?:my|her|the)?\s*"
        r"(?:posture|weight)|posture\s+shift(?:s|ed|ing)?)\b",
        re.IGNORECASE,
    ),
    "speak-softly": re.compile(
        r"\b(?:voice\s+(?:softens?|lower(?:s|ed)?|goes?\s+soft)|"
        r"speak(?:s|ing)?\s+softly|softer\s+voice)\b",
        re.IGNORECASE,
    ),
}


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
            natural_pattern = _NATURAL_EXPRESSION_PATTERNS.get(expression_id)
            if (
                any(phrase in text for phrase in phrases)
                or (
                    natural_pattern is not None
                    and natural_pattern.search(message) is not None
                )
            ):
                recent.append(expression_id)
    return tuple(recent)


@dataclass(frozen=True, slots=True)
class EmbodiedExpressionPlan:
    """One present-turn representational expression suggestion."""

    primary: str | None
    alternates: tuple[str, ...]
    pose: str | None
    pose_alternates: tuple[str, ...]
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
        if self.pose is not None and not _valid_pose_id(self.pose):
            raise ValueError("pose must be a reviewed automatic public pose")
        if not isinstance(self.pose_alternates, tuple):
            raise TypeError("pose_alternates must be a tuple")
        if any(not _valid_pose_id(item) for item in self.pose_alternates):
            raise ValueError("pose alternates must be reviewed automatic public poses")
        if self.pose is not None and self.pose in self.pose_alternates:
            raise ValueError("primary pose must not be duplicated in pose alternates")
        if self.intensity not in ("subtle", "moderate", "strong"):
            raise ValueError("unsupported expression intensity")
        if not isinstance(self.active_signals, tuple):
            raise TypeError("active_signals must be a tuple")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("expression plan reason must be nonempty")

    def prompt(self) -> str:
        """Provider-facing plan. This is style guidance, never execution evidence."""
        candidate = _expression_text(self.primary)
        alternates = _list_text(self.alternates, _expression_text)
        pose = _pose_text(self.pose)
        pose_alternates = _list_text(self.pose_alternates, _pose_text)
        avoid = _list_text(self.avoid_recent, _expression_text)
        preferred_line = (
            "No visible cue is grounded; express personality through cadence, wording, "
            "voice, or intentional stillness."
            if self.primary is None
            else f"Preferred brief expression for this reply: {candidate}"
        )
        return "\n".join((
            "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT",
            preferred_line,
            f"Other fitting expressions: {alternates}",
            f"A fitting body pose, if useful: {pose}",
            f"Other fitting poses: {pose_alternates}",
            f"Avoid repeating these recently used expression families: {avoid}",
            f"Suggested intensity: {self.intensity}",
            "Use one brief expression cue in the reply unless it would obscure urgent facts, "
            "conflict with the current boundary, or falsely imply sensation or execution. "
            "For technical or serious replies, keep it restrained rather than omitting "
            "personality. Intentional stillness is an expression only when grounded. "
            "These are guidance, not text to copy. "
            "Write natural prose or a concise stage direction; do not narrate this guidance, "
            "promise how a future reply will sound, or expose internal labels.",
            "Representational expression is not evidence of physical sensation, real-world "
            "motion, contact, consent, renderer execution, or authority. It cannot override "
            "interaction, safety, or action policy.",
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
        expressive_emotion = (
            influence.foreground_emotion
            or influence.primary_emotion
        )
        expressive_intensity = (
            influence.foreground_intensity
            if influence.foreground_emotion is not None
            else min(influence.primary_intensity, 0.20)
        )
        if (
            emotion_decision.mode is not InfluenceMode.NONE
            and expressive_emotion is not None
        ):
            candidates.extend(_EMOTION_CANDIDATES.get(
                expressive_emotion,
                (),
            ))

        daypart_decision = matrix_plan.decision_for(InfluenceSignal.DAYPART)
        if daypart_decision.mode is not InfluenceMode.NONE:
            candidates.extend(_DAYPART_CANDIDATES.get(influence.daypart, ()))
            candidates.extend(_DAYLIGHT_CANDIDATES.get(influence.daylight, ()))

        season_decision = matrix_plan.decision_for(InfluenceSignal.SEASON)
        if season_decision.mode is not InfluenceMode.NONE:
            candidates.extend(_SEASON_CANDIDATES.get(influence.season, ()))

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

        pose_candidates: list[str] = []
        if (
            emotion_decision.mode is not InfluenceMode.NONE
            and expressive_emotion is not None
        ):
            pose_candidates.extend(_EMOTION_POSES.get(
                expressive_emotion,
                (),
            ))
        if daypart_decision.mode is not InfluenceMode.NONE:
            pose_candidates.extend(_DAYPART_POSES.get(influence.daypart, ()))
        if season_decision.mode is not InfluenceMode.NONE:
            pose_candidates.extend(_SEASON_POSES.get(influence.season, ()))
        poses = tuple(dict.fromkeys(
            candidate for candidate in pose_candidates
            if _valid_pose_id(candidate)
        ))
        rotated_poses = _rotate(poses, message_id + ":pose")
        pose = rotated_poses[0] if rotated_poses else None
        pose_alternates = tuple(
            item for item in rotated_poses[1:3]
            if item != pose
        )

        if expressive_intensity >= 0.70:
            intensity = "strong"
        elif expressive_intensity >= 0.35:
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
            pose=pose,
            pose_alternates=pose_alternates,
            avoid_recent=recent[:8],
            intensity=intensity,
            active_signals=active_signals,
            reason=reason,
        )
