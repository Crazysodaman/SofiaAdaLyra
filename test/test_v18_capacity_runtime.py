"""CA-6109: real background capacity diagnostic, no autonomous enforcement."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.platform.application.presence import WorldAvailability, WorldEpistemicState
from sofia.ops.capacity import CapacityError, Reading
from sofia.ops.capacity_runtime import _disk_level, record_local_capacity
from sofia.ops.capacity import Level

pytestmark = pytest.mark.pkg_ops
NOW = datetime(2026, 10, 15, 22, tzinfo=timezone.utc)
TB = 1 << 40
GB = 1 << 30


class Recorder:
    def __init__(self):
        self.observations = []

    def record_state(self, **kwargs):
        self.observations.append(kwargs)
        return kwargs


def fake_storage(path):
    assert Path(path).name == "sofia.db"
    return (Reading("canonical_db_bytes", 6 * GB),)


def fake_space(free=200 * GB, total=TB):
    return lambda _: SimpleNamespace(free=free, total=total)


def test_actual_production_projection_only_records_scoped_diagnostic(tmp_path):
    state = tmp_path / "sofia.db"
    recorder = Recorder()
    result = record_local_capacity(
        state_path=state, presence=recorder, now=NOW,
        read_storage=fake_storage, disk_usage=fake_space(),
    )
    assert recorder.observations == [result]
    assert result["epistemic_state"] is WorldEpistemicState.OBSERVED
    assert result["predicate"] == "storage.capacity"
    assert result["availability"] is WorldAvailability.HEALTHY
    assert result["source_id"] == "ops:capacity_probe"
    assert result["freshness"] == timedelta(minutes=15)
    assert result["audience_id"] is None
    data = result["value"]
    assert data["canonical_db_bytes"] == 6 * GB
    assert data["db_budget_level"] == "warn"
    assert data["filesystem_pressure_level"] == "normal"
    assert data["action_taken"] is False
    assert data["acceptance_verified"] is False
    assert "process_rss_bytes" in data["unmeasured"]
    assert "cpu_sustained_millicores" in data["unmeasured"]
    assert "path" not in str(data).lower()


def test_nearly_full_filesystem_is_degraded_and_never_claimed_fixed(tmp_path):
    recorder = Recorder()
    result = record_local_capacity(
        state_path=tmp_path / "sofia.db", presence=recorder, now=NOW,
        read_storage=fake_storage, disk_usage=fake_space(free=500_000_000),
    )
    assert result["value"]["filesystem_pressure_level"] == "stop"
    assert result["value"]["overall_advisory_level"] == "stop"
    assert result["availability"] is WorldAvailability.DEGRADED
    assert result["value"]["action_taken"] is False
    assert result["value"]["acceptance_verified"] is False


def test_missing_measurement_fails_before_presenting_a_false_health_signal(tmp_path):
    recorder = Recorder()
    with pytest.raises(CapacityError, match="missing"):
        record_local_capacity(
            state_path=tmp_path / "sofia.db", presence=recorder, now=NOW,
            read_storage=lambda _: (), disk_usage=fake_space(),
        )
    assert not recorder.observations


@pytest.mark.parametrize("free,total", [
    (-1, 1000), (1001, 1000), (100, 0), (100, -1),
    (True, 1000), (100, 1000.5),
])
def test_invalid_disk_readings_never_create_a_health_record(free, total):
    with pytest.raises(CapacityError):
        _disk_level(free=free, total=total)


def test_clock_is_required_to_be_aware(tmp_path):
    with pytest.raises(CapacityError, match="timezone"):
        record_local_capacity(
            state_path=tmp_path / "sofia.db",
            presence=Recorder(),
            now=datetime(2026, 10, 15),
            read_storage=fake_storage,
            disk_usage=fake_space(),
        )


def test_boundaries_on_small_and_large_real_filesystems():
    assert _disk_level(free=GB, total=100 * GB) is Level.STOP
    assert _disk_level(free=3 * GB, total=100 * GB) is Level.DEGRADED
    assert _disk_level(free=6 * GB, total=100 * GB) is Level.WARN
    assert _disk_level(free=11 * GB, total=100 * GB) is Level.NORMAL
    assert _disk_level(free=30 * GB, total=TB) is Level.DEGRADED
    assert _disk_level(free=19 * GB, total=TB) is Level.STOP


def test_background_runtime_registers_exact_owned_callback():
    from inspect import getsource
    from sofia.platform.application.background_runtime import create_background_coordinator
    source = getsource(create_background_coordinator)
    assert 'coordinator.set_task(' in source
    assert '"local_capacity_observation"' in source
    assert "record_local_capacity(" in source
    assert "interval_seconds=300.0" in source
