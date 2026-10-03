from datetime import datetime, timezone
import sqlite3

from sofia.ops import ActivityMode, FleetHost, HostLifecycle, HostTelemetry
from sofia.ops.capability import OpsToolService
from sofia.ops.reconcile import (
    MaintenanceReceipt,
    MaintenanceReceiptOutcome,
)
from sofia.ops.desired import DesiredWorkloadPlacement
from sofia.ops.workload import WorkloadInstance, WorkloadPhase


NOW = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)


def _host(host_id: str, cpu: float) -> FleetHost:
    return FleetHost(
        host_id,
        "windows",
        "x86_64",
        HostLifecycle.CANDIDATE,
        True,
        HostTelemetry(
            NOW,
            cpu_percent=cpu,
            ram_used_bytes=1,
            ram_total_bytes=100,
        ),
    )


def test_ops_tool_placement_uses_same_durable_game_mode_evidence(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    service.activity.set_override("venus", ActivityMode.GAMING, at=NOW)
    service.activity.set_override("artemis", ActivityMode.NORMAL, at=NOW)

    decision = service.choose_placement(
        {
            "workload_id": "background",
            "version": "1",
            "supported_platforms": ["windows"],
            "supported_architectures": ["x86_64"],
        }
    )

    assert decision["host_id"] == "artemis"
    assert decision["eligible_hosts"][0] == "artemis"


def test_ops_tool_can_explicitly_allow_interactive_host(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    service.activity.set_override("venus", ActivityMode.GAMING, at=NOW)

    decision = service.choose_placement(
        {
            "workload_id": "desktop-client",
            "version": "1",
            "supported_platforms": ["windows"],
            "supported_architectures": ["x86_64"],
            "allow_interactive_host": True,
        }
    )

    assert decision["host_id"] == "venus"


def test_ops_tool_reads_verified_maintenance_receipt(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    receipt = MaintenanceReceipt(
        request_id="maint-read-1",
        host_id="artemis",
        operation="service_restart",
        target="SofiaAdaLyra",
        attempted_at=NOW,
        completed_at=NOW,
        outcome=MaintenanceReceiptOutcome.VERIFIED,
        execution_ref="remote:maint-read-1",
        verification_ref="verify:maint-read-1",
        observed="service running after restart",
    )
    service.maintenance_receipts.record(receipt)

    projected = service.maintenance_receipt("maint-read-1")

    assert projected is not None
    assert projected["outcome"] == "verified"
    assert projected["execution_ref"] == "remote:maint-read-1"
    assert projected["verification_ref"] == "verify:maint-read-1"
    assert projected["observed"] == "service running after restart"


def test_ops_drift_proposal_is_read_only_and_non_authoritative(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    result = service.drift_with_proposals(
        {
            "desired_hosts": [],
            "desired_workloads": [
                {
                    "workload_id": "plex",
                    "host_id": "artemis",
                }
            ],
            "instances": [
                {
                    "instance_id": "plex-1",
                    "workload_id": "plex",
                    "version": "1",
                    "host_id": "venus",
                    "phase": "ready",
                }
            ],
        }
    )

    assert result["drift"] == (
        {
            "kind": "workload_placement",
            "subject_id": "plex",
            "expected": "artemis",
            "observed": "venus",
        },
    )
    assert result["proposals"][0]["kind"] == "workload_migration"
    assert result["proposals"][0]["source_host_id"] == "venus"
    assert result["proposals"][0]["target_host_id"] == "artemis"
    assert result["proposals"][0]["authorized"] is False


def test_ops_reconciliation_preview_uses_durable_desired_and_observed_state(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    service.desired_state.set_workload(
        DesiredWorkloadPlacement("plex", "artemis"),
        at=NOW,
    )
    service.workloads.observe(
        WorkloadInstance(
            instance_id="plex-1",
            workload_id="plex",
            version="1",
            host_id="venus",
            phase=WorkloadPhase.READY,
            lease_epoch=3,
        ),
        at=NOW,
    )

    result = service.reconciliation_preview()

    assert result["desired_workloads"] == (
        {"workload_id": "plex", "host_id": "artemis"},
    )
    assert result["observed_workloads"][0]["host_id"] == "venus"
    assert result["drift"] == (
        {
            "kind": "workload_placement",
            "subject_id": "plex",
            "expected": "artemis",
            "observed": "venus",
        },
    )
    proposal = result["proposals"][0]
    assert proposal["kind"] == "workload_migration"
    assert proposal["source_host_id"] == "venus"
    assert proposal["target_host_id"] == "artemis"
    assert proposal["authorized"] is False
