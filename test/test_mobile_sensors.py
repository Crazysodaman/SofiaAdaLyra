"""Authenticated phone observations become bounded ENVIRONMENT evidence."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.environment import EnvironmentFreshness
from sofia.environment.prompt import environment_prompt
from sofia.environment.service import EnvironmentService
from sofia.mobile.model import MobileSensorReport
from sofia.mobile.sensors import MobileSensorProvider, MobileSensorStore


NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def payload(**changes):
    value = {
        "device_id": "android-owner-1",
        "observed_at": NOW.isoformat(),
        "timezone": "America/Chicago",
        "latitude": 32.7,
        "longitude": -97.1,
        "accuracy_meters": 25.0,
        "battery_percent": 72.0,
        "charging": True,
        "network": "wifi",
        "activity": "walking",
        "ambient_light_lux": 120.0,
        "pressure_hpa": 1009.2,
        "proximity_near": False,
        "step_counter": 3210.0,
    }
    value.update(changes)
    return value


def test_mobile_report_is_durable_and_projects_without_coordinates(tmp_path):
    store = MobileSensorStore(tmp_path / "state.db")
    report = MobileSensorReport.from_payload(payload())
    store.record(report, received_at=NOW)
    service = EnvironmentService(
        providers=(MobileSensorProvider(store),)
    )

    snapshot = service.snapshot(now=NOW)
    prompt = environment_prompt(snapshot)

    assert snapshot.mobile_freshness is EnvironmentFreshness.CURRENT
    assert snapshot.current_location_freshness is EnvironmentFreshness.CURRENT
    assert snapshot.mobile is not None
    assert snapshot.mobile.activity.value == "walking"
    assert snapshot.mobile.battery_percent == 72.0
    assert "Phone battery: 72%." in prompt
    assert "Bounded device activity: walking." in prompt
    assert "Coordinates are intentionally withheld" in prompt
    assert "32.7" not in prompt
    assert "-97.1" not in prompt
    assert "android-owner-1" not in prompt
    assert "cannot prove intent" in prompt


def test_stale_mobile_report_is_retained_but_not_presented_as_current(tmp_path):
    store = MobileSensorStore(tmp_path / "state.db")
    old = NOW - timedelta(minutes=20)
    store.record(
        MobileSensorReport.from_payload(payload(observed_at=old.isoformat())),
        received_at=NOW,
    )
    snapshot = EnvironmentService(
        providers=(MobileSensorProvider(store),)
    ).snapshot(now=NOW)

    assert snapshot.mobile_freshness is EnvironmentFreshness.STALE
    assert "do not present it as current" in environment_prompt(snapshot)


@pytest.mark.parametrize(
    "changes",
    (
        {"latitude": 91.0},
        {"longitude": None},
        {"battery_percent": 101.0},
        {"network": "satellite"},
        {"activity": "sleeping"},
        {"charging": "yes"},
        {"unexpected": "field"},
    ),
)
def test_invalid_mobile_sensor_values_fail_closed(changes):
    with pytest.raises((TypeError, ValueError)):
        MobileSensorReport.from_payload(payload(**changes))


def test_store_rejects_future_timestamp(tmp_path):
    store = MobileSensorStore(tmp_path / "state.db")
    report = MobileSensorReport.from_payload(
        payload(observed_at=(NOW + timedelta(minutes=6)).isoformat())
    )
    with pytest.raises(ValueError, match="future"):
        store.record(report, received_at=NOW)
