"""Wave E resilience reports retain the supplied evidence behind conclusions."""
from datetime import datetime, timezone

from sofia.modules.it_backup_dr import assess_recovery
from sofia.modules.it_containers import inspect_containers
from sofia.modules.it_database import analyze_status
from sofia.modules.it_devops.analysis import assess_pipeline

NOW = datetime(2026, 11, 3, 4, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
COMMIT = "b" * 40


def test_container_receipt_retains_observation_time():
    result=inspect_containers([{"source_ref":"host:one","container_ref":"service:one",
        "observed_at":NOW.isoformat(),"state":"running","health":"healthy",
        "restart_count":2}],now=NOW)
    assert result["containers"][0]["observed_at"] == NOW.isoformat()
    assert result["effect"] == "none"


def test_database_receipt_retains_telemetry_basis():
    result=analyze_status({"source_ref":"db:probe","database_ref":"db:one",
        "observed_at":NOW.isoformat(),"service_state":"up","connections_used":91,
        "connections_limit":100,"replica_lag_seconds":31,"p95_query_ms":1001,
        "errors_last_5m":2},now=NOW)
    assert result["connections_used"] == 91 and result["connections_limit"] == 100
    assert result["replica_lag_seconds"] == 31 and result["p95_query_ms"] == 1001
    assert result["errors_last_5m"] == 2 and result["effect"] == "none"


def test_backup_receipt_retains_recovery_objectives_and_claims():
    result=assess_recovery({"source_ref":"backup:probe","dataset_ref":"dataset:one",
        "observed_at":NOW.isoformat(),"last_backup_at":NOW.isoformat(),
        "backup_state":"completed","integrity_check":"passed","restore_drill":"passed",
        "rpo_seconds":3600,"rto_seconds":600,"restore_duration_seconds":500},now=NOW)
    assert (result["rpo_seconds"],result["rto_seconds"],result["restore_duration_seconds"]) == (3600,600,500)
    assert result["restore_claim"] == "supplied_pass" and result["effect"] == "none"


def test_devops_receipt_retains_exact_pipeline_evidence_without_deploying():
    result=assess_pipeline({"source_ref":"ci:source","pipeline_ref":"ci:run",
        "observed_at":NOW.isoformat(),"commit_sha":COMMIT,"branch":"feature:one",
        "build":"passed","tests":"passed","security_scan":"passed",
        "artifact_digest":DIGEST,"deploy_state":"waiting_approval"},now=NOW)
    assert result["branch"] == "feature:one" and result["artifact_digest"] == DIGEST
    assert (result["build"],result["tests"],result["security_scan"]) == ("passed","passed","passed")
    assert result["deploy_state"] == "waiting_approval"
    assert result["eligible_for_human_review"] is True and result["effect"] == "none"
