"""Safety, freshness, redaction and registration tests for IT/Homelab analyzers."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.homelab.analysis import assess_services, capability_registrations as homelab_regs
from sofia.modules.it_database.analysis import analyze_status, capability_registrations as database_regs
from sofia.modules.it_observability.correlation import correlate, capability_registrations as observability_regs
from sofia.modules.it_storage.analysis import analyze_volumes, capability_registrations as storage_regs
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def volume(**change):
    data = {"source_ref": "platform:host1", "volume_ref": "volume:one", "observed_at": NOW.isoformat(),
            "total_bytes": 1_000_000, "used_bytes": 200_000, "read_only": False, "io_errors": 0}
    data.update(change)
    return data


def database(**change):
    data = {"source_ref": "platform:dbagent", "database_ref": "db:one", "observed_at": NOW.isoformat(),
            "service_state": "up", "connections_used": 10, "connections_limit": 100,
            "replica_lag_seconds": None, "p95_query_ms": None, "errors_last_5m": 0}
    data.update(change)
    return data


def observation(**change):
    data = {"source_ref": "platform:monitor", "component_ref": "app:one", "observed_at": NOW.isoformat(),
            "state": "ok", "signal": "memory"}
    data.update(change)
    return data


def service(name="api", **change):
    data = {"source_ref": "platform:site1", "service_ref": name, "host_ref": "node:01",
            "observed_at": NOW.isoformat(), "state": "healthy", "depends_on": []}
    data.update(change)
    return data


def test_storage_adds_bounded_smart_growth_and_redacted_note():
    report = analyze_volumes([volume(used_bytes=900_000, smart_state="warning", growth_bytes_per_day=5_000,
                                     note="token=abc123 C:\\Users\\alice\\secret.txt /home/bob/db.conf")], now=NOW)
    row = report["volumes"][0]
    assert row["classification"] == "degraded"
    assert row["smart_state"] == "warning"
    assert row["projected_days_to_full"] == 20.0
    assert {"capacity_warning", "smart_warning_reported", "capacity_growth_high"}.issubset(row["flags"])
    assert row["redactions"] == 3
    assert "<redacted>" in row["note"]
    for secret in ("abc123", "Users", "/home/bob"):
        assert secret not in json.dumps(report)


def test_storage_stale_masks_smart_growth_and_note_secret():
    report = analyze_volumes([volume(observed_at=(NOW - timedelta(minutes=6)).isoformat(), used_bytes=999_000,
                                     smart_state="failed", growth_bytes_per_day=1, note="secret=hidden")], now=NOW)
    row = report["volumes"][0]
    assert (row["freshness"], row["classification"], row["flags"]) == ("stale", "unknown", [])
    assert row["used_percent"] is None and row["smart_state"] is None
    assert row["growth_bytes_per_day"] is None and row["projected_days_to_full"] is None
    assert "hidden" not in json.dumps(report)


@pytest.mark.parametrize("change", [
    {"smart_state": "ok"}, {"growth_bytes_per_day": -1}, {"growth_bytes_per_day": True},
    {"note": "x" * 281}, {"note": "line\nbreak"},
])
def test_storage_rejects_malformed_new_fields(change):
    with pytest.raises(ValueError):
        analyze_volumes([volume(**change)], now=NOW)


@pytest.mark.parametrize("change", [
    {"volume_ref": "a/../../etc"}, {"source_ref": "C:/Users/alice"},
    {"volume_ref": "token:abc"}, {"source_ref": "platform:/home/alice"},
])
def test_storage_rejects_unsafe_identity(change):
    with pytest.raises(ValueError):
        analyze_volumes([volume(**change)], now=NOW)


def test_storage_rejects_duplicate_and_oversized_input():
    with pytest.raises(ValueError):
        analyze_volumes([volume(), volume()], now=NOW)
    oversized = [volume(volume_ref=f"volume:{index}") for index in range(65)]
    with pytest.raises(ValueError):
        analyze_volumes(oversized, now=NOW)


def test_database_replication_pressure_and_redaction():
    report = analyze_status(database(connections_used=95, replica_lag_seconds=400, p95_query_ms=6_000,
                                     errors_last_5m=2, replication_state="stopped",
                                     note="password=hunter2 https://admin:secret@db.example/internal /var/lib/db"),
                            now=NOW)
    assert report["classification"] == "degraded"
    assert report["replication_state"] == "stopped"
    assert {"connection_pressure", "replica_lag_elevated", "replica_lag_critical",
            "query_latency_elevated", "query_latency_critical", "errors_reported",
            "replication_stopped_reported"}.issubset(report["flags"])
    assert report["redactions"] >= 3
    for secret in ("hunter2", "admin:secret", "/var/lib/db"):
        assert secret not in json.dumps(report)


def test_database_unknown_replication_and_stale_are_truthful():
    unknown = analyze_status(database(replication_state="unknown"), now=NOW)
    assert (unknown["classification"], unknown["replication_state"]) == ("unknown", "unknown")
    assert "replication_state_unknown" in unknown["flags"]
    stale = analyze_status(database(observed_at=(NOW - timedelta(hours=1)).isoformat(),
                                    replication_state="stopped", replica_lag_seconds=400), now=NOW)
    assert (stale["freshness"], stale["classification"], stale["flags"]) == ("stale", "unknown", [])
    assert stale["replication_state"] is None and stale["connection_percent"] is None


@pytest.mark.parametrize("change", [
    {"replication_state": "legacy"}, {"note": "x" * 281}, {"note": "tab\there"},
    {"database_ref": "a/../../secrets"}, {"source_ref": "C:/Users/alice"},
    {"database_ref": "credential:prod"},
])
def test_database_rejects_malformed_or_unsafe_input(change):
    with pytest.raises(ValueError):
        analyze_status(database(**change), now=NOW)


def test_observability_correlates_fresh_incident_and_redacts_summaries():
    report = correlate([
        observation(state="warning", summary="token=abc123 C:\\Users\\alice\\service.log"),
        observation(signal="cpu", state="critical", summary="failure at /home/bob/app.log"),
    ], now=NOW)
    incident = report["incidents"][0]
    assert (incident["severity"], incident["freshness"], incident["correlated"]) == ("critical", "fresh", True)
    assert incident["degraded_signals"] == ["cpu", "memory"]
    assert report["redactions"] == 3
    for secret in ("abc123", "Users", "/home/bob"):
        assert secret not in json.dumps(report)


def test_observability_stale_evidence_is_reported_not_incident():
    report = correlate([observation(observed_at=(NOW - timedelta(hours=1)).isoformat(),
                                    state="critical", summary="secret=hidden")], now=NOW)
    assert report["incidents"] == [] and report["excluded_out_of_window"] == 1
    stale = report["stale_observations"][0]
    assert stale["freshness"] == "stale" and stale["summary"] == "<redacted>"
    assert "hidden" not in json.dumps(report)


@pytest.mark.parametrize("change", [
    {"signal": "command"}, {"state": "red"}, {"summary": "x" * 281},
    {"summary": "line\nbreak"}, {"source_ref": "C:/Users/alice"},
    {"component_ref": "a/../../secret"}, {"component_ref": "token:prod"},
])
def test_observability_rejects_malformed_or_unsafe_input(change):
    with pytest.raises(ValueError):
        correlate([observation(**change)], now=NOW)


def test_observability_rejects_duplicate_and_oversized_input():
    with pytest.raises(ValueError):
        correlate([observation(), observation()], now=NOW)
    with pytest.raises(ValueError):
        correlate([observation() for _ in range(129)], now=NOW)


def test_homelab_preserves_identity_and_redacts_notes():
    report = assess_services([
        service("db", state="unavailable", note="password=hidden C:\\Users\\alice\\db"),
        service("api", depends_on=["db"], note="see /home/bob/app.log"),
    ], now=NOW)
    api = next(item for item in report["services"] if item["service_ref"] == "api")
    assert (api["source_ref"], api["host_ref"], api["freshness"]) == ("platform:site1", "node:01", "fresh")
    assert api["unavailable_upstreams"] == ["db"] and api["classification"] == "attention"
    assert report["freshness_counts"] == {"fresh": 2, "stale": 0, "future": 0}
    assert report["redactions"] == 3
    for secret in ("hidden", "Users", "/home/bob"):
        assert secret not in json.dumps(report)


def test_homelab_stale_dependency_stays_unknown():
    report = assess_services([
        service("db", state="unavailable", observed_at=(NOW - timedelta(minutes=8)).isoformat()),
        service("api", depends_on=["db"]),
    ], now=NOW)
    db = next(item for item in report["services"] if item["service_ref"] == "db")
    api = next(item for item in report["services"] if item["service_ref"] == "api")
    assert (db["freshness"], db["reported_state"], db["classification"]) == ("stale", "unknown", "unknown")
    assert api["unknown_upstreams"] == ["db"] and api["unavailable_upstreams"] == []
    assert report["freshness_counts"] == {"fresh": 1, "stale": 1, "future": 0}


@pytest.mark.parametrize("change", [
    {"state": "broken"}, {"note": "x" * 281}, {"note": "line\nbreak"},
    {"service_ref": "a/../../secret"}, {"source_ref": "C:/Users/alice"},
    {"host_ref": "platform:/home/alice"}, {"depends_on": ["token:prod"]},
])
def test_homelab_rejects_malformed_or_unsafe_input(change):
    with pytest.raises(ValueError):
        assess_services([service(**change)], now=NOW)


def test_homelab_rejects_duplicate_and_oversized_input():
    with pytest.raises(ValueError):
        assess_services([service("api"), service("api")], now=NOW)
    oversized = [service(f"service-{index}") for index in range(65)]
    with pytest.raises(ValueError):
        assess_services(oversized, now=NOW)


@pytest.mark.parametrize("factory,params", [
    (storage_regs, {"volumes": [volume(observed_at=datetime.now(timezone.utc).isoformat())]}),
    (database_regs, {"status": database(observed_at=datetime.now(timezone.utc).isoformat())}),
    (observability_regs, {"observations": [observation(observed_at=datetime.now(timezone.utc).isoformat())]}),
    (homelab_regs, {"observations": [service(observed_at=datetime.now(timezone.utc).isoformat())]}),
])
def test_capability_registration_shape(factory, params):
    registrations = factory()
    assert isinstance(registrations, tuple) and len(registrations) == 1
    capability, handler = registrations[0]
    assert isinstance(capability, Capability) and callable(handler)
    result = handler(CapabilityRequest(capability, params, None, "review supplied observations"))
    assert result["effect"] == "none"
    assert result["evidence_class"] == "supplied_unverified"
    assert result["sdk_protocol"] == "1.0"
    with pytest.raises(ValueError):
        handler(CapabilityRequest(Capability(capability.name, "Forged descriptor"), params, None, "forged"))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, dict(params, command="restart"), None, "invalid"))
