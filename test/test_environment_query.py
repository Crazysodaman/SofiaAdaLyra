from datetime import datetime, timedelta, timezone

from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import (
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    ForecastPeriod,
    IndoorEnvironmentObservation,
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
        precision_meters=12.0,
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
    assert "precision about 12 m" in answer.content


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

def test_my_timezone_does_not_relabel_host_timezone_as_user_timezone():
    host_config = EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Runtime host",
            timezone="America/Chicago",
            subject=LocationSubject.HOST,
            latitude=32.5,
            longitude=-97.1,
        )
    )
    snapshot = EnvironmentService(host_config).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's my timezone?",
        snapshot=snapshot,
    )
    assert answer.content == "I don't have an evidenced user timezone."

    context_answer = EnvironmentQueryResolver().resolve(
        "what timezone are you using?",
        snapshot=snapshot,
    )
    assert "host timezone" in context_answer.content
    assert "America/Chicago" in context_answer.content


def test_direct_forecast_returns_bounded_current_forecast():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="test.weather",
        forecast=(
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=1),
                condition="cloudy",
                high_c=24.0,
                low_c=16.0,
                precipitation_probability=20.0,
            ),
        ),
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
        "what's the forecast?",
        snapshot=snapshot,
    )
    assert "Current bounded forecast:" in answer.content
    assert "cloudy" in answer.content
    assert "precipitation 20%" in answer.content


def test_sunrise_and_sunset_are_directly_queryable():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    sunrise = EnvironmentQueryResolver().resolve(
        "when is sunrise?",
        snapshot=snapshot,
    )
    sunset = EnvironmentQueryResolver().resolve(
        "when is sunset?",
        snapshot=snapshot,
    )
    assert sunrise.recognized
    assert "Approximate sunrise is" in sunrise.content
    assert sunset.recognized
    assert "Approximate sunset is" in sunset.content


def test_current_indoor_environment_is_directly_queryable():
    indoor = IndoorEnvironmentObservation(
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=10),
        source_id="test.indoor",
        temperature_c=22.0,
        humidity_percent=45.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    indoor=indoor,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the temperature inside?",
        snapshot=snapshot,
    )
    assert "temperature 22.0 °C" in answer.content
    assert "humidity 45%" in answer.content
    assert "test.indoor" in answer.content

def test_environment_context_sources_are_direct_and_privacy_bounded():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    resolver = EnvironmentQueryResolver()

    assert resolver.might_match(
        "Explain your current environment context sources."
    )
    answer = resolver.resolve(
        "Explain your current environment context sources.",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Environment context sources:" in answer.content
    assert "trusted runtime host clock" in answer.content
    assert "Configured area" in answer.content
    assert "config.environment" in answer.content
    assert "not current physical-location proof" in answer.content
    assert "Current physical location evidence: unavailable." in answer.content
    assert "Weather/forecast evidence: unavailable." in answer.content
    assert "32.5" not in answer.content
    assert "-97.1" not in answer.content

