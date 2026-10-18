from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sofia.learning.contracts import DataUse, DataUseGrant, PredictionMode
from sofia.learning.fleet_pressure import FleetPressurePilot
from sofia.learning.fleet_advisory import FleetAdvisoryEngine
from sofia.learning.service import LearningService
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.ops.history import SQLiteTelemetryHistory
from sofia.ops.model import FleetHost, HostLifecycle, HostTelemetry, WorkloadContract
from sofia.ops.latency import FleetLatencyStore
from sofia.ops.placement import PlacementEngine


NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


class _ApprovalVerifier:
    def __init__(self):
        self.consumed = set()

    def consume(self, *, approval_id, capability, parameters, now, _transaction_db):
        if approval_id in self.consumed:
            raise PermissionError("approval replay")
        assert capability.startswith("learning.")
        assert parameters
        assert _transaction_db.in_transaction
        self.consumed.add(approval_id)


class _CanonicalOps:
    def __init__(self, state_path: Path):
        self.history = SQLiteTelemetryHistory(state_path)
        self.activity = HostActivityStore(state_path)

    @staticmethod
    def fleet():
        return ({
            "host_id": "venus", "trusted": True, "lifecycle": "healthy",
        },)


def _grant() -> DataUseGrant:
    return DataUseGrant(
        grant_id="data-use:fleet-pressure", principal_id="sparks",
        audience_id="local:text", purpose="host-pressure-forecast",
        uses=frozenset({
            DataUse.OBSERVATION, DataUse.STORAGE, DataUse.FEATURE_EXTRACTION,
            DataUse.STATISTICAL_TRAINING,
        }),
        issued_at=NOW - timedelta(hours=1), expires_at=NOW + timedelta(days=30),
        approval_ref="owner-ui:fleet-pressure-grant",
    )


def _telemetry(at: datetime, cpu: float) -> HostTelemetry:
    return HostTelemetry(
        observed_at=at, cpu_percent=cpu,
        ram_used_bytes=4, ram_total_bytes=16,
    )


def test_fleet_pressure_requires_explicit_data_use_and_respects_gaming(
    canonical_state_path: Path,
):
    verifier = _ApprovalVerifier()
    learning = LearningService(canonical_state_path, approval_verifier=verifier)
    ops = _CanonicalOps(canonical_state_path)
    for minutes, cpu in ((-3, 20.0), (-2, 25.0), (-1, 30.0), (0, 35.0)):
        ops.history.append("venus", _telemetry(NOW + timedelta(minutes=minutes), cpu))
    pilot = FleetPressurePilot(canonical_state_path, learning=learning, ops_service=ops)

    assert pilot.tick(at=NOW) is None
    learning.record_grant(_grant())
    ops.activity.set_override("venus", ActivityMode.GAMING, at=NOW)
    gaming = pilot.tick(at=NOW, busy=False)
    assert gaming["resource_targets_skipped"] == 1
    assert gaming["forecasts_created"] == 0
    assert pilot.diagnostics()["totals"] == {}
    ops.activity.set_override("venus", ActivityMode.AUTO, at=NOW + timedelta(seconds=1))
    learning.set_mode(
        PredictionMode.ADVISORY, at=NOW + timedelta(seconds=1),
        approval_ref="owner-ui:separate-advisory-consumer",
    )
    # The unpromoted Fleet pilot cannot inherit another consumer's advisory mode.
    assert pilot.tick(at=NOW + timedelta(seconds=1)) is None


def test_shadow_forecast_settles_from_delayed_telemetry_and_survives_restart(
    canonical_state_path: Path,
):
    verifier = _ApprovalVerifier()
    learning = LearningService(canonical_state_path, approval_verifier=verifier)
    grant = _grant()
    learning.record_grant(grant)
    ops = _CanonicalOps(canonical_state_path)
    for minutes, cpu in ((-3, 20.0), (-2, 25.0), (-1, 30.0), (0, 35.0)):
        ops.history.append("venus", _telemetry(NOW + timedelta(minutes=minutes), cpu))
    pilot = FleetPressurePilot(canonical_state_path, learning=learning, ops_service=ops)

    created = pilot.tick(at=NOW)
    assert created == {
        "forecasts_created": 1, "outcomes_settled": 0,
        "outcomes_unknown": 0, "mode": PredictionMode.SHADOW.value,
        "resource_targets_created": 6,
        "resource_targets_settled": 0,
        "resource_targets_skipped": 2,
        "resource_errors": 0,
    }
    before = pilot.diagnostics()
    assert before["actions_executed"] == 0
    assert before["totals"] == {"pending": 1}
    assert pilot.tick(at=NOW) is None
    assert pilot.diagnostics()["totals"] == {"pending": 1}

    ops.history.append("venus", _telemetry(NOW + timedelta(minutes=5), 62.0))
    outcome = pilot.tick(at=NOW + timedelta(minutes=5))
    assert outcome["outcomes_settled"] == 1
    restarted = FleetPressurePilot(
        canonical_state_path,
        learning=LearningService(canonical_state_path, approval_verifier=_ApprovalVerifier()),
        ops_service=_CanonicalOps(canonical_state_path),
    )
    after = restarted.diagnostics()
    assert after["totals"]["settled"] == 1
    settled = next(row for row in after["forecasts"] if row["status"] == "settled")
    assert settled["outcome_ref"].startswith("ml-fleet-outcome:")
    assert settled["candidate_error"] is not None
    assert settled["last_value_error"] is not None
    assert settled["ewma_error"] is not None
    assert after["paired_metrics"]["settled"] == 1
    assert after["paired_metrics"]["advancement_authorized"] is False


