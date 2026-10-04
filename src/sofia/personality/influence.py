from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sofia.environment.model import EnvironmentFreshness, EnvironmentSnapshot
from sofia.emotion.journal import CurrentEmotionalState


_BACKGROUND_RELATIONAL = frozenset({
    "affection", "fondness", "warmth", "tenderness", "romance",
})


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
    weather_condition: str | None
    temperature_c: float | None
    weather_freshness: str | None
    location_freshness: str | None
    primary_emotion_evidence_refs: tuple[str, ...]
    emotional_tone: str
    primary_emotion: str | None
    primary_intensity: float
    active_emotions: tuple[str, ...]
    foreground_emotion_evidence_refs: tuple[str, ...] = ()
    foreground_emotion: str | None = None
    foreground_intensity: float = 0.0
    daypart_evidence_refs: tuple[str, ...] = ()
    season_evidence_refs: tuple[str, ...] = ()
    weather_evidence_refs: tuple[str, ...] = ()

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
        weather_is_current = (
            environment is not None
            and environment.weather is not None
            and environment.weather_freshness is EnvironmentFreshness.CURRENT
        )
        weather_condition = (
            environment.weather.condition
            if weather_is_current
            else None
        )
        temperature_c = (
            environment.weather.temperature_c
            if weather_is_current
            else None
        )
        weather_freshness = (
            None
            if environment is None
            else environment.weather_freshness.value
        )
        location_freshness = (
            None
            if environment is None
            else environment.current_location_freshness.value
        )
        # Keep the strongest modeled emotion for wardrobe/avatar style.
        # Conversation expression gets a separate foreground channel so
        # persistent relational tone cannot monopolize dialogue.
        primary = emotion.active[0] if emotion.active else None
        foreground = next(
            (
                item for item in emotion.active
                if item.name not in _BACKGROUND_RELATIONAL
            ),
            None,
        )
        effective_location = (
            None if environment is None else environment.effective_location
        )
        location_ref = (
            None
            if effective_location is None
            else f"environment.location:{effective_location.source_id}"
        )
        clock_refs = (
            ()
            if environment is None or environment.user_local_time is None
            else tuple(
                ref
                for ref in ("runtime.clock", location_ref)
                if ref is not None
            )
        )
        season_refs = (
            clock_refs
            if season is not None
            else ()
        )
        weather_refs = (
            ()
            if environment is None or environment.weather is None
            else (f"environment.weather:{environment.weather.source_id}",)
        )
        return cls(
            daypart=daypart(local),
            season=season,
            daylight=daylight,
            weather_condition=weather_condition,
            temperature_c=temperature_c,
            weather_freshness=weather_freshness,
            location_freshness=location_freshness,
            primary_emotion_evidence_refs=(
                () if primary is None else primary.evidence_refs
            ),
            emotional_tone=emotion.tone,
            primary_emotion=None if primary is None else primary.name,
            primary_intensity=0.0 if primary is None else primary.intensity,
            foreground_emotion_evidence_refs=(
                () if foreground is None else foreground.evidence_refs
            ),
            foreground_emotion=(
                None if foreground is None else foreground.name
            ),
            foreground_intensity=(
                0.0 if foreground is None else foreground.intensity
            ),
            active_emotions=tuple(item.name for item in emotion.active),
            daypart_evidence_refs=clock_refs,
            season_evidence_refs=season_refs,
            weather_evidence_refs=weather_refs,
        )

    def prompt(self) -> str:
        return "\n".join((
            "CONTINUITY INFLUENCE CONTEXT (non-authoritative)",
            f"Local daypart: {self.daypart}",
            f"Season: {self.season or 'unknown'}",
            f"Daylight: {self.daylight or 'unknown'}",
            f"Weather condition: {self.weather_condition or 'unknown'}",
            (
                "Outdoor temperature C: "
                + ("unknown" if self.temperature_c is None else f"{self.temperature_c:.1f}")
            ),
            f"Weather freshness: {self.weather_freshness or 'unknown'}",
            f"Location freshness: {self.location_freshness or 'unknown'}",
            f"Modeled emotional tone: {self.emotional_tone}",
            (
                "Foreground conversational emotion: "
                f"{self.foreground_emotion or 'none'}"
            ),
            f"Foreground intensity: {self.foreground_intensity:.3f}",
            (
                "Background relational tone available to non-conversational "
                f"style systems: {'yes' if self.primary_emotion is not None and self.foreground_emotion is None else 'contextual'}"
            ),
            (
                "These signals may naturally influence attention, conversational "
                "tone, what feels worth reflecting on, what memories feel relevant, "
                "and whether a grounded topic feels worth mentioning later. They "
                "must not invent facts, prove causes, create permissions, or override "
                "safety/authority. Time, season and weather are context, not commands. "
                "They may color expression or salience, but they do not create or prove "
                "a new emotional state. If asked how weather/time/season makes Sofía "
                "feel, answer from the current modeled emotional state and describe "
                "environmental influence as influence, not as a fabricated emotional "
                "cause. Do not invent warmth, calm, comfort, sadness, irritation, or "
                "other feelings solely because of a weather condition. Emotion may "
                "influence thought style and salience but never validate a memory, "
                "habit, expectation, or external event."
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
    if influence.daylight in {"night", "polar_night"}:
        score -= 0.03
    elif influence.daylight in {"day", "polar_day"}:
        score += 0.01
    if (
        influence.weather_condition
        and influence.weather_freshness == "current"
    ):
        weather = influence.weather_condition.casefold()
        if any(token in weather for token in ("storm", "tornado", "hurricane", "severe")):
            score += 0.08
        elif any(token in weather for token in ("rain", "snow", "fog")):
            score += 0.01
    return round(max(0.0, min(1.0, score)), 4)
