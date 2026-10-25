"""Bounded, negative-path and cross-module tests for independent IT batch 3."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.it_storage import analyze_volumes
from sofia.modules.it_database import analyze_status
from sofia.modules.it_backup_dr import assess_recovery
from sofia.modules.it_security import triage_findings
from sofia.modules.it_storage.analysis import capability_registrations as storage_regs
from sofia.modules.it_database.analysis import capability_registrations as database_regs
from sofia.modules.it_backup_dr.analysis import capability_registrations as backup_regs
from sofia.modules.it_security.analysis import capability_registrations as security_regs
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc)


def volume(**kwargs):
    return {"source_ref": "platform:host1", "volume_ref": "volume:one", "observed_at": NOW.isoformat(),
            "total_bytes": 1_000_000, "used_bytes": 200_000, "read_only": False, "io_errors": 0} | kwargs


def database(**kwargs):
    return {"source_ref": "platform:dbagent", "database_ref": "db:one", "observed_at": NOW.isoformat(),
            "service_state": "up", "connections_used": 10, "connections_limit": 100,
            "replica_lag_seconds": None, "p95_query_ms": None, "errors_last_5m": 0} | kwargs


def backup(**kwargs):
    return {"source_ref": "backup:provider", "dataset_ref": "dataset:one", "observed_at": NOW.isoformat(),
            "last_backup_at": (NOW - timedelta(minutes=1)).isoformat(), "backup_state": "completed",
            "integrity_check": "passed", "restore_drill": "passed", "rpo_seconds": 300,
            "rto_seconds": 180, "restore_duration_seconds": 120} | kwargs


def security(**kwargs):
    return {"source_ref": "platform:edr", "asset_ref": "host:one", "finding_ref": "finding:one", "observed_at": NOW.isoformat(),
            "kind": "configuration_drift", "severity": "medium", "state": "open"} | kwargs


def test_storage_healthy_and_critical():
    r = analyze_volumes([volume(), volume(volume_ref="volume:two", used_bytes=960_000)], now=NOW)
    assert r["volumes"][0]["classification"] == "no_issue_observed"
    assert r["volumes"][1]["flags"] == ["capacity_critical"]
    assert r["volumes"][1]["used_percent"] == 96.0
    assert r["effect"] == "none" and r["evidence_class"] == "supplied_unverified"


def test_storage_read_only_and_io_error_flags():
    r = analyze_volumes([volume(read_only=True, io_errors=5)], now=NOW)
    assert set(r["volumes"][0]["flags"]) == {"read_only_observed", "io_errors_observed"}


def test_storage_stale_masks_health_and_usage():
    r = analyze_volumes([volume(observed_at=(NOW-timedelta(minutes=6)).isoformat(), used_bytes=999_000)], now=NOW)
    assert r["volumes"][0]["used_percent"] is None
    assert r["volumes"][0]["flags"] == []
    assert r["volumes"][0]["classification"] == "unknown"


@pytest.mark.parametrize("change", [{"used_bytes": -1}, {"used_bytes": 1_000_001}, {"total_bytes": 0},
                                     {"io_errors": True}, {"read_only": "false"}, {"volume_ref": "../etc"},
                                     {"observed_at": "now"}, {"total_bytes": 1.25}])
def test_storage_rejects_bad_input(change):
    with pytest.raises(ValueError):
        analyze_volumes([volume(**change)], now=NOW)


def test_storage_duplicate_ref_and_unknown_fields():
    with pytest.raises(ValueError):
        analyze_volumes([volume(), volume()], now=NOW)
    with pytest.raises(ValueError):
        analyze_volumes([volume(path="/private")], now=NOW)


def test_database_connection_and_replica_pressure():
    r = analyze_status(database(connections_used=98, replica_lag_seconds=45, p95_query_ms=1500, errors_last_5m=2), now=NOW)
    assert r["connection_percent"] == 98.0
    assert set(r["flags"]) == {"connection_pressure", "replica_lag_elevated", "query_latency_elevated", "errors_reported"}
    assert r["classification"] == "degraded"


def test_database_unknown_service_state_stays_unknown():
    assert analyze_status(database(service_state="unknown"), now=NOW)["classification"] == "unknown"


def test_database_stale_does_not_claim_status_or_pressure():
    r = analyze_status(database(service_state="down", observed_at=(NOW-timedelta(hours=1)).isoformat()), now=NOW)
    assert (r["freshness"], r["classification"], r["flags"], r["connection_percent"]) == ("stale", "unknown", [], None)


@pytest.mark.parametrize("change", [{"connections_used": True}, {"connections_limit": 0},
                                     {"connections_used": 101}, {"p95_query_ms": float("nan")},
                                     {"replica_lag_seconds": float("inf")}, {"errors_last_5m": -1},
                                     {"service_state": "restart"}, {"database_ref": "database\nsecret"},
                                     {"observed_at": "yesterday"}])
def test_database_rejects_invalid_evidence(change):
    with pytest.raises(ValueError):
        analyze_status(database(**change), now=NOW)


def test_backup_completed_is_not_equivalent_to_restorable():
    r = assess_recovery(backup(restore_drill="not_run", restore_duration_seconds=None), now=NOW)
    assert r["restore_claim"] == "not_verified"
    assert "restore_not_verified" in r["flags"]
    assert r["classification"] == "degraded"


def test_backup_passed_drill_remains_supplied_claim_not_certificate():
    r = assess_recovery(backup(), now=NOW)
    assert r["restore_claim"] == "supplied_pass"
    assert r["evidence_class"] == "supplied_unverified"
    assert r["effect"] == "none"


def test_backup_rpo_rto_exceeded_in_observation():
    r = assess_recovery(backup(last_backup_at=(NOW-timedelta(minutes=10)).isoformat(), restore_duration_seconds=200), now=NOW)
    assert set(r["flags"]) == {"rpo_exceeded", "rto_exceeded_in_drill"}


def test_backup_stale_suppresses_apparent_recovery_status():
    r = assess_recovery(backup(observed_at=(NOW-timedelta(hours=1)).isoformat(),
                               last_backup_at=(NOW-timedelta(hours=2)).isoformat()), now=NOW)
    assert (r["classification"], r["restore_claim"], r["flags"], r["last_backup_age_seconds"]) == ("unknown", "not_verified", [], None)


@pytest.mark.parametrize("change", [{"last_backup_at": (NOW+timedelta(seconds=1)).isoformat()},
                                     {"rpo_seconds": True}, {"rto_seconds": 0},
                                     {"backup_state": "start"}, {"integrity_check": "okay"},
                                     {"restore_drill": "not_run", "restore_duration_seconds": 23},
                                     {"restore_drill": "passed", "restore_duration_seconds": None},
                                     {"dataset_ref": "../secrets"}, {"observed_at": "last night"}])
def test_backup_denies_invalid_or_inconsistent_claims(change):
    with pytest.raises(ValueError):
        assess_recovery(backup(**change), now=NOW)


def test_backup_unknown_completion_remains_unknown():
    r = assess_recovery(backup(backup_state="unknown"), now=NOW)
    assert r["classification"] == "unknown"


def test_security_highest_reported_severity_is_only_a_claim():
    r = triage_findings([security(), security(finding_ref="finding:two", kind="unexpected_exposure", severity="critical")], now=NOW)
    assert r["highest_reported_severity"] == "critical"
    assert r["summary"] == "reported_findings_need_review"
    assert r["effect"] == "none" and r["evidence_class"] == "supplied_unverified"
    assert "Review" in r["findings"][1]["next_check"]


def test_security_resolved_does_not_trigger_remediation():
    r = triage_findings([security(state="resolved")], now=NOW)
    assert r["highest_reported_severity"] is None
    assert r["findings"][0]["next_check"] is None


def test_security_stale_open_critical_not_current():
    r = triage_findings([security(observed_at=(NOW-timedelta(minutes=6)).isoformat(), severity="critical")], now=NOW)
    assert r["highest_reported_severity"] is None
    assert r["findings"][0]["classification"] == "unknown"
    assert r["summary"] == "unknown"


@pytest.mark.parametrize("change", [{"kind": "arbitrary_command"}, {"severity": "system"},
                                     {"state": "execute"}, {"source_ref": "../../key"},
                                     {"observed_at": "2026-10-25"}, {"asset_ref": "a\nB"},
                                     {"raw_secret": "PASSWORD"}])
def test_security_rejects_untrusted_fields(change):
    with pytest.raises(ValueError):
        triage_findings([security(**change)], now=NOW)


def test_security_duplicate_and_bounded_input():
    with pytest.raises(ValueError):
        triage_findings([security(), security()], now=NOW)
    with pytest.raises(ValueError):
        triage_findings([], now=NOW)


def test_cross_module_storage_alert_does_not_fabricate_backup_receipt():
    disk = analyze_volumes([volume(used_bytes=990_000)], now=NOW)
    backup_report = assess_recovery(backup(restore_drill="not_run", restore_duration_seconds=None), now=NOW)
    assert disk["volumes"][0]["flags"] == ["capacity_critical"]
    assert backup_report["restore_claim"] == "not_verified"
    assert backup_report["effect"] == "none"


def test_handlers_derive_bounded_results_without_side_effects():
    # The handler reads the current clock. Fresh data is constructed at runtime.
    at = datetime.now(timezone.utc)
    examples = [
        (storage_regs, {"volumes": [volume(observed_at=at.isoformat())]}),
        (database_regs, {"status": database(observed_at=at.isoformat())}),
        (backup_regs, {"observation": backup(observed_at=at.isoformat(), last_backup_at=(at-timedelta(minutes=1)).isoformat())}),
        (security_regs, {"findings": [security(observed_at=at.isoformat())]}),
    ]
    for factory, params in examples:
        ((cap, handler),) = factory()
        result = handler(CapabilityRequest(cap, params, None, "Approved source projection"))
        assert result["effect"] == "none"
        assert result["sdk_protocol"] == "1.0"
        with pytest.raises(ValueError):
            handler(CapabilityRequest(Capability(cap.name, "Impersonated descriptor"), params, None, "Forged"))
