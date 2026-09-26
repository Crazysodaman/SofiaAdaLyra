from datetime import datetime, timedelta, timezone

from sofia.environment.config import ConfiguredLocation, EnvironmentConfiguration
from sofia.environment.model import (
    EnvironmentFreshness,
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    Season,
    WeatherObservation,
)
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.service import EnvironmentService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class FakeProvider:
    name = "fake"

    def __init__(self, observation=None, error=None):
        self.observation = observation or EnvironmentProviderObservation()
        self.error = error
        self.calls = 0

    def observe(self, *, now):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.observation


def config():
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Configured area",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        ),
        refresh_seconds=300,
    )


def test_configured_location_drives_timezone_season_and_daylight_without_claiming_current():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    assert snapshot.configured_location is not None
    assert snapshot.configured_location.kind is LocationEvidenceKind.CONFIGURED
    assert snapshot.current_location is None
    assert snapshot.timezone == "America/Chicago"
    assert snapshot.user_local_time is not None
    assert snapshot.season is Season.AUTUMN
    assert snapshot.daylight is not None


def test_current_provider_location_takes_precedence_over_configured_location():
    current = LocationObservation(
        label="Current place",
        source_id="test.current",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CURRENT,
        timezone="America/Denver",
        latitude=39.7,
        longitude=-104.9,
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=13),
    )
    provider = FakeProvider(
        EnvironmentProviderObservation(current_location=current)
    )
    snapshot = EnvironmentService(
        config(),
        providers=(provider,),
    ).snapshot(now=NOW)
    assert snapshot.current_location is current
    assert snapshot.effective_location is current
    assert snapshot.timezone == "America/Denver"


def test_fresh_mobile_location_without_timezone_does_not_reuse_home_timezone():
    current = LocationObservation(
        label="Current mobile place",
        source_id="test.current",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CURRENT,
        timezone=None,
        latitude=39.7,
        longitude=-104.9,
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=13),
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            FakeProvider(
                EnvironmentProviderObservation(
                    current_location=current
                )
            ),
        ),
    ).snapshot(now=NOW)
    assert snapshot.current_location_freshness is EnvironmentFreshness.CURRENT
    assert snapshot.effective_location is current
    assert snapshot.timezone is None
    assert snapshot.user_local_time is None
    assert snapshot.season is None
    assert snapshot.daylight is None


def test_stale_current_location_falls_back_to_configured_location():
    stale = LocationObservation(
        label="Old place",
        source_id="test.current",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CURRENT,
        timezone="America/Denver",
        latitude=39.7,
        longitude=-104.9,
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            FakeProvider(
                EnvironmentProviderObservation(
                    current_location=stale
                )
            ),
        ),
    ).snapshot(now=NOW)
    assert snapshot.current_location is stale
    assert snapshot.current_location_freshness is EnvironmentFreshness.STALE
    assert snapshot.effective_location is snapshot.configured_location
    assert snapshot.timezone == "America/Chicago"


def test_current_weather_is_projected_with_explicit_freshness():
    weather = WeatherObservation(
        condition="rainy",
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25),
        source_id="test.weather",
        temperature_c=12.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            FakeProvider(
                EnvironmentProviderObservation(weather=weather)
            ),
        ),
    ).snapshot(now=NOW)
    assert snapshot.weather is weather
    assert snapshot.weather_freshness is EnvironmentFreshness.CURRENT


def test_provider_is_cached_within_refresh_window():
    provider = FakeProvider()
    service = EnvironmentService(config(), providers=(provider,))
    service.snapshot(now=NOW)
    service.snapshot(now=NOW + timedelta(seconds=120))
    assert provider.calls == 1
    service.snapshot(now=NOW + timedelta(seconds=301))
    assert provider.calls == 2


def test_provider_failure_is_degraded_evidence_not_runtime_failure():
    provider = FakeProvider(error=RuntimeError("secret details should not leak"))
    snapshot = EnvironmentService(
        config(),
        providers=(provider,),
    ).snapshot(now=NOW)
    assert snapshot.weather is None
    assert snapshot.provider_errors == ("fake:RuntimeError",)
    assert "secret details" not in snapshot.provider_errors[0]
