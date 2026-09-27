from __future__ import annotations

from dataclasses import dataclass

from sofia.avatar.presentation import AppearanceState, PresentationState
from sofia.avatar.wardrobe_routine import EmotionStyleInfluence
from sofia.personality.influence import ContinuityInfluence


@dataclass(frozen=True, slots=True)
class AvatarInfluenceProposal:
    """Non-authoritative appearance/expression suggestion.

    A proposal may shape later AVATAR selection, but it never commits
    presentation state and never proves a renderer displayed anything.
    """

    appearance: AppearanceState
    expression_tags: tuple[str, ...]
    posture_tags: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.appearance, AppearanceState):
            raise TypeError("appearance must be AppearanceState")
        for name in ("expression_tags", "posture_tags", "reasons"):
            value = getattr(self, name)
            if (
                not isinstance(value, tuple)
                or len(set(value)) != len(value)
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                raise ValueError(f"{name} must be a distinct tuple of strings")


def propose_avatar_influence(
    *,
    current: PresentationState,
    influence: ContinuityInfluence,
) -> AvatarInfluenceProposal:
    if not isinstance(current, PresentationState):
        raise TypeError("current must be PresentationState")
    if not isinstance(influence, ContinuityInfluence):
        raise TypeError("influence must be ContinuityInfluence")

    tags = list(current.appearance.style_tags)
    expressions: list[str] = []
    posture: list[str] = []
    reasons: list[str] = []

    if influence.daypart == "night":
        tags.append("late-night")
        posture.append("relaxed")
        reasons.append("local_daypart")
    elif influence.daypart == "morning":
        tags.append("morning")
        posture.append("upright")
        reasons.append("local_daypart")

    if influence.season:
        tags.append(f"season:{influence.season}")
        reasons.append("season")

    if influence.daylight:
        tags.append(f"daylight:{influence.daylight}")
        reasons.append("daylight")

    if (
        influence.weather_condition
        and influence.weather_freshness == "current"
    ):
        weather = influence.weather_condition.casefold()
        if any(token in weather for token in ("rain", "snow", "storm", "fog")):
            tags.append("weather-cozy")
            reasons.append("weather")

    emotion = influence.primary_emotion
    if emotion is not None and influence.primary_intensity >= 0.25:
        reasons.append("modeled_emotion")
        if emotion in {"joy", "excitement", "amusement", "playfulness"}:
            expressions.extend(("smile", "bright-eyes"))
            posture.append("open")
        elif emotion in {"fondness", "affection", "warmth", "tenderness"}:
            expressions.extend(("soft-smile", "gentle-gaze"))
            posture.append("soft")
        elif emotion in {"bashfulness", "embarrassment", "nervousness"}:
            expressions.extend(("blush", "avert-gaze"))
            posture.append("reserved")
        elif emotion in {"concern", "sadness", "disappointment"}:
            expressions.append("subdued")
            posture.append("quiet")
        elif emotion in {"determination", "frustration", "anger"}:
            expressions.append("focused")
            posture.append("firm")

    appearance = AppearanceState(
        hairstyle=current.appearance.hairstyle,
        hair_color=current.appearance.hair_color,
        tail_color=current.appearance.tail_color,
        style_tags=tuple(dict.fromkeys(tags)),
    )
    return AvatarInfluenceProposal(
        appearance=appearance,
        expression_tags=tuple(dict.fromkeys(expressions)),
        posture_tags=tuple(dict.fromkeys(posture)),
        reasons=tuple(dict.fromkeys(reasons)) or ("no_change",),
    )


def wardrobe_emotion_influences(
    influence: ContinuityInfluence,
) -> tuple[EmotionStyleInfluence, ...]:
    """Translate grounded modeled emotion into bounded wardrobe style bias."""
    if not isinstance(influence, ContinuityInfluence):
        raise TypeError("influence must be ContinuityInfluence")
    if (
        influence.primary_emotion is None
        or influence.primary_intensity < 0.20
        or not influence.primary_emotion_evidence_refs
    ):
        return ()

    tags: tuple[str, ...]
    emotion = influence.primary_emotion
    if emotion in {"joy", "excitement", "playfulness", "amusement"}:
        tags = ("playful", "bright")
    elif emotion in {"fondness", "affection", "warmth", "tenderness"}:
        tags = ("soft", "cozy")
    elif emotion in {"determination", "frustration", "anger"}:
        tags = ("focused", "practical")
    elif emotion in {"bashfulness", "embarrassment", "nervousness"}:
        tags = ("soft", "reserved")
    else:
        tags = ("contextual",)

    return (
        EmotionStyleInfluence(
            emotion=emotion,
            intensity=influence.primary_intensity,
            style_tags=tags,
            evidence_refs=influence.primary_emotion_evidence_refs,
        ),
    )
