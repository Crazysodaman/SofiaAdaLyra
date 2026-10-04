from datetime import datetime, timedelta, timezone

import pytest

from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_planner import (
    Activity,
    Season,
    WardrobeContext,
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


def snapshot_for(
    *,
    condition: str = "rainy",
    temperature_c: float = 15.0,
    stale: bool = False,
):
    weather = WeatherObservation(
        condition=condition,
        observed_at=NOW - (
            timedelta(hours=3) if stale else timedelta(minutes=5)
        ),
        expires_at=NOW - (
            timedelta(hours=2) if stale else -timedelta(minutes=25)
        ),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=temperature_c,
    )
    return EnvironmentService(
        config(),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)


def test_wardrobe_context_uses_environment_season_and_current_weather():
    snapshot = snapshot_for()
    context = WardrobeContext.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )

    assert context.season is Season.AUTUMN
    assert context.weather is not None
    assert context.weather.condition is Weather.WET
    assert context.weather.source_id == "test.weather"
    assert context.now == snapshot.user_local_time
    assert context.effective_weather is Weather.WET


def test_stale_environment_weather_is_not_consumed():
    context = WardrobeContext.from_environment_snapshot(
        snapshot_for(stale=True),
        activity=Activity.RELAXING,
    )
    assert context.weather is None
    assert context.effective_weather is None


@pytest.mark.parametrize(
    ("condition", "temperature", "expected"),
    (
        ("clear", 31.0, Weather.HOT),
        ("clear", 5.0, Weather.COLD),
        ("snowy", 15.0, Weather.COLD),
        ("cloudy", 20.0, Weather.MILD),
    ),
)
def test_environment_weather_mapping_is_bounded(
    condition,
    temperature,
    expected,
):
    context = WardrobeContext.from_environment_snapshot(
        snapshot_for(
            condition=condition,
            temperature_c=temperature,
        ),
        activity=Activity.CONVERSATION,
    )
    assert context.weather is not None
    assert context.weather.condition is expected


def test_wardrobe_context_refuses_to_guess_season():
    snapshot = EnvironmentService().snapshot(now=NOW)
    with pytest.raises(
        WardrobeError,
        match="no grounded season",
    ):
        WardrobeContext.from_environment_snapshot(
            snapshot,
            activity=Activity.CONVERSATION,
        )
