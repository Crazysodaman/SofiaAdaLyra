"""Named acceptance gate for the master ENVIRONMENT checklist.

This suite consolidates the production invariants behind checklist items
294-299 and 301. Item 293 (live weather population) additionally requires a
real provider canary and is not faked here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sofia.cognition.matrix import (
    ContextualInfluenceMatrix,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)
from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import (
    DaylightState,
    EnvironmentFreshness,
    LocationSubject,
    Season,
    WeatherObservation,
)
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.query import EnvironmentQueryResolver
from sofia.environment.service import EnvironmentService
from sofia.personality.influence import ContinuityInfluence, daypart


NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


class Provider:
    name = "acceptance-weather"

    def __init__(self, weather: WeatherObservation) -> None:
        self.weather = weather

    def observe(self, *, now):
        return EnvironmentProviderObservation(weather=self.weather)


def configuration() -> EnvironmentConfiguration:
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Homelab",
            timezone="America/Chicago",
            subject=LocationSubject.SITE,
            latitude=32.66,
            longitude=-97.1,
        )
    )


def test_environment_acceptance_central_daypart_season_and_daylight():
    snapshot = EnvironmentService(configuration()).snapshot(now=NOW)

    assert snapshot.timezone == "America/Chicago"
    assert snapshot.user_local_time is not None
    assert snapshot.user_local_time.hour == 13
    assert daypart(snapshot.user_local_time) == "afternoon"
    assert snapshot.season is Season.AUTUMN
    assert snapshot.daylight is not None
    assert snapshot.daylight.state is DaylightState.DAY


def test_environment_acceptance_current_weather_is_fresh_and_queryable():
    weather = WeatherObservation(
        condition="light rain",
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25),
        source_id="nws:TEST",
        location_label="Homelab",
        temperature_c=21.0,
        humidity_percent=95.0,
        wind_kph=8.0,
    )
    snapshot = EnvironmentService(
        configuration(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)

    assert snapshot.weather is weather
    assert snapshot.weather_freshness is EnvironmentFreshness.CURRENT

    answer = EnvironmentQueryResolver().resolve(
        "current weather?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "Current weather for Homelab" in answer.content
    assert "nws:TEST" in answer.content


def test_environment_acceptance_stale_weather_is_never_reported_current():
    stale = WeatherObservation(
        condition="old storm",
        observed_at=NOW - timedelta(hours=3),
        expires_at=NOW - timedelta(hours=2),
        source_id="nws:STALE",
        location_label="Homelab",
        temperature_c=8.0,
    )
    snapshot = EnvironmentService(
        configuration(),
        providers=(Provider(stale),),
    ).snapshot(now=NOW)

    assert snapshot.weather is stale
    assert snapshot.weather_freshness is EnvironmentFreshness.STALE

    answer = EnvironmentQueryResolver().resolve(
        "current weather?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "don't have current weather evidence" in answer.content
    assert "stale" in answer.content
    assert "old storm" not in answer.content


def test_environment_acceptance_context_cannot_grant_authority_or_safety():
    influence = ContinuityInfluence(
        daypart="afternoon",
        season="autumn",
        daylight="day",
        weather_condition="light rain",
        temperature_c=21.0,
        weather_freshness="current",
        location_freshness="unknown",
        primary_emotion_evidence_refs=("emotion:test",),
        emotional_tone="neutral",
        primary_emotion="curiosity",
        primary_intensity=0.25,
        active_emotions=("curiosity",),
        daypart_evidence_refs=(
            "runtime.clock",
            "environment.location:config.environment",
        ),
        season_evidence_refs=(
            "runtime.clock",
            "environment.location:config.environment",
        ),
        weather_evidence_refs=("environment.weather:nws:TEST",),
    )
    matrix = ContextualInfluenceMatrix()

    for surface in (
        InfluenceSurface.TOOL_AUTHORITY,
        InfluenceSurface.SAFE_POLICY,
        InfluenceSurface.RELEASE_VERIFY,
        InfluenceSurface.FLEET_AUTHORITY,
        InfluenceSurface.BODY_SAFETY,
    ):
        plan = matrix.plan(surface, influence)
        assert {
            signal: plan.mode_for(signal)
            for signal in InfluenceSignal
        } == {
            signal: InfluenceMode.NONE
            for signal in InfluenceSignal
        }
