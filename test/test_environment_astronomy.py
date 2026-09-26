from datetime import date, datetime, timezone

from sofia.environment.astronomy import daylight_for, season_for
from sofia.environment.model import DaylightState, Season


def test_season_is_hemisphere_aware():
    day = date(2026, 7, 15)
    assert season_for(day=day, latitude=32.5) is Season.SUMMER
    assert season_for(day=day, latitude=-33.9) is Season.WINTER


def test_season_boundaries_are_deterministic():
    assert season_for(day=date(2026, 3, 20), latitude=40.0) is Season.SPRING
    assert season_for(day=date(2026, 9, 22), latitude=40.0) is Season.AUTUMN
    assert season_for(day=date(2026, 12, 21), latitude=-33.0) is Season.SUMMER


def test_midday_and_midnight_resolve_daylight_for_known_place():
    midday = daylight_for(
        now=datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc),
        latitude=32.5,
        longitude=-97.1,
        timezone_name="America/Chicago",
    )
    midnight = daylight_for(
        now=datetime(2026, 9, 25, 5, 0, tzinfo=timezone.utc),
        latitude=32.5,
        longitude=-97.1,
        timezone_name="America/Chicago",
    )
    assert midday.state is DaylightState.DAY
    assert midnight.state is DaylightState.NIGHT
    assert midday.sunrise is not None
    assert midday.sunset is not None


def test_polar_day_and_night_are_explicit():
    summer = daylight_for(
        now=datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc),
        latitude=89.0,
        longitude=0.0,
        timezone_name="UTC",
    )
    winter = daylight_for(
        now=datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc),
        latitude=89.0,
        longitude=0.0,
        timezone_name="UTC",
    )
    assert summer.state is DaylightState.POLAR_DAY
    assert winter.state is DaylightState.POLAR_NIGHT
