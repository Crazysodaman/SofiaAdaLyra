from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sofia.ops.model import FleetHost, HostLifecycle, HostTelemetry
from sofia.ops.persistence import (
    FleetPersistenceError,
    JsonFleetRegistry,
    _replace_with_retry,
)
import sofia.ops.persistence as persistence


NOW = datetime(2026, 9, 26, 22, 0, tzinfo=timezone.utc)


def _candidate(host_id: str = "venus") -> FleetHost:
    return FleetHost(
        host_id=host_id,
        platform="windows",
        architecture="x86_64",
        lifecycle=HostLifecycle.CANDIDATE,
        trusted=True,
        telemetry=HostTelemetry(
            observed_at=NOW,
            cpu_percent=5,
            ram_used_bytes=1,
            ram_total_bytes=100,
        ),
    )


def test_atomic_replace_retries_transient_permission_error(tmp_path, monkeypatch):
    source = tmp_path / "fleet.json.tmp"
    target = tmp_path / "fleet.json"
    source.write_text('{"hosts":[]}', encoding="utf-8")
    target.write_text('{"hosts":[{"old":true}]}', encoding="utf-8")

    real_replace = Path.replace
    attempts = {"count": 0}

    def flaky_replace(self, destination):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError(5, "simulated SMB access denied")
        return real_replace(self, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr(persistence.time, "sleep", lambda seconds: None)

    _replace_with_retry(source, target, attempts=4)

    assert attempts["count"] == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"hosts": []}


def test_failed_durable_transition_rolls_back_in_memory_state(tmp_path, monkeypatch):
    path = tmp_path / "fleet.json"
    registry = JsonFleetRegistry(path)
    registry.register_candidate(_candidate())

    before_disk = path.read_text(encoding="utf-8")

    def fail_replace(*args, **kwargs):
        raise FleetPersistenceError("simulated permanent share failure")

    monkeypatch.setattr(persistence, "_replace_with_retry", fail_replace)

    with pytest.raises(FleetPersistenceError):
        registry.transition("venus", HostLifecycle.ENROLLED)

    assert registry.host("venus").lifecycle is HostLifecycle.CANDIDATE
    assert path.read_text(encoding="utf-8") == before_disk
