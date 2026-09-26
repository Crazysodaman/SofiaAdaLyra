from datetime import datetime, timedelta, timezone

import pytest

from sofia.avatar.interact_bridge import (
    HostEnvironmentEvidence,
    InteractionBridgeError,
)
from sofia.avatar.wardrobe_routine import (
    Activity,
    Season as AvatarSeason,
    Weather,
)
from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import WeatherObservation
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.service import EnvironmentService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class Provider:
    name = "avatar-weather"

    def __init__(self, weather):
        self.weather = weather

    def observe(self, *, now):
        return EnvironmentProviderObservation(weather=self.weather)


def config():
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Configured area",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )


def test_avatar_consumes_shared_environment_season_and_current_weather():
    weather = WeatherObservation(
        condition="rainy",
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=15.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)

    environment = HostEnvironmentEvidence.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )

    assert environment.season is AvatarSeason.AUTUMN
    assert environment.weather is not None
    assert environment.weather.condition is Weather.WET
    assert environment.weather.source_id == "test.weather"
    assert environment.clock_source_id == "environment.snapshot"
    assert environment.observed_at == snapshot.user_local_time


def test_avatar_does_not_consume_stale_weather():
    weather = WeatherObservation(
        condition="hot",
        observed_at=NOW - timedelta(hours=3),
        expires_at=NOW - timedelta(hours=2),
        source_id="test.weather",
        temperature_c=38.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)

    environment = HostEnvironmentEvidence.from_environment_snapshot(
        snapshot,
        activity=Activity.RELAXING,
    )
    assert environment.weather is None


@pytest.mark.parametrize(
    ("condition", "temperature", "expected"),
    (
        ("clear", 31.0, Weather.HOT),
        ("clear", 5.0, Weather.COLD),
        ("snowy", 15.0, Weather.COLD),
        ("cloudy", 20.0, Weather.MILD),
    ),
)
def test_avatar_weather_mapping_is_bounded(
    condition,
    temperature,
    expected,
):
    weather = WeatherObservation(
        condition=condition,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
        source_id="test.weather",
        temperature_c=temperature,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)
    environment = HostEnvironmentEvidence.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )
    assert environment.weather is not None
    assert environment.weather.condition is expected


def test_avatar_refuses_to_guess_season_without_grounded_location():
    snapshot = EnvironmentService().snapshot(now=NOW)
    with pytest.raises(InteractionBridgeError, match="no grounded season"):
        HostEnvironmentEvidence.from_environment_snapshot(
            snapshot,
            activity=Activity.CONVERSATION,
        )
