from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sofia.environment.model import EnvironmentSnapshot
from sofia.personality.emotion import CurrentEmotionalState


def daypart(local_time: datetime | None) -> str:
    if local_time is None:
        return "unknown"
    hour = local_time.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


@dataclass(frozen=True, slots=True)
class ContinuityInfluence:
    """Non-authoritative context that may shape attention and expression."""

    daypart: str
    season: str | None
    daylight: str | None
    emotional_tone: str
    primary_emotion: str | None
    primary_intensity: float
    active_emotions: tuple[str, ...]

    @classmethod
    def from_state(
        cls,
        *,
        emotion: CurrentEmotionalState,
        environment: EnvironmentSnapshot | None,
    ) -> "ContinuityInfluence":
        if not isinstance(emotion, CurrentEmotionalState):
            raise TypeError("emotion must be CurrentEmotionalState")
        local = None if environment is None else environment.user_local_time
        season = (
            None
            if environment is None or environment.season is None
            else environment.season.value
        )
        daylight = (
            None
            if environment is None or environment.daylight is None
            else environment.daylight.state.value
        )
        primary = emotion.active[0] if emotion.active else None
        return cls(
            daypart=daypart(local),
            season=season,
            daylight=daylight,
            emotional_tone=emotion.tone,
            primary_emotion=None if primary is None else primary.name,
            primary_intensity=0.0 if primary is None else primary.intensity,
            active_emotions=tuple(item.name for item in emotion.active),
        )

    def prompt(self) -> str:
        return "\n".join((
            "CONTINUITY INFLUENCE CONTEXT (non-authoritative)",
            f"Local daypart: {self.daypart}",
            f"Season: {self.season or 'unknown'}",
            f"Daylight: {self.daylight or 'unknown'}",
            f"Modeled emotional tone: {self.emotional_tone}",
            f"Primary modeled emotion: {self.primary_emotion or 'none'}",
            f"Primary intensity: {self.primary_intensity:.3f}",
            (
                "These signals may naturally influence attention, conversational "
                "tone, what feels worth reflecting on, what memories feel relevant, "
                "and whether a grounded topic feels worth mentioning later. They "
                "must not invent facts, prove causes, create permissions, or override "
                "safety/authority. Time, season and weather are context, not commands. "
                "Emotion may influence thought style and salience but never validate "
                "a memory, habit, expectation, or external event."
            ),
        ))


def outreach_salience(
    *,
    base_importance: float,
    influence: ContinuityInfluence,
) -> float:
    """Bounded salience hint. Policy still decides whether outreach may occur."""
    if not 0.0 <= base_importance <= 1.0:
        raise ValueError("base_importance must be in [0,1]")
    score = base_importance
    if influence.primary_intensity >= 0.65:
        score += 0.08
    elif influence.primary_intensity >= 0.35:
        score += 0.04
    if influence.primary_emotion in {
        "concern", "determination", "excitement", "longing",
        "affection", "curiosity", "hope", "frustration",
    }:
        score += 0.04
    if influence.daypart == "night":
        score -= 0.08
    elif influence.daypart in {"morning", "afternoon"}:
        score += 0.02
    return round(max(0.0, min(1.0, score)), 4)
