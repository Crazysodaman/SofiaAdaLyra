from datetime import datetime, timedelta, timezone

from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import (
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    WeatherObservation,
)
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.query import EnvironmentQueryResolver
from sofia.environment.service import EnvironmentService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class Provider:
    name = "query"

    def __init__(self, observation):
        self.observation = observation

    def observe(self, *, now):
        return self.observation


def config():
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Configured area",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )


def test_direct_time_uses_evidenced_timezone_not_host_assumption():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what time is it?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "America/Chicago" in answer.content


def test_direct_location_distinguishes_configured_from_current():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "where am I?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "configured location is Configured area" in answer.content
    assert "won't claim you're there right now" in answer.content


def test_direct_location_uses_only_fresh_user_current_evidence():
    current = LocationObservation(
        label="Current place",
        source_id="test.current",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CURRENT,
        timezone="America/Chicago",
        latitude=32.6,
        longitude=-97.2,
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=10),
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    current_location=current,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what is my current location",
        snapshot=snapshot,
    )
    assert "Current location evidence says you're at Current place" in answer.content


def test_where_are_you_does_not_reuse_user_location_as_host_location():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "where are you?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "runtime host/site" in answer.content
    assert "Configured area" not in answer.content


def test_timezone_query_reports_only_evidenced_timezone():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's my timezone?",
        snapshot=snapshot,
    )
    assert answer.content.endswith("America/Chicago.")


def test_direct_weather_refuses_stale_observation():
    weather = WeatherObservation(
        condition="rainy",
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
        source_id="test.weather",
        temperature_c=12.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the weather?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "don't have current weather evidence" in answer.content
    assert "stale" in answer.content
    assert "12.0" not in answer.content


def test_direct_weather_reports_current_source_and_observation():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=3),
        expires_at=NOW + timedelta(minutes=20),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=24.5,
        humidity_percent=40.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the weather like?",
        snapshot=snapshot,
    )
    assert "Current weather for Configured area: clear" in answer.content
    assert "24.5 °C" in answer.content
    assert "test.weather" in answer.content


def test_unknown_direct_environment_question_is_not_hijacked():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "Tell me a story about winter.",
        snapshot=snapshot,
    )
    assert not answer.recognized
    assert answer.content == ""
