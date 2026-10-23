"""Typed, read-only source-to-sink contracts for companion events (CA-003/005).

The records in this module are projections over existing canonical owners.  They
do not create an event ledger, grant authority, validate evidence, or turn a
delivery acknowledgement into proof that a person observed a message.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
import re

from sofia.platform.application.decision_persistence import CompanionTurnPersistence
from sofia.core.cognition.matrix.model import MatrixTrace


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,199}$")


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded machine-safe identifier")
    return value


def _optional_id(value: str | None, label: str) -> str | None:
    if value is not None:
        _id(value, label)
    return value


class CanonicalEventOwner(str, Enum):
    CONVERSATION = "conversation"
    MATRIX = "cognition_v2_matrix"
    NEURO = "neuro"
    MEMORY = "memory"
    GOALS = "goals"
    LIFE = "life"
    RUN = "run"
    SAFE = "safe"
    ACT = "act"


class ContractErrorState(str, Enum):
    NONE = "none"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class EventOwnershipProjection:
    """Content-free event envelope whose values remain source-owned."""

    schema_version: int
    event_id: str
    owner: CanonicalEventOwner
    source_id: str
    subject_id: str | None
    principal_id: str | None
    audience_id: str | None
    observed_at: datetime
    expires_at: datetime | None = None
    confidence: float | None = None
    evidence_refs: tuple[str, ...] = ()
    action_id: str | None = None
    goal_id: str | None = None
    project_id: str | None = None
    consent_classification: str | None = None
    delivery_receipt_id: str | None = None
    resource_refs: tuple[str, ...] = ()
    error_state: ContractErrorState = ContractErrorState.NONE
    expected_effect: "ExpectedEffectProjection | None" = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported event ownership projection version")
        for value, label in (
            (self.event_id, "event_id"), (self.source_id, "source_id"),
        ):
            _id(value, label)
        if not isinstance(self.owner, CanonicalEventOwner):
            raise TypeError("owner must be CanonicalEventOwner")
        for value, label in (
            (self.subject_id, "subject_id"),
            (self.principal_id, "principal_id"),
            (self.audience_id, "audience_id"),
            (self.action_id, "action_id"), (self.goal_id, "goal_id"),
            (self.project_id, "project_id"),
            (self.consent_classification, "consent_classification"),
            (self.delivery_receipt_id, "delivery_receipt_id"),
        ):
            _optional_id(value, label)
        if (self.principal_id is None) != (self.audience_id is None):
            raise ValueError("principal and audience must be present together")
        if not isinstance(self.observed_at, datetime) or (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime) or (
                self.expires_at.tzinfo is None
                or self.expires_at.utcoffset() is None
            ):
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at < self.observed_at:
                raise ValueError("expires_at cannot precede observed_at")
        if self.confidence is not None and (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(float(self.confidence))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("confidence must be None or a finite value in 0..1")
        for values, label in (
            (self.evidence_refs, "evidence_refs"),
            (self.resource_refs, "resource_refs"),
        ):
            if not isinstance(values, tuple) or len(values) > 64:
                raise ValueError(f"{label} must be a bounded tuple")
            for value in values:
                _id(value, label)
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")
        if not isinstance(self.error_state, ContractErrorState):
            raise TypeError("error_state must be ContractErrorState")
        if self.expected_effect is not None:
            if not isinstance(self.expected_effect, ExpectedEffectProjection):
                raise TypeError("expected_effect must be a typed projection")
            if (
                self.expected_effect.owner is not self.owner
                or self.expected_effect.action_id != self.action_id
            ):
                raise ValueError("expected_effect belongs to another action")

    @property
    def can_authorize(self) -> bool:
        """A projection is deliberately incapable of authorization."""
        return False


@dataclass(frozen=True, slots=True)
class ExpectedEffectProjection:
    """Read-only settlement contract for one already-authorized optional action.

    This projection cannot execute, retry, or authorize the action.  Settling a
    narrowly defined transport/job effect also never proves a larger GOAL or
    LIFE objective.
    """

    schema_version: int
    owner: CanonicalEventOwner
    action_id: str
    expected_effect: str
    lifecycle_state: str
    expected_effect_satisfied: bool
    settlement_receipt_ref: str | None
    objective_verified: bool = False
    retry_permitted: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported expected-effect projection version")
        if self.owner not in (CanonicalEventOwner.RUN, CanonicalEventOwner.ACT):
            raise ValueError("expected-effect owner must be RUN or ACT")
        _id(self.action_id, "action_id")
        if (
            not isinstance(self.expected_effect, str)
            or not self.expected_effect.strip()
            or len(self.expected_effect) > 2_000
        ):
            raise ValueError("expected_effect must be nonempty and bounded")
        _id(self.lifecycle_state, "lifecycle_state")
        _optional_id(self.settlement_receipt_ref, "settlement_receipt_ref")
        for value, label in (
            (self.expected_effect_satisfied, "expected_effect_satisfied"),
            (self.objective_verified, "objective_verified"),
            (self.retry_permitted, "retry_permitted"),
        ):
            if type(value) is not bool:
                raise TypeError(f"{label} must be bool")
        if self.expected_effect_satisfied and self.settlement_receipt_ref is None:
            raise ValueError("a settled expected effect requires a receipt")
        if self.objective_verified:
            raise ValueError("RUN/ACT settlement cannot verify a larger objective")

    @property
    def can_authorize(self) -> bool:
        return False


def project_run_expected_effect(job) -> ExpectedEffectProjection:
    """Expose RUN's declared condition without upgrading executor success.

    A generic completed job has no uniformly typed independent receipt oracle.
    LIFE and other domain owners must perform their own exact receipt lookup;
    therefore this generic projection remains unsatisfied even when RUN reports
    COMPLETED.  UNCERTAIN is explicitly non-retryable.
    """
    from sofia.platform.run.work import WorkJob, WorkStatus

    if not isinstance(job, WorkJob):
        raise TypeError("canonical WorkJob required")
    lifecycle = (
        "reported_completed_unverified"
        if job.status is WorkStatus.COMPLETED else job.status.value
    )
    return ExpectedEffectProjection(
        schema_version=1,
        owner=CanonicalEventOwner.RUN,
        action_id=job.job_id,
        expected_effect=job.completion_condition,
        lifecycle_state=lifecycle,
        expected_effect_satisfied=False,
        settlement_receipt_ref=None,
        retry_permitted=False,
    )


def project_act_expected_effect(message, *, send_result=None) -> ExpectedEffectProjection:
    """Settle only ACT transport acceptance, never human observation."""
    from sofia.platform.act.delivery import BoundMessage, DeliveryOutcome, SendResult

    if not isinstance(message, BoundMessage):
        raise TypeError("canonical BoundMessage required")
    if send_result is not None and not isinstance(send_result, SendResult):
        raise TypeError("send_result must be SendResult or None")
    delivered = (
        send_result is not None
        and send_result.outcome is DeliveryOutcome.DELIVERED
    )
    state = "pending"
    if send_result is not None:
        state = send_result.outcome.value
    return ExpectedEffectProjection(
        schema_version=1,
        owner=CanonicalEventOwner.ACT,
        action_id=message.message_id,
        expected_effect=(
            "configured transport accepts the exact bound message for "
            + message.recipient_id
        ),
        lifecycle_state=state,
        expected_effect_satisfied=delivered,
        settlement_receipt_ref=(
            None if send_result is None else send_result.receipt_id
        ),
        # FAILED may follow normal bounded ACT retry policy. An unknown outcome
        # may already have delivered and is never automatically replayed.
        retry_permitted=(
            send_result is not None
            and send_result.outcome is DeliveryOutcome.FAILED
        ),
    )


def project_matrix_event(
    matrix_trace: MatrixTrace,
    *,
    persistence: CompanionTurnPersistence | None = None,
) -> EventOwnershipProjection:
    """Adapt a Matrix v2 turn without widening its authenticated scope."""
    if not isinstance(matrix_trace, MatrixTrace):
        raise TypeError("matrix_trace must be MatrixTrace")
    envelope = matrix_trace.envelope
    if persistence is not None:
        if not isinstance(persistence, CompanionTurnPersistence):
            raise TypeError("persistence must be CompanionTurnPersistence")
        if (
            persistence.message_id != envelope.message_id
            or persistence.session_id != envelope.session_id
        ):
            raise ValueError("persistence belongs to another turn")

    # Matrix's principal claim is projected only when the independent SOCIAL
    # binding was verified.  The channel is never substituted for an audience.
    scoped = bool(persistence and persistence.principal_scope_verified)
    audience = None if not scoped or persistence is None else persistence.verified_audience_id
    if (
        audience is not None
        and matrix_trace.privacy is not None
        and matrix_trace.privacy.audience_id != audience
    ):
        raise ValueError("Matrix privacy scope conflicts with canonical binding")
    principal = envelope.principal_id if scoped and audience is not None else None
    refs = tuple(dict.fromkeys((
        *(() if persistence is None else persistence.response_evidence_refs),
        *(
            record.source_ref
            for record in (
                () if matrix_trace.evidence is None
                else matrix_trace.evidence.records
            )
            if record.source_ref is not None
        ),
    )))
    return EventOwnershipProjection(
        schema_version=1,
        event_id=(
            persistence.canonical_event_id
            if persistence is not None and persistence.canonical_event_id
            else envelope.message_id
        ),
        owner=CanonicalEventOwner.MATRIX,
        source_id=envelope.message_id,
        subject_id=envelope.session_id,
        principal_id=principal,
        audience_id=audience,
        observed_at=envelope.created_at,
        confidence={"low": 0.34, "medium": 0.67, "high": 1.0}[
            matrix_trace.turn.confidence.value
        ],
        evidence_refs=refs,
        # Matrix authority is not consent. Only the SAFE/INTERACT owner may
        # populate this field through a corresponding typed adapter.
        consent_classification=None,
        error_state=(
            ContractErrorState.NONE
            if persistence is None or persistence.canonical_turn_settled
            else ContractErrorState.UNCERTAIN
        ),
    )


def project_goal_event(goal, event) -> EventOwnershipProjection:
    """Adapt one lifecycle event already present in a canonical Goal."""
    from sofia.core.goals.model import Goal, GoalLifecycleEvent

    if not isinstance(goal, Goal) or not isinstance(event, GoalLifecycleEvent):
        raise TypeError("canonical Goal and GoalLifecycleEvent required")
    if event not in goal.history:
        raise ValueError("goal event is not part of the supplied goal revision")
    return EventOwnershipProjection(
        schema_version=1, event_id=event.event_id,
        owner=CanonicalEventOwner.GOALS, source_id=event.event_id,
        subject_id=goal.id,
        principal_id=goal.scope_principal_id,
        audience_id=goal.scope_audience,
        observed_at=event.occurred_at, expires_at=goal.expires_at,
        confidence=goal.confidence, evidence_refs=event.evidence_refs,
        goal_id=goal.id,
    )


def project_life_event(project, event) -> EventOwnershipProjection:
    """Adapt a LIFE event only when it belongs to the supplied project."""
    from sofia.core.life.model import LifeProject, ProjectEvent

    if not isinstance(project, LifeProject) or not isinstance(event, ProjectEvent):
        raise TypeError("canonical LifeProject and ProjectEvent required")
    if event.project_id != project.project_id:
        raise ValueError("project event belongs to another project")
    return EventOwnershipProjection(
        schema_version=1, event_id=event.event_id,
        owner=CanonicalEventOwner.LIFE, source_id=event.event_id,
        subject_id=project.project_id,
        principal_id=project.owner_principal_id,
        audience_id=project.audience_id,
        observed_at=event.occurred_at, confidence=project.confidence,
        evidence_refs=event.evidence_refs, goal_id=project.goal_id,
        project_id=project.project_id,
    )


def project_run_job(job) -> EventOwnershipProjection:
    """Adapt a RUN job state; a terminal status is not proof of its effect."""
    from sofia.platform.run.work import WorkJob, WorkStatus

    if not isinstance(job, WorkJob):
        raise TypeError("canonical WorkJob required")
    errors = {
        WorkStatus.FAILED: ContractErrorState.FAILED,
        WorkStatus.UNCERTAIN: ContractErrorState.UNCERTAIN,
        WorkStatus.CANCELLED: ContractErrorState.REVOKED,
    }
    project_id = job.payload.get("project_id")
    if project_id is not None:
        _id(project_id, "RUN project_id")
    return EventOwnershipProjection(
        schema_version=1, event_id=job.job_id,
        owner=CanonicalEventOwner.RUN, source_id=job.job_id,
        subject_id=job.kind, principal_id=None, audience_id=None,
        observed_at=job.updated_at, expires_at=job.deadline,
        action_id=job.job_id, project_id=project_id,
        error_state=errors.get(job.status, ContractErrorState.NONE),
        expected_effect=project_run_expected_effect(job),
    )


def project_act_delivery(message, *, send_result=None) -> EventOwnershipProjection:
    """Adapt an ACT envelope and its transport result without claiming receipt."""
    from sofia.platform.act.delivery import BoundMessage, SendResult, DeliveryOutcome

    if not isinstance(message, BoundMessage):
        raise TypeError("canonical BoundMessage required")
    if send_result is not None and not isinstance(send_result, SendResult):
        raise TypeError("send_result must be SendResult or None")
    state = ContractErrorState.NONE
    if send_result is not None:
        if send_result.outcome is DeliveryOutcome.FAILED:
            state = ContractErrorState.FAILED
        elif send_result.outcome is DeliveryOutcome.OUTCOME_UNKNOWN:
            state = ContractErrorState.UNCERTAIN
    return EventOwnershipProjection(
        schema_version=1, event_id=message.message_id,
        owner=CanonicalEventOwner.ACT, source_id=message.message_id,
        subject_id=message.recipient_id, principal_id=None, audience_id=None,
        observed_at=message.created_at, expires_at=message.expires_at,
        evidence_refs=(message.evidence_id,), goal_id=message.goal_id,
        action_id=message.message_id,
        delivery_receipt_id=(
            None if send_result is None else send_result.receipt_id
        ),
        error_state=state,
        expected_effect=project_act_expected_effect(
            message, send_result=send_result,
        ),
    )
# This is documentation executable by tests/UI rather than a competing store.
EVENT_FIELD_OWNERS: dict[str, tuple[CanonicalEventOwner, ...]] = {
    "event_id": tuple(CanonicalEventOwner),
    "source_id": tuple(CanonicalEventOwner),
    "subject_id": tuple(CanonicalEventOwner),
    "principal_id": (
        CanonicalEventOwner.CONVERSATION, CanonicalEventOwner.MATRIX,
        CanonicalEventOwner.GOALS, CanonicalEventOwner.LIFE,
        CanonicalEventOwner.SAFE, CanonicalEventOwner.ACT,
    ),
    "audience_id": (
        CanonicalEventOwner.CONVERSATION, CanonicalEventOwner.MATRIX,
        CanonicalEventOwner.MEMORY, CanonicalEventOwner.GOALS,
        CanonicalEventOwner.LIFE, CanonicalEventOwner.ACT,
    ),
    "observed_at": tuple(CanonicalEventOwner),
    "expires_at": (
        CanonicalEventOwner.MEMORY, CanonicalEventOwner.GOALS,
        CanonicalEventOwner.RUN, CanonicalEventOwner.SAFE,
        CanonicalEventOwner.ACT,
    ),
    "confidence": (
        CanonicalEventOwner.MATRIX, CanonicalEventOwner.NEURO,
        CanonicalEventOwner.MEMORY, CanonicalEventOwner.GOALS,
        CanonicalEventOwner.LIFE,
    ),
    "evidence_refs": (
        CanonicalEventOwner.MATRIX, CanonicalEventOwner.MEMORY,
        CanonicalEventOwner.GOALS, CanonicalEventOwner.LIFE,
        CanonicalEventOwner.RUN,
    ),
    "action_id": (
        CanonicalEventOwner.RUN, CanonicalEventOwner.SAFE,
        CanonicalEventOwner.ACT,
    ),
    "goal_id": (CanonicalEventOwner.GOALS, CanonicalEventOwner.LIFE, CanonicalEventOwner.ACT),
    "project_id": (CanonicalEventOwner.LIFE, CanonicalEventOwner.RUN, CanonicalEventOwner.ACT),
    "consent_classification": (CanonicalEventOwner.SAFE,),
    "delivery_receipt_id": (CanonicalEventOwner.ACT,),
    "resource_refs": (CanonicalEventOwner.RUN, CanonicalEventOwner.LIFE),
    "error_state": tuple(CanonicalEventOwner),
    "expected_effect": (CanonicalEventOwner.RUN, CanonicalEventOwner.ACT),
}