def test_missing_delayed_measurement_is_unknown_not_success(
    canonical_state_path: Path,
):
    verifier = _ApprovalVerifier()
    learning = LearningService(canonical_state_path, approval_verifier=verifier)
    learning.record_grant(_grant())
    ops = _CanonicalOps(canonical_state_path)
    for minutes, cpu in ((-3, 20.0), (-2, 25.0), (-1, 30.0), (0, 35.0)):
        ops.history.append("venus", _telemetry(NOW + timedelta(minutes=minutes), cpu))
    pilot = FleetPressurePilot(canonical_state_path, learning=learning, ops_service=ops)
    pilot.tick(at=NOW)

    result = pilot.tick(at=NOW + timedelta(minutes=16))
    assert result["outcomes_unknown"] == 1
    diagnostic = pilot.diagnostics()
    assert diagnostic["totals"]["unknown"] == 1
    unknown = next(row for row in diagnostic["forecasts"] if row["status"] == "unknown")
    assert unknown["actual_percent"] is None
    assert unknown["candidate_error"] is None


def test_multi_resource_targets_cover_all_horizons_and_reject_out_of_order(
    canonical_state_path: Path,
):
    learning = LearningService(canonical_state_path, approval_verifier=_ApprovalVerifier())
    learning.record_grant(_grant())
    ops = _CanonicalOps(canonical_state_path)
    for minutes, value in ((-3, 70.0), (-2, 80.0), (-1, 90.0), (0, 98.0)):
        ops.history.append("venus", HostTelemetry(
            observed_at=NOW + timedelta(minutes=minutes), cpu_percent=value,
            ram_used_bytes=int(value), ram_total_bytes=100,
            gpu_percent=value, vram_used_bytes=int(value), vram_total_bytes=100,
        ))
    pilot = FleetPressurePilot(canonical_state_path, learning=learning, ops_service=ops)
    result = pilot.tick(at=NOW)
    assert result["resource_targets_created"] == 12
    diagnostic = pilot.diagnostics()["resource_advisory"]
    assert diagnostic["horizons_minutes"] == (5, 15, 30)
    assert diagnostic["resources"] == ("cpu", "ram", "gpu", "vram")
    assert diagnostic["events"]["anomaly_candidate"] >= 4
    assert diagnostic["authority"] is False
    assert diagnostic["actions_executed"] == 0

    # A late source observation is retained by OPS but cannot become a label.
    ops.history.append("venus", HostTelemetry(
        observed_at=NOW - timedelta(minutes=10), cpu_percent=5.0,
        ram_used_bytes=5, ram_total_bytes=100,
    ))
    rejected = pilot.tick(at=NOW + timedelta(seconds=1))
    assert rejected["resource_targets_skipped"] == 1
    assert pilot.diagnostics()["resource_advisory"]["events"]["skipped"] >= 1


def test_anomaly_false_alarm_and_advisory_error_circuit_are_diagnostic_only(
    canonical_state_path: Path,
):
    ops = _CanonicalOps(canonical_state_path)
    for minutes, value in ((-3, 70.0), (-2, 80.0), (-1, 90.0), (0, 98.0)):
        ops.history.append("venus", HostTelemetry(
            observed_at=NOW + timedelta(minutes=minutes), cpu_percent=value,
            ram_used_bytes=4, ram_total_bytes=16,
        ))
    advisor = FleetAdvisoryEngine(canonical_state_path, ops_service=ops)
    host = {"host_id": "venus", "trusted": True, "lifecycle": "healthy"}
    assert advisor.observe_host(host, at=NOW)["created"] == 6
    ops.history.append("venus", HostTelemetry(
        observed_at=NOW + timedelta(minutes=5), cpu_percent=10.0,
        ram_used_bytes=4, ram_total_bytes=16,
    ))
    assert advisor.observe_host(host, at=NOW + timedelta(minutes=5))["settled"] >= 2
    assert advisor.diagnostics()["events"]["anomaly_outcome"] >= 1

    class BrokenHistory:
        def ingestion_window(self, *args, **kwargs):
            raise RuntimeError("telemetry disconnected")

    ops.history = BrokenHistory()
    for seconds in range(6, 12):
        advisor.observe_host(host, at=NOW + timedelta(seconds=seconds))
    health = advisor.diagnostics()
    assert health["advisory_enabled"] is False
    assert "deterministic OPS remains active" in health["disabled_reason"]
    assert health["deterministic_ops_preserved"] is True


