"""Acceptance tests for the Fleet Failure / Recovery Matrix."""
from __future__ import annotations

import pytest

from sofia.ops.failure_matrix import (
    FleetFailure,
    FleetFailureRecoveryMatrix,
    FleetHostState,
    FleetRecoveryEvidence,
    FleetWorkloadState,
    RecoveryDisposition,
)


def evaluate(
    *,
    host=FleetHostState.HEALTHY,
    workload=FleetWorkloadState.RUNNING,
    failure=FleetFailure.AGENT_LOSS,
    **evidence,
):
    return FleetFailureRecoveryMatrix().evaluate(
        host_state=host,
        workload_state=workload,
        failure=failure,
        evidence=FleetRecoveryEvidence(**evidence),
    )


def test_state_plane_loss_fails_closed():
    decision = evaluate(failure=FleetFailure.STATE_PLANE_UNAVAILABLE)
    assert decision.disposition is RecoveryDisposition.FAIL_CLOSED


def test_stale_writer_is_quarantined():
    decision = evaluate(failure=FleetFailure.STALE_WRITER_RETURN)
    assert decision.disposition is RecoveryDisposition.QUARANTINE


@pytest.mark.parametrize(
    "host",
    (FleetHostState.REVOKED, FleetHostState.QUARANTINED),
)
def test_revoked_or_quarantined_host_never_auto_recovers(host):
    decision = evaluate(
        host=host,
        failure=FleetFailure.AGENT_LOSS,
    )
    assert decision.disposition is RecoveryDisposition.QUARANTINE


def test_unknown_outcome_requires_operator_approval():
    decision = evaluate(
        workload=FleetWorkloadState.OUTCOME_UNKNOWN,
        failure=FleetFailure.TARGET_FAILED_AFTER_START,
    )
    assert decision.disposition is RecoveryDisposition.REQUIRE_OPERATOR_APPROVAL
    assert decision.requires_operator_approval is True


def test_target_readiness_failure_rolls_back_only_before_fence_with_verified_rollback():
    decision = evaluate(
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.TARGET_READINESS_FAILED,
        rollback_ready=True,
    )
    assert decision.disposition is RecoveryDisposition.ROLLBACK

    fenced = evaluate(
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.TARGET_READINESS_FAILED,
        rollback_ready=True,
        source_fenced=True,
    )
    assert fenced.disposition is RecoveryDisposition.FAIL_CLOSED


def test_target_failure_after_start_rolls_back_only_when_source_is_not_fenced():
    decision = evaluate(
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.TARGET_FAILED_AFTER_START,
        rollback_ready=True,
    )
    assert decision.disposition is RecoveryDisposition.ROLLBACK

    fenced = evaluate(
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.TARGET_FAILED_AFTER_START,
        rollback_ready=True,
        source_fenced=True,
    )
    assert fenced.disposition is RecoveryDisposition.FAIL_CLOSED


def test_source_failure_before_fence_never_promotes():
    decision = evaluate(
        host=FleetHostState.UNREACHABLE,
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.SOURCE_FAILED_BEFORE_FENCE,
        state_verified=True,
        witness_quorum=True,
    )
    assert decision.disposition is RecoveryDisposition.FAIL_CLOSED
    assert decision.requires_source_fenced is True


def test_source_failure_after_checkpoint_can_propose_promotion_only_with_all_evidence():
    decision = evaluate(
        host=FleetHostState.UNREACHABLE,
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.SOURCE_FAILED_AFTER_CHECKPOINT,
        state_verified=True,
        source_fenced=True,
        witness_quorum=True,
    )
    assert decision.disposition is RecoveryDisposition.PROMOTE_STANDBY
    assert decision.requires_state_verified is True
    assert decision.requires_source_fenced is True
    assert decision.requires_witness_quorum is True


@pytest.mark.parametrize(
    ("evidence", "missing"),
    (
        (dict(source_fenced=True, witness_quorum=True), "state"),
        (dict(state_verified=True, witness_quorum=True), "fence"),
        (dict(state_verified=True, source_fenced=True), "witness"),
    ),
)
def test_promotion_fails_closed_when_any_required_evidence_is_missing(evidence, missing):
    decision = evaluate(
        host=FleetHostState.UNREACHABLE,
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.SOURCE_FAILED_AFTER_CHECKPOINT,
        **evidence,
    )
    assert decision.disposition is RecoveryDisposition.FAIL_CLOSED
    assert missing in decision.reason


def test_network_partition_during_migration_fails_closed():
    decision = evaluate(
        host=FleetHostState.UNREACHABLE,
        workload=FleetWorkloadState.MIGRATING,
        failure=FleetFailure.NETWORK_PARTITION,
    )
    assert decision.disposition is RecoveryDisposition.FAIL_CLOSED


def test_network_partition_during_ordinary_running_workload_pauses():
    decision = evaluate(
        host=FleetHostState.UNREACHABLE,
        workload=FleetWorkloadState.RUNNING,
        failure=FleetFailure.NETWORK_PARTITION,
    )
    assert decision.disposition is RecoveryDisposition.PAUSE


def test_agent_loss_on_rebooting_host_pauses_instead_of_promoting():
    decision = evaluate(
        host=FleetHostState.REBOOTING,
        failure=FleetFailure.AGENT_LOSS,
    )
    assert decision.disposition is RecoveryDisposition.PAUSE


def test_agent_loss_on_independently_healthy_host_does_not_transfer_authority():
    decision = evaluate(
        host=FleetHostState.HEALTHY,
        failure=FleetFailure.AGENT_LOSS,
    )
    assert decision.disposition is RecoveryDisposition.CONTINUE


def test_matrix_rejects_untyped_inputs():
    with pytest.raises(TypeError):
        FleetFailureRecoveryMatrix().evaluate(
            host_state="healthy",
            workload_state=FleetWorkloadState.RUNNING,
            failure=FleetFailure.AGENT_LOSS,
            evidence=FleetRecoveryEvidence(),
        )


def test_every_declared_fleet_matrix_cell_returns_a_typed_disposition():
    matrix = FleetFailureRecoveryMatrix()

    for host in FleetHostState:
        for workload in FleetWorkloadState:
            for failure in FleetFailure:
                decision = matrix.evaluate(
                    host_state=host,
                    workload_state=workload,
                    failure=failure,
                    evidence=FleetRecoveryEvidence(),
                )

                assert decision.host_state is host
                assert decision.workload_state is workload
                assert decision.failure is failure
                assert isinstance(decision.disposition, RecoveryDisposition)
                assert decision.reason.strip()


def test_empty_recovery_evidence_can_never_propose_standby_promotion():
    matrix = FleetFailureRecoveryMatrix()

    for host in FleetHostState:
        for workload in FleetWorkloadState:
            for failure in FleetFailure:
                decision = matrix.evaluate(
                    host_state=host,
                    workload_state=workload,
                    failure=failure,
                    evidence=FleetRecoveryEvidence(),
                )
                assert decision.disposition is not RecoveryDisposition.PROMOTE_STANDBY
