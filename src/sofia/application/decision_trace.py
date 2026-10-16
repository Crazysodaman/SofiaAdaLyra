"""Read-only source-grounded decision diagnostics for one companion turn.

The authoritative records are owned by Cognition v2/Matrix, NEURO, LIFE,
MEMORY, SAFE, RUN and ACT. This module writes nothing. In particular, a
recent NEURO snapshot cannot be assumed to have caused an unrelated turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.application.decision_persistence import CompanionTurnPersistence
from sofia.application.event_contracts import (
    EventOwnershipProjection,
    project_matrix_event,
)
from sofia.cognition.matrix.model import MatrixTrace, EvidenceState
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
    canonical_persistence: CompanionTurnPersistence | None = None
    neuro_observed_for_turn_at: datetime | None = None
    source_event: EventOwnershipProjection | None = None
    neuro_winner: "DecisionAlternative | None" = None
    rejected_alternatives: tuple["DecisionAlternative", ...] = ()
    eligible_memory_refs: tuple[str, ...] = ()
    referenced_goal_refs: tuple[str, ...] = ()
    referenced_activity_refs: tuple[str, ...] = ()
    execution_decision: "ExecutionDecision | None" = None
    outcomes: tuple["DecisionOutcome", ...] = ()

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "diagnostic projection only; never authority or proof of action",
            "same-turn NEURO observation is ephemeral, not proof of causal use",
            "goal/LIFE/ACT outcomes are absent without typed source references",
            "evidence references are not automatically independent validation",
        )


@dataclass(frozen=True, slots=True)
class DecisionAlternative:
    source: str
    kind: str
    key: str
    score: float
    selected: bool
    observed_at: datetime

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.source, self.kind, self.key)
        ):
            raise ValueError("decision alternative identifiers must be nonempty")
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, (int, float))
            or not 0.0 <= float(self.score) <= 1.0
        ):
            raise ValueError("decision alternative score must be in 0..1")
        if type(self.selected) is not bool:
            raise TypeError("selected must be bool")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("alternative observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ExecutionDecision:
    authority_result: str | None
    exposed_capabilities: tuple[str, ...]
    route: str | None
    model_steps: tuple[str, ...]
    external_effect_claimed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.exposed_capabilities, tuple):
            raise TypeError("exposed_capabilities must be a tuple")
        if not isinstance(self.model_steps, tuple):
            raise TypeError("model_steps must be a tuple")
        if type(self.external_effect_claimed) is not bool:
            raise TypeError("external_effect_claimed must be bool")


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    kind: str
    status: str
    source_ref: str | None
    independently_verified: bool

    def __post_init__(self) -> None:
        if not self.kind or not self.status:
            raise ValueError("decision outcome kind/status must be nonempty")
        if type(self.independently_verified) is not bool:
            raise TypeError("independently_verified must be bool")


def project_companion_decision(
    *,
    matrix_trace: MatrixTrace | None,
    neuro_snapshot: NeuroStateSnapshot | None,
    canonical_persistence: CompanionTurnPersistence | None = None,
    neuro_turn_snapshot: NeuroStateSnapshot | None = None,
    selected_goal_event: EventOwnershipProjection | None = None,
    selected_activity_event: EventOwnershipProjection | None = None,
    outcome_events: tuple[EventOwnershipProjection, ...] = (),
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

    if neuro_turn_snapshot is not None:
        if not isinstance(neuro_turn_snapshot, NeuroStateSnapshot):
            raise TypeError("neuro_turn_snapshot must be a NEURO observation")
        if neuro_turn_snapshot.generated_at > matrix_trace.created_at:
            raise ValueError("NEURO observation cannot follow the completed decision")
    if canonical_persistence is not None:
        if not isinstance(canonical_persistence, CompanionTurnPersistence):
            raise TypeError("canonical_persistence must be typed proof or None")
        if (
            canonical_persistence.message_id != matrix_trace.envelope.message_id
            or canonical_persistence.session_id != matrix_trace.envelope.session_id
        ):
            raise ValueError("canonical proof belongs to another turn")
    for event, expected, label in (
        (selected_goal_event, "goals", "selected_goal_event"),
        (selected_activity_event, "life", "selected_activity_event"),
    ):
        if event is None:
            continue
        if not isinstance(event, EventOwnershipProjection):
            raise TypeError(f"{label} must be a typed event projection")
        if event.owner.value != expected:
            raise ValueError(f"{label} has the wrong canonical owner")
        if event.observed_at > matrix_trace.created_at:
            raise ValueError(f"{label} cannot postdate the decision")
    if not isinstance(outcome_events, tuple) or any(
        not isinstance(event, EventOwnershipProjection)
        for event in outcome_events
    ):
        raise TypeError("outcome_events must contain typed event projections")
    selected_events = tuple(
        event for event in (selected_goal_event, selected_activity_event)
        if event is not None
    )
    for event in (*selected_events, *outcome_events):
        if event.principal_id is not None and (
            matrix_trace.envelope.principal_id != event.principal_id
            or matrix_trace.privacy is None
            or matrix_trace.privacy.audience_id != event.audience_id
        ):
            raise PermissionError("decision event crosses principal/audience scope")

    # A response's evidence_refs are *claims*, even when their bytes were
    # durably settled in canonical SQLite. They are useful for diagnostics
    # but cannot independently link GOALS, LIFE or ACT source-owned events.
    # Require a Matrix-side evidence reference recorded for this turn.
    # Event identity or timestamp alone is never a causal attestation.
    linked_refs = {
        record.source_ref
        for record in (() if matrix_trace.evidence is None
                       else matrix_trace.evidence.records)
        if record.source_ref is not None
        and record.state is EvidenceState.AVAILABLE
    }
    for event in selected_events:
        source_keys = {event.event_id, event.source_id,
                       event.goal_id, event.project_id}
        if not source_keys.intersection(linked_refs):
            raise ValueError("selected decision event lacks same-turn source reference")
    for event in outcome_events:
        source_keys = {event.event_id, event.source_id, event.action_id}
        if not source_keys.intersection(linked_refs):
            raise ValueError("outcome event lacks same-turn source reference")

    refs: list[str] = []
    if matrix_trace.evidence is not None:
        for item in matrix_trace.evidence.records:
            if item.source_ref and item.source_ref not in refs:
                refs.append(item.source_ref)
    if canonical_persistence is not None:
        for item in canonical_persistence.response_evidence_refs:
            if item not in refs:
                refs.append(item)

    winner = None
    rejected = ()
    if neuro_turn_snapshot is not None:
        if neuro_turn_snapshot.focus is not None:
            item = neuro_turn_snapshot.focus
            winner = DecisionAlternative(
                item.source, item.kind, item.key, item.score, True,
                item.updated_at,
            )
        rejected = tuple(
            DecisionAlternative(
                item.source, item.kind, item.key, item.score, False,
                item.updated_at,
            )
            for item in neuro_turn_snapshot.secondary
        )

    # Only AVAILABLE Matrix evidence is eligible for downstream context.
    # Stale/unknown claims remain visible as references for diagnosis, not
    # as eligible memories or chosen GOALS/LIFE activity.
    memory_refs = tuple(
        ref for ref in refs
        if ref in linked_refs
        and ref.startswith(("memory:", "conversation-retrieval:"))
    )
    goal_refs = tuple(ref for ref in refs
                      if ref in linked_refs and ref.startswith("goal:"))
    activity_refs = tuple(ref for ref in refs
                          if ref in linked_refs and ref.startswith("life:"))
    execution = ExecutionDecision(
        authority_result=(
            None if matrix_trace.authority is None
            else matrix_trace.authority.decision.value
        ),
        exposed_capabilities=(
            () if matrix_trace.tool_exposure is None
            else matrix_trace.tool_exposure.capabilities
        ),
        route=(
            None if matrix_trace.cognition_execution is None
            else matrix_trace.cognition_execution.actual_route
        ),
        model_steps=(
            () if matrix_trace.cognition_execution is None else tuple(
                f"{step.role}:{step.model or 'unknown'}@{step.host or 'unknown'}:"
                f"{'succeeded' if step.succeeded else 'failed'}"
                for step in matrix_trace.cognition_execution.steps
            )
        ),
    )
    outcomes: list[DecisionOutcome] = []
    if matrix_trace.response_validation is not None:
        outcomes.append(DecisionOutcome(
            "response_validation",
            matrix_trace.response_validation.disposition.value,
            matrix_trace.envelope.message_id,
            False,
        ))
    if canonical_persistence is not None:
        outcomes.append(DecisionOutcome(
            "canonical_response",
            "settled" if canonical_persistence.canonical_turn_settled else "unverified",
            canonical_persistence.assistant_message_id,
            # Cross-table settlement establishes canonical durability,
            # not independent, human-reviewed answer/effect validation.
            False,
        ))
    for event in outcome_events:
        outcomes.append(DecisionOutcome(
            kind=f"{event.owner.value}_event",
            status=event.error_state.value,
            source_ref=(
                event.delivery_receipt_id or event.action_id or event.event_id
            ),
            # Source-projected ACT acknowledgement is not independently
            # authenticated evidence that the external effect occurred.
            independently_verified=False,
        ))

    return CompanionDecisionTrace(
        schema_version=2,
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
        neuro_turn_correlated=neuro_turn_snapshot is not None,
        goal_id=(
            None if selected_goal_event is None
            else selected_goal_event.goal_id
        ),
        life_project_id=(
            None if selected_activity_event is None
            else selected_activity_event.project_id
        ),
        canonical_persistence=canonical_persistence,
        neuro_observed_for_turn_at=(
            None if neuro_turn_snapshot is None
            else neuro_turn_snapshot.generated_at
        ),
        source_event=project_matrix_event(
            matrix_trace, persistence=canonical_persistence,
        ),
        neuro_winner=winner,
        rejected_alternatives=rejected,
        eligible_memory_refs=memory_refs,
        referenced_goal_refs=goal_refs,
        referenced_activity_refs=activity_refs,
        execution_decision=execution,
        outcomes=tuple(outcomes),
    )
