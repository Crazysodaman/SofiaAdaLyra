from dataclasses import asdict
import json

import pytest

from sofia.ops.model import FleetHost, HostLifecycle
from sofia.ops.state_registry import StatePlaneFleetRegistry
from sofia.state.model import StateKey
from sofia.state.sqlite_plane import SQLiteStatePlane


def candidate(host_id):
    return FleetHost(host_id, "linux", "x86_64", HostLifecycle.CANDIDATE, False)


def legacy_file(tmp_path, hosts):
    path = tmp_path / "fleet.json"
    rows = []
    for host in hosts:
        raw = asdict(host)
        raw["lifecycle"] = host.lifecycle.value
        rows.append(raw)
    path.write_text(json.dumps({"hosts": rows}), encoding="utf-8")
    return path


def test_legacy_import_resumes_after_partial_durable_failure(tmp_path, monkeypatch):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    hosts = (candidate("venus"), candidate("terra"))
    legacy = legacy_file(tmp_path, hosts)
    original_write = plane.write

    def fail_second(record, *, expected_revision):
        if record.key.key == "terra":
            raise RuntimeError("simulated storage failure")
        return original_write(record, expected_revision=expected_revision)

    monkeypatch.setattr(plane, "write", fail_second)
    with pytest.raises(RuntimeError, match="storage failure"):
        StatePlaneFleetRegistry(plane, legacy_path=legacy)
    assert legacy.is_file()
    assert plane.read(StateKey(namespace="ops-fleet-host", key="venus")) is not None
    monkeypatch.setattr(plane, "write", original_write)
    restored = StatePlaneFleetRegistry(plane, legacy_path=legacy)
    assert restored.host("terra") == hosts[1]
    assert restored.host("venus") == hosts[0]
    assert not legacy.exists()
    assert legacy.with_name("fleet.json.migrated").is_file()


def test_legacy_import_preserves_later_canonical_state(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    registry = StatePlaneFleetRegistry(plane)
    registry.register_candidate(FleetHost("venus", "windows", "amd64", HostLifecycle.CANDIDATE, False))
    legacy = legacy_file(tmp_path, (candidate("venus"), candidate("terra")))
    restored = StatePlaneFleetRegistry(plane, legacy_path=legacy)
    assert restored.host("venus").platform == "windows"
    assert restored.host("terra") == candidate("terra")
    assert not legacy.exists()


def test_changed_partial_import_fails_without_retiring_input(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    registry = StatePlaneFleetRegistry(plane)
    registry._persist(candidate("venus"), source="legacy-json:fleet")
    altered = FleetHost("venus", "windows", "amd64", HostLifecycle.CANDIDATE, False)
    legacy = legacy_file(tmp_path, (altered,))
    with pytest.raises(ValueError, match="conflicting partial"):
        StatePlaneFleetRegistry(plane, legacy_path=legacy)
    assert legacy.is_file()
    assert StatePlaneFleetRegistry(plane).host("venus") == candidate("venus")


def test_failed_transition_keeps_canonical_and_cached_state(tmp_path, monkeypatch):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    registry = StatePlaneFleetRegistry(plane)
    host = FleetHost("venus", "linux", "x86_64", HostLifecycle.CANDIDATE, True)
    registry.register_candidate(host)

    def fail_write(*args, **kwargs):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(plane, "write", fail_write)
    with pytest.raises(RuntimeError, match="storage failure"):
        registry.transition("venus", HostLifecycle.ENROLLED)
    assert registry.host("venus") == host
    assert StatePlaneFleetRegistry(plane).host("venus") == host
