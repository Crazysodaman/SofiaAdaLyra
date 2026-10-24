from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops import (
    FleetPressureSample, ForecastAdvice, deterministic_fleet_forecast,
)


NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def sample(when, *, cpu=300, ram=400, gpu=200, vram=300, io=100, network=100,
           demand=300):
    return FleetPressureSample(
        "venus", when, cpu, ram, gpu, vram, io, network, demand,
    )


def test_deterministic_forecast_reports_measured_pressure_and_advice_only():
    result = deterministic_fleet_forecast((
        sample(NOW - timedelta(minutes=1), cpu=500),
        sample(NOW, cpu=600),
    ), now=NOW, horizon=timedelta(minutes=3))
    assert result.advice is ForecastAdvice.THROTTLE
    assert result.authoritative is False
    cpu = next(item for item in result.projections if item.resource == "cpu")
    assert cpu.projected == 900


def test_unknown_measurements_remain_unknown_and_do_not_become_capacity():
    result = deterministic_fleet_forecast((
        sample(NOW - timedelta(minutes=1), gpu=None, vram=None),
        sample(NOW, gpu=None, vram=None),
    ), now=NOW)
    assert next(item for item in result.projections if item.resource == "gpu").projected is None
    assert "gpu pressure is unobserved" in result.reasons


def test_stale_or_cross_host_forecast_fails_closed():
    old = sample(NOW - timedelta(minutes=5))
    newer = sample(NOW - timedelta(minutes=4))
    with pytest.raises(RuntimeError, match="stale"):
        deterministic_fleet_forecast((old, newer), now=NOW)
    other = FleetPressureSample(
        "artemis", NOW, 1, 1, 1, 1, 1, 1, 1,
    )
    with pytest.raises(ValueError, match="one host"):
        deterministic_fleet_forecast((sample(NOW - timedelta(seconds=1)), other), now=NOW)
