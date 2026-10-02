"""Fleet failure/recovery decision matrix.

This OPS-owned matrix converts observed failure state plus independently
verified recovery evidence into a bounded disposition. It does not perform
promotion, fencing, rollback, maintenance, or any other consequential action.
Those remain behind their existing authority/execution boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FleetHostState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    REBOOTING = "rebooting"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"


class FleetWorkloadState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DRAINING = "draining"
    CHECKPOINTING = "checkpointing"
    MIGRATING = "migrating"
    OUTCOME_UNKNOWN = "outcome_unknown"


class FleetFailure(str, Enum):
    AGENT_LOSS = "agent_loss"
    NETWORK_PARTITION = "network_partition"
    TARGET_READINESS_FAILED = "target_readiness_failed"
    SOURCE_FAILED_BEFORE_FENCE = "source_failed_before_fence"
    SOURCE_FAILED_AFTER_CHECKPOINT = "source_failed_after_checkpoint"
    TARGET_FAILED_AFTER_START = "target_failed_after_start"
    STALE_WRITER_RETURN = "stale_writer_return"
    STATE_PLANE_UNAVAILABLE = "state_plane_unavailable"


class RecoveryDisposition(str, Enum):
    CONTINUE = "continue"
    PAUSE = "pause"
    ROLLBACK = "rollback"
    QUARANTINE = "quarantine"
    FAIL_CLOSED = "fail_closed"
    REQUIRE_OPERATOR_APPROVAL = "require_operator_approval"
    PROMOTE_STANDBY = "promote_standby"


@dataclass(frozen=True, slots=True)
class FleetRecoveryEvidence:
    state_verified: bool = False
    source_fenced: bool = False
    witness_quorum: bool = False
    rollback_ready: bool = False
    operator_approved: bool = False

    def __post_init__(self) -> None:
        for name in (
            "state_verified",
            "source_fenced",
            "witness_quorum",
            "rollback_ready",
            "operator_approved",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class FleetRecoveryDecision:
    host_state: FleetHostState
    workload_state: FleetWorkloadState
    failure: FleetFailure
    disposition: RecoveryDisposition
    reason: str
    requires_state_verified: bool = False
    requires_source_fenced: bool = False
    requires_witness_quorum: bool = False
    requires_operator_approval: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.host_state, FleetHostState):
            raise TypeError("host_state must be FleetHostState")
        if not isinstance(self.workload_state, FleetWorkloadState):
            raise TypeError("workload_state must be FleetWorkloadState")
        if not isinstance(self.failure, FleetFailure):
            raise TypeError("failure must be FleetFailure")
        if not isinstance(self.disposition, RecoveryDisposition):
            raise TypeError("disposition must be RecoveryDisposition")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("recovery decision reason must be nonempty")


class FleetFailureRecoveryMatrix:
    """Choose a fail-closed recovery disposition from observed state.

    PROMOTE_STANDBY means only that promotion may be proposed to the existing
    promotion/lease boundary. It is never authority to perform the promotion.
    """

    def evaluate(
        self,
        *,
        host_state: FleetHostState,
        workload_state: FleetWorkloadState,
        failure: FleetFailure,
        evidence: FleetRecoveryEvidence,
    ) -> FleetRecoveryDecision:
        for value, expected, label in (
            (host_state, FleetHostState, "host_state"),
            (workload_state, FleetWorkloadState, "workload_state"),
            (failure, FleetFailure, "failure"),
            (evidence, FleetRecoveryEvidence, "evidence"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{label} must be {expected.__name__}")

        if failure is FleetFailure.STATE_PLANE_UNAVAILABLE:
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.FAIL_CLOSED,
                "authoritative state is unavailable; no ownership-changing recovery is safe",
            )

        if failure is FleetFailure.STALE_WRITER_RETURN:
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.QUARANTINE,
                "a stale writer must be isolated before any workload authority can continue",
            )

        if host_state in {FleetHostState.REVOKED, FleetHostState.QUARANTINED}:
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.QUARANTINE,
                "revoked or quarantined hosts cannot participate in automatic recovery",
            )

        if workload_state is FleetWorkloadState.OUTCOME_UNKNOWN:
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.REQUIRE_OPERATOR_APPROVAL,
                "workload outcome is unknown; automatic recovery would risk duplicate execution",
                requires_operator_approval=True,
            )

        if failure is FleetFailure.TARGET_READINESS_FAILED:
            if evidence.source_fenced:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.FAIL_CLOSED,
                    "target failed readiness after source fencing; source must not be reactivated automatically",
                    requires_source_fenced=True,
                )
            if evidence.rollback_ready:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.ROLLBACK,
                    "target failed readiness before source fencing and verified rollback is available",
                )
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.PAUSE,
                "target failed readiness and rollback readiness is not verified",
            )

        if failure is FleetFailure.TARGET_FAILED_AFTER_START:
            if evidence.source_fenced:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.FAIL_CLOSED,
                    "target failed after start and the source is already fenced",
                    requires_source_fenced=True,
                )
            if evidence.rollback_ready:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.ROLLBACK,
                    "target failed after start before source fencing; verified rollback may restore the source path",
                )
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.PAUSE,
                "target failed after start and rollback is not independently verified",
            )

        if failure is FleetFailure.SOURCE_FAILED_BEFORE_FENCE:
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.FAIL_CLOSED,
                "source failed before fencing; writer ownership cannot be proven safe",
                requires_source_fenced=True,
            )

        if failure is FleetFailure.SOURCE_FAILED_AFTER_CHECKPOINT:
            ready_for_promotion = (
                evidence.state_verified
                and evidence.source_fenced
                and evidence.witness_quorum
            )
            if ready_for_promotion:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.PROMOTE_STANDBY,
                    "checkpoint/state, source fencing, and independent witness quorum are verified",
                    requires_state_verified=True,
                    requires_source_fenced=True,
                    requires_witness_quorum=True,
                )
            missing = []
            if not evidence.state_verified:
                missing.append("state verification")
            if not evidence.source_fenced:
                missing.append("source fence")
            if not evidence.witness_quorum:
                missing.append("witness quorum")
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.FAIL_CLOSED,
                "standby promotion lacks required " + ", ".join(missing),
                requires_state_verified=True,
                requires_source_fenced=True,
                requires_witness_quorum=True,
            )

        if failure is FleetFailure.NETWORK_PARTITION:
            if workload_state in {
                FleetWorkloadState.MIGRATING,
                FleetWorkloadState.CHECKPOINTING,
                FleetWorkloadState.DRAINING,
            }:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.FAIL_CLOSED,
                    "network partition during authority-sensitive transition risks split brain",
                )
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.PAUSE,
                "network partition prevents reliable current-state observation",
            )

        if failure is FleetFailure.AGENT_LOSS:
            if host_state is FleetHostState.REBOOTING:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.PAUSE,
                    "agent loss during an observed reboot should wait for bounded recovery evidence",
                )
            if host_state is FleetHostState.UNREACHABLE:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.PAUSE,
                    "agent loss with unreachable host lacks enough evidence for promotion",
                )
            if host_state is FleetHostState.DEGRADED:
                return self._decision(
                    host_state,
                    workload_state,
                    failure,
                    RecoveryDisposition.PAUSE,
                    "degraded host with agent loss requires renewed telemetry before recovery",
                )
            return self._decision(
                host_state,
                workload_state,
                failure,
                RecoveryDisposition.CONTINUE,
                "host remains independently healthy; agent recovery may proceed without authority transfer",
            )

        raise RuntimeError("unhandled fleet failure")

    @staticmethod
    def _decision(
        host_state: FleetHostState,
        workload_state: FleetWorkloadState,
        failure: FleetFailure,
        disposition: RecoveryDisposition,
        reason: str,
        *,
        requires_state_verified: bool = False,
        requires_source_fenced: bool = False,
        requires_witness_quorum: bool = False,
        requires_operator_approval: bool = False,
    ) -> FleetRecoveryDecision:
        return FleetRecoveryDecision(
            host_state=host_state,
            workload_state=workload_state,
            failure=failure,
            disposition=disposition,
            reason=reason,
            requires_state_verified=requires_state_verified,
            requires_source_fenced=requires_source_fenced,
            requires_witness_quorum=requires_witness_quorum,
            requires_operator_approval=requires_operator_approval,
        )
