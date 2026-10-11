"""Read-only source-grounded decision diagnostics for one companion turn.

The authoritative records are owned by Cognition v2/Matrix, NEURO, LIFE,
MEMORY, SAFE, RUN and ACT. This module writes nothing. In particular, a
recent NEURO snapshot cannot be assumed to have caused an unrelated turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.cognition.matrix.model import MatrixTrace
from sofia.neuro.model import NeuroStateSnapshot


@dataclass(frozen=True, slots=True)
class CompanionDecisionTrace:
    """Content-minimal view, never an execution or evaluation receipt."""

    schema_version: int
    message_id: str
    session_id: str
    principal_id: str | None
    channel: str
    decided_at: datetime
    intent: str
    history_policy: str
    response_strategy: str
    planned_route: str | None
    executed_route: str | None
    authority_result: str | None
    response_disposition: str | None
    referenced_evidence: tuple[str, ...]
    neuro_latest_at: datetime | None
    neuro_turn_correlated: bool
    goal_id: str | None = None
    life_project_id: str | None = None
    act_delivery_ref: str | None = None
    objective_verified: bool = False

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "diagnostic projection only; never authority or proof of action",
            "NEURO snapshot is not turn-correlated unless explicit provenance exists",
            "goal/LIFE/ACT outcomes not joined without typed source references",
            "evidence references are not automatically independent validation",
        )


def project_companion_decision(
    *,
    matrix_trace: MatrixTrace | None,
    neuro_snapshot: NeuroStateSnapshot | None,
) -> CompanionDecisionTrace | None:
    """Project only typed observations, never infer cause or success.

    A latest NEURO snapshot is exposed by timestamp *as separate context*.
    Cross-system proof will require a common, versioned turn/event ID.
    """
    if matrix_trace is None:
        return None
    if not isinstance(matrix_trace, MatrixTrace):
        raise TypeError("matrix_trace must be MatrixTrace or None")
    if neuro_snapshot is not None and not isinstance(
        neuro_snapshot, NeuroStateSnapshot
    ):
        raise TypeError("neuro_snapshot must be NeuroStateSnapshot or None")

    refs: list[str] = []
    if matrix_trace.evidence is not None:
        for item in matrix_trace.evidence.records:
            if item.source_ref and item.source_ref not in refs:
                refs.append(item.source_ref)

    return CompanionDecisionTrace(
        schema_version=1,
        message_id=matrix_trace.envelope.message_id,
        session_id=matrix_trace.envelope.session_id,
        principal_id=matrix_trace.envelope.principal_id,
        channel=matrix_trace.envelope.channel,
        decided_at=matrix_trace.created_at,
        intent=matrix_trace.turn.intent.value,
        history_policy=matrix_trace.turn.history_policy.value,
        response_strategy=matrix_trace.turn.response_strategy.value,
        planned_route=(
            None if matrix_trace.routing is None
            else matrix_trace.routing.route.value
        ),
        executed_route=(
            None if matrix_trace.cognition_execution is None
            else matrix_trace.cognition_execution.actual_route
        ),
        authority_result=(
            None if matrix_trace.authority is None
            else matrix_trace.authority.decision.value
        ),
        response_disposition=(
            None if matrix_trace.response_validation is None
            else matrix_trace.response_validation.disposition.value
        ),
        referenced_evidence=tuple(refs),
        neuro_latest_at=(
            None if neuro_snapshot is None else neuro_snapshot.generated_at
        ),
        neuro_turn_correlated=False,
    )
