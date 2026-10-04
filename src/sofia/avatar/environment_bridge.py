"""Trusted ENVIRONMENT -> AVATAR wardrobe-planning adapter.

This module converts an already-grounded ENVIRONMENT snapshot into the coarse
season/weather/activity evidence used by the AVATAR wardrobe planner. It does
not fetch weather, infer a location, modify presentation state, assemble model
prompts, or grant any renderer/action authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re

from sofia.environment.model import (
    EnvironmentFreshness,
    EnvironmentSnapshot,
    Season as EnvironmentSeason,
)

from .wardrobe_planner import (
    Activity,
    EmotionStyleInfluence,
    Season,
    WardrobeContext,
    Weather,
    WeatherObservation,
)

_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\\Z", re.ASCII)


class EnvironmentBridgeError(ValueError):
    """Reject malformed or ungrounded host environment evidence."""


def _aware(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise EnvironmentBridgeError(f"{label} must be timezone-aware")
    return value


def _label(value: str, label: str, *, limit: int = 120) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise EnvironmentBridgeError(f"invalid {label}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise EnvironmentBridgeError(f"invalid {label}")
    return value


@dataclass(frozen=True, slots=True)
class HostWeatherEvidence:
    """Validated planner-facing weather evidence from ENVIRONMENT."""

    condition: Weather
    observed_at: datetime
    source_id: str
    location_label: str
    temperature_c: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Weather):
            raise EnvironmentBridgeError(
                "weather condition must be a Weather value"
            )
        _aware(self.observed_at, "weather observed_at")
        if (
            not isinstance(self.source_id, str)
            or not _SOURCE_ID.fullmatch(self.source_id)
        ):
            raise EnvironmentBridgeError("invalid weather source ID")
        _label(self.location_label, "weather location")
        if self.temperature_c is not None:
            if (
                isinstance(self.temperature_c, bool)
                or not isinstance(self.temperature_c, (int, float))
            ):
                raise EnvironmentBridgeError(
                    "temperature must be a Celsius number"
                )
            if (
                not math.isfinite(self.temperature_c)
                or not -100 <= self.temperature_c <= 70
            ):
                raise EnvironmentBridgeError(
                    "temperature is outside supported Celsius bounds"
                )

    def for_planner(self) -> WeatherObservation:
        return WeatherObservation(
            condition=self.condition,
            observed_at=self.observed_at,
            source_id=self.source_id,
        )


@dataclass(frozen=True, slots=True)
class HostEnvironmentEvidence:
    """One grounded ENVIRONMENT sample adapted for wardrobe planning."""

    observed_at: datetime
    season: Season
    activity: Activity
    clock_source_id: str
    weather: HostWeatherEvidence | None = None

    def __post_init__(self) -> None:
        _aware(self.observed_at, "host time")
        if (
            not isinstance(self.season, Season)
            or not isinstance(self.activity, Activity)
        ):
            raise EnvironmentBridgeError("season and activity must be typed")
        if (
            not isinstance(self.clock_source_id, str)
            or not _SOURCE_ID.fullmatch(self.clock_source_id)
        ):
            raise EnvironmentBridgeError("invalid clock source ID")
        if (
            self.weather is not None
            and not isinstance(self.weather, HostWeatherEvidence)
        ):
            raise EnvironmentBridgeError(
                "weather must be HostWeatherEvidence or None"
            )

    @classmethod
    def from_environment_snapshot(
        cls,
        snapshot: EnvironmentSnapshot,
        *,
        activity: Activity,
    ) -> "HostEnvironmentEvidence":
        """Map current ENVIRONMENT evidence into wardrobe categories."""
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise EnvironmentBridgeError(
                "snapshot must be EnvironmentSnapshot"
            )
        if not isinstance(activity, Activity):
            raise EnvironmentBridgeError("activity must be Activity")
        if snapshot.season is None:
            raise EnvironmentBridgeError(
                "environment snapshot has no grounded season"
            )

        season_map = {
            EnvironmentSeason.SPRING: Season.SPRING,
            EnvironmentSeason.SUMMER: Season.SUMMER,
            EnvironmentSeason.AUTUMN: Season.AUTUMN,
            EnvironmentSeason.WINTER: Season.WINTER,
        }
        observed_at = snapshot.user_local_time or snapshot.host_local_time

        weather = None
        source = snapshot.weather
        if (
            source is not None
            and snapshot.weather_freshness is EnvironmentFreshness.CURRENT
        ):
            condition = source.condition.casefold()
            wet_tokens = (
                "rain", "shower", "drizzle", "thunder",
                "storm", "hail", "sleet", "pour",
            )
            cold_tokens = ("snow", "ice", "frost", "freez")
            temperature = (
                source.feels_like_c
                if source.feels_like_c is not None
                else source.temperature_c
            )
            if any(token in condition for token in wet_tokens):
                wardrobe_weather = Weather.WET
            elif (
                any(token in condition for token in cold_tokens)
                or (temperature is not None and temperature <= 10.0)
            ):
                wardrobe_weather = Weather.COLD
            elif temperature is not None and temperature >= 27.0:
                wardrobe_weather = Weather.HOT
            else:
                wardrobe_weather = Weather.MILD

            weather = HostWeatherEvidence(
                condition=wardrobe_weather,
                observed_at=source.observed_at,
                source_id=source.source_id,
                location_label=(
                    source.location_label
                    or (
                        snapshot.effective_location.label
                        if snapshot.effective_location is not None
                        else "environment"
                    )
                ),
                temperature_c=source.temperature_c,
            )

        return cls(
            observed_at=observed_at,
            season=season_map[snapshot.season],
            activity=activity,
            clock_source_id="environment.snapshot",
            weather=weather,
        )

    def planner_context(
        self,
        *,
        emotion_influences: tuple[EmotionStyleInfluence, ...] = (),
    ) -> WardrobeContext:
        """Build the typed planner context consumed by live AVATAR routines."""
        return WardrobeContext(
            now=self.observed_at,
            season=self.season,
            activity=self.activity,
            weather=self.weather.for_planner() if self.weather else None,
            emotion_influences=emotion_influences,
        )
