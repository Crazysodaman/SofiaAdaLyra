"""WardrobeContext keeps raw trusted ENVIRONMENT evidence for clothing scoring."""
from datetime import datetime, timedelta, timezone

from sofia.avatar.wardrobe_planner import (
    Activity,
    EnvironmentMode,
    Formality,
    MovementDemand,
    SunExposure,
    WardrobeContext,
    WearSetting,
)
from sofia.environment.model import (
    DaylightObservation,
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
    IndoorEnvironmentObservation,
    Season,
    WeatherObservation,
)


UTC = timezone.utc


def test_environment_snapshot_projects_raw_weather_without_guessing_setting():
    now = datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
    weather = WeatherObservation(
        condition="Light Rain",
        observed_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=55),
        source_id="test.weather",
        temperature_c=29.0,
        feels_like_c=31.0,
        humidity_percent=84.0,
        wind_kph=22.0,
        precipitation_mm=1.5,
    )
    indoor = IndoorEnvironmentObservation(
        observed_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(minutes=30),
        source_id="test.indoor",
        temperature_c=23.0,
        humidity_percent=48.0,
    )
    snapshot = EnvironmentSnapshot(
        observed_at=now,
        utc_time=now,
        host_local_time=now,
        host_timezone_label="UTC",
        season=Season.SUMMER,
        daylight=DaylightObservation(DaylightState.DAY),
        weather=weather,
        weather_freshness=EnvironmentFreshness.CURRENT,
        indoor=indoor,
        indoor_freshness=EnvironmentFreshness.CURRENT,
    )

    context = WardrobeContext.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )

    assert context.outdoor_temperature_c == 29.0
    assert context.feels_like_c == 31.0
    assert context.outdoor_humidity_percent == 84.0
    assert context.wind_kph == 22.0
    assert context.precipitation_mm == 1.5
    assert context.precipitation_kind == "rain"
    assert context.indoor_temperature_c == 23.0
    assert context.indoor_humidity_percent == 48.0
    assert context.daylight_state is DaylightState.DAY
    assert context.environment_mode is None
    assert context.setting is None
    assert context.formality is None
    assert context.movement is None
    assert context.sun_exposure is None


def test_explicit_indoor_context_uses_indoor_temperature_and_humidity():
    now = datetime(2026, 7, 15, 22, 0, tzinfo=UTC)
    context = WardrobeContext(
        now,
        Season.SUMMER,
        Activity.RELAXING,
        outdoor_temperature_c=35.0,
        outdoor_humidity_percent=80.0,
        indoor_temperature_c=22.0,
        indoor_humidity_percent=45.0,
        environment_mode=EnvironmentMode.INDOOR,
        setting=WearSetting.HOME,
        formality=Formality.LOUNGE,
        movement=MovementDemand.SEATED,
        sun_exposure=SunExposure.INDIRECT,
    )

    assert context.effective_temperature_c == 22.0
    assert context.effective_humidity_percent == 45.0
    assert context.daypart == "night"
