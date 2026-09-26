from datetime import datetime, timedelta, timezone

import pytest

from sofia.environment.model import (
    EnvironmentFreshness,
    EnvironmentSnapshot,
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    WeatherObservation,
)


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


def test_current_location_requires_observation_time():
    with pytest.raises(ValueError, match="requires observed_at"):
        LocationObservation(
            label="Known place",
            source_id="test.location",
            subject=LocationSubject.USER,
            kind=LocationEvidenceKind.CURRENT,
        )


def test_configured_location_is_not_current_evidence():
    location = LocationObservation(
        label="Configured home",
        source_id="config.environment",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CONFIGURED,
        timezone="America/Chicago",
        latitude=32.5,
        longitude=-97.1,
    )
    assert location.observed_at is None
    assert location.kind is LocationEvidenceKind.CONFIGURED


@pytest.mark.parametrize(
    ("observed_delta", "expires_delta", "expected"),
    (
        (timedelta(minutes=-5), timedelta(minutes=25), EnvironmentFreshness.CURRENT),
        (timedelta(hours=-2), timedelta(minutes=-1), EnvironmentFreshness.STALE),
        (timedelta(minutes=10), timedelta(minutes=40), EnvironmentFreshness.FUTURE),
    ),
)
def test_weather_freshness_is_explicit(
    observed_delta,
    expires_delta,
    expected,
):
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW + observed_delta,
        expires_at=NOW + expires_delta,
        source_id="test.weather",
    )
    assert weather.freshness(now=NOW) is expected


def test_environment_snapshot_rejects_current_slot_with_configured_evidence():
    configured = LocationObservation(
        label="Configured home",
        source_id="config.environment",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CONFIGURED,
        timezone="America/Chicago",
    )
    with pytest.raises(ValueError, match="current_location"):
        EnvironmentSnapshot(
            observed_at=NOW,
            utc_time=NOW,
            host_local_time=NOW,
            host_timezone_label="UTC",
            current_location=configured,
        )


def test_location_coordinates_are_paired_and_bounded():
    with pytest.raises(ValueError, match="supplied together"):
        LocationObservation(
            label="Bad",
            source_id="test.location",
            subject=LocationSubject.USER,
            kind=LocationEvidenceKind.CONFIGURED,
            latitude=30.0,
        )
    with pytest.raises(ValueError, match="latitude"):
        LocationObservation(
            label="Bad",
            source_id="test.location",
            subject=LocationSubject.USER,
            kind=LocationEvidenceKind.CONFIGURED,
            latitude=91.0,
            longitude=0.0,
        )

def test_location_precision_requires_coordinates_and_is_bounded():
    with pytest.raises(ValueError, match="requires coordinates"):
        LocationObservation(
            label="Bad",
            source_id="test.location",
            subject=LocationSubject.USER,
            kind=LocationEvidenceKind.CONFIGURED,
            precision_meters=25.0,
        )
    location = LocationObservation(
        label="Approximate place",
        source_id="test.location",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CONFIGURED,
        latitude=32.5,
        longitude=-97.1,
        precision_meters=25.0,
    )
    assert location.precision_meters == 25.0

