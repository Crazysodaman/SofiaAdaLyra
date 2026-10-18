from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sofia.learning.contracts import DataUse, DataUseGrant, PredictionMode
from sofia.learning.fleet_pressure import FleetPressurePilot
from sofia.learning.service import LearningService
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.ops.history import SQLiteTelemetryHistory
from sofia.ops.model import HostTelemetry


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
    assert pilot.tick(at=NOW, busy=False) is None
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