def test_placement_advisory_uses_existing_ops_policy_and_requires_mtls_identity(
    canonical_state_path: Path,
):
    ops = _CanonicalOps(canonical_state_path)
    for minutes, value in ((-3, 20.0), (-2, 22.0), (-1, 24.0), (0, 26.0)):
        ops.history.append("venus", HostTelemetry(
            observed_at=NOW + timedelta(minutes=minutes), cpu_percent=value,
            ram_used_bytes=4, ram_total_bytes=16,
        ))
    telemetry = HostTelemetry(
        observed_at=NOW, cpu_percent=26.0, ram_used_bytes=4, ram_total_bytes=16,
    )

    class Registry:
        def __init__(self, node_id):
            self.node_id = node_id

        def hosts(self):
            return (FleetHost(
                "venus", "linux", "x86_64", HostLifecycle.HEALTHY, True,
                telemetry=telemetry, node_id=self.node_id,
            ),)

    ops.registry = Registry(uuid4())
    ops.placement = PlacementEngine()
    advisor = FleetAdvisoryEngine(canonical_state_path, ops_service=ops)
    advisor.observe_host({"host_id": "venus", "trusted": True, "lifecycle": "healthy"}, at=NOW)
    latency = FleetLatencyStore(canonical_state_path)
    for index, elapsed in enumerate((12.0, 15.0, 18.0)):
        latency.append_authenticated(
            request_id=uuid4(), host_id="venus", node_id=ops.registry.node_id,
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=elapsed,
            observed_at=NOW - timedelta(seconds=2-index),
        )
    workload = WorkloadContract(
        "read-only-check", "1", ("linux",), ("x86_64",), min_ram_bytes=1,
    )
    suggestion = advisor.placement_advisory(workload, at=NOW)
    assert suggestion["suggested_host_id"] == "venus"
    assert suggestion["authority"] is False
    assert suggestion["can_move_workload"] is False
    assert 12.0 <= suggestion["predicted_latency_ms"] <= 18.0
    assert suggestion["latency_sample_count"] == 3
    assert suggestion["latency_evidence_kind"] == "pinned_mtls_operation_result"

    ops.registry = Registry(None)
    assert advisor.placement_advisory(workload, at=NOW) is None


def test_placement_advisory_abstains_for_stale_or_wrong_node_latency(
    canonical_state_path: Path,
):
    ops = _CanonicalOps(canonical_state_path)
    node_id = uuid4()
    telemetry = HostTelemetry(
        observed_at=NOW, cpu_percent=26.0, ram_used_bytes=4, ram_total_bytes=16,
    )

    class Registry:
        @staticmethod
        def hosts():
            return (FleetHost(
                "venus", "linux", "x86_64", HostLifecycle.HEALTHY, True,
                telemetry=telemetry, node_id=node_id,
            ),)

    ops.registry = Registry()
    ops.placement = PlacementEngine()
    for minutes, value in ((-3, 20.0), (-2, 22.0), (-1, 24.0), (0, 26.0)):
        ops.history.append("venus", HostTelemetry(
            observed_at=NOW + timedelta(minutes=minutes), cpu_percent=value,
            ram_used_bytes=4, ram_total_bytes=16,
        ))
    advisor = FleetAdvisoryEngine(canonical_state_path, ops_service=ops)
    advisor.observe_host({"host_id": "venus", "trusted": True, "lifecycle": "healthy"}, at=NOW)
    latency = FleetLatencyStore(canonical_state_path)
    for _ in range(3):
        latency.append_authenticated(
            request_id=uuid4(), host_id="venus", node_id=uuid4(),
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=10.0,
            observed_at=NOW,
        )
        latency.append_authenticated(
            request_id=uuid4(), host_id="venus", node_id=node_id,
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=10.0,
            observed_at=NOW - timedelta(minutes=11),
        )
    workload = WorkloadContract(
        "read-only-check", "1", ("linux",), ("x86_64",), min_ram_bytes=1,
    )
    assert advisor.placement_advisory(workload, at=NOW) is None
    assert advisor.diagnostics()["events"]["placement_skipped"] >= 1
