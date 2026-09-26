from datetime import datetime, timedelta, timezone

from sofia.environment.config import ConfiguredLocation, EnvironmentConfiguration
from sofia.environment.model import WeatherObservation
from sofia.environment.prompt import environment_prompt
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.service import EnvironmentService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class Provider:
    name = "prompt-test"

    def __init__(self, weather):
        self.weather = weather

    def observe(self, *, now):
        return EnvironmentProviderObservation(weather=self.weather)


def configuration():
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Configured area",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )


def test_prompt_distinguishes_configured_from_current_location():
    snapshot = EnvironmentService(configuration()).snapshot(now=NOW)
    prompt = environment_prompt(snapshot)
    assert "TRUSTED ENVIRONMENT SNAPSHOT" in prompt
    assert "TRUSTED RUNTIME CLOCK" in prompt
    assert "Configured user location: Configured area" in prompt
    assert "NOT proof" in prompt
    assert "Current physical location evidence: unavailable." in prompt
    assert "Derived season: autumn." in prompt


def test_prompt_never_exposes_coordinates():
    snapshot = EnvironmentService(configuration()).snapshot(now=NOW)
    prompt = environment_prompt(snapshot)
    assert "32.5" not in prompt
    assert "-97.1" not in prompt
    assert "Coordinates are intentionally withheld" not in prompt


def test_stale_weather_is_not_projected_as_current():
    weather = WeatherObservation(
        condition="rainy",
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=10.0,
    )
    snapshot = EnvironmentService(
        configuration(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)
    prompt = environment_prompt(snapshot)
    assert "Weather freshness: stale." in prompt
    assert "Current weather condition: rainy" not in prompt
    assert "10.0 C" not in prompt
    assert "do not present stale/future evidence as current" in prompt


def test_current_weather_includes_source_and_observation_time():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=25.0,
    )
    snapshot = EnvironmentService(
        configuration(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)
    prompt = environment_prompt(snapshot)
    assert "Weather freshness: current." in prompt
    assert "Current weather condition: clear." in prompt
    assert "Outdoor temperature: 25.0 C." in prompt
    assert "Weather source: test.weather" in prompt
