"""Typed, authority-free persistent goal domain models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from sofia.capability.model import CapabilityProposal


SOFIA_GOAL_OWNER_ID = "sofia:self"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


class GoalOrigin(str, Enum):
    USER = "user"
    SELF = "self"
    SYSTEM = "system"
    MAINTENANCE = "maintenance"


class GoalStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class CompletionKind(str, Enum):
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    EVIDENCE_TRUE = "evidence_true"
    OPERATION_RECEIPT = "operation_receipt"
    NO_RECURRENCE = "no_recurrence"
    ALL_CHILDREN = "all_children"
    USER_DEFINED = "user_defined"


class GoalPolicyDecision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    ASK_USER = "ask_user"
    MERGE = "merge"


class GoalRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GoalCost(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GoalRunState(str, Enum):
    NONE = "none"
    PENDING_INSPECTION = "pending_inspection"
    SCHEDULED_RECHECK = "scheduled_recheck"
    WAITING_EVIDENCE = "waiting_evidence"
    WAITING_DEADLINE = "waiting_deadline"
    BLOCKED_APPROVAL = "blocked_approval"


TERMINAL_GOAL_STATUSES = frozenset({
    GoalStatus.COMPLETED,
    GoalStatus.REJECTED,
    GoalStatus.CANCELLED,
    GoalStatus.EXPIRED,
    GoalStatus.SUPERSEDED,
})


ALLOWED_TRANSITIONS = {
    GoalStatus.CANDIDATE: frozenset({
        GoalStatus.ACTIVE, GoalStatus.REJECTED, GoalStatus.CANCELLED,
        GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
    }),
    GoalStatus.ACTIVE: frozenset({
        GoalStatus.PAUSED, GoalStatus.BLOCKED, GoalStatus.COMPLETED,
        GoalStatus.CANCELLED, GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
    }),
    GoalStatus.PAUSED: frozenset({
        GoalStatus.ACTIVE, GoalStatus.CANCELLED, GoalStatus.EXPIRED,
        GoalStatus.SUPERSEDED,
    }),
    GoalStatus.BLOCKED: frozenset({
        GoalStatus.ACTIVE, GoalStatus.PAUSED, GoalStatus.CANCELLED,
        GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
    }),
}


def validate_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded identifier")


def validate_time(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


def validate_refs(refs: tuple[str, ...], name: str, *, maximum: int = 32) -> None:
    if (
        not isinstance(refs, tuple)
        or len(refs) > maximum
        or len(set(refs)) != len(refs)
        or any(_IDENTIFIER.fullmatch(ref) is None for ref in refs)
    ):
        raise ValueError(f"{name} must contain distinct bounded evidence references")


@dataclass(frozen=True, slots=True)
class GoalCompletionCondition:
    kind: CompletionKind
    description: str
    no_recurrence_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CompletionKind):
            raise TypeError("completion kind must be CompletionKind")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description) > 320
        ):
            raise ValueError("completion description must be bounded and nonempty")
        if self.kind is CompletionKind.NO_RECURRENCE:
            if (
                type(self.no_recurrence_seconds) is not int
                or not 60 <= self.no_recurrence_seconds <= 31_536_000
            ):
                raise ValueError("no-recurrence completion requires a bounded duration")
        elif self.no_recurrence_seconds is not None:
            raise ValueError("only no-recurrence completion accepts a duration")


@dataclass(frozen=True, slots=True)
class GoalLifecycleEvent:
    event_id: str
    from_status: GoalStatus | None
    to_status: GoalStatus
    actor_principal_id: str
    occurred_at: datetime
    evidence_refs: tuple[str, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.event_id, "event_id")
        if self.from_status is not None and not isinstance(
            self.from_status, GoalStatus
        ):
            raise TypeError("from_status must be GoalStatus or None")
        if not isinstance(self.to_status, GoalStatus):
            raise TypeError("to_status must be GoalStatus")
        validate_identifier(self.actor_principal_id, "actor_principal_id")
        validate_time(self.occurred_at, "occurred_at")
        validate_refs(self.evidence_refs, "event evidence_refs")
        if self.note is not None and (
            not isinstance(self.note, str)
            or not self.note.strip()
            or len(self.note) > 320
        ):
            raise ValueError("event note must be None or bounded nonempty text")


@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    origin: GoalOrigin
    owner_principal_id: str
    scope_principal_id: str | None
    scope_audience: str | None
    title: str
    reason: str
    status: GoalStatus
    base_priority: float
    confidence: float
    created_at: datetime
    updated_at: datetime
    evidence_refs: tuple[str, ...]
    completion: GoalCompletionCondition
    history: tuple[GoalLifecycleEvent, ...]
    parent_goal_id: str | None = None
    blocked_reason: str | None = None
    completion_evidence: tuple[str, ...] = ()
    expires_at: datetime | None = None
    superseded_by: str | None = None
    run_state: GoalRunState = GoalRunState.NONE
    revision: int = 1

    def __post_init__(self) -> None:
        validate_identifier(self.id, "goal id")
        if not isinstance(self.origin, GoalOrigin):
            raise TypeError("origin must be GoalOrigin")
        validate_identifier(self.owner_principal_id, "owner_principal_id")
        if self.scope_principal_id is not None:
            validate_identifier(self.scope_principal_id, "scope_principal_id")
        if self.scope_audience is not None:
            validate_identifier(self.scope_audience, "scope_audience")
        if (self.scope_principal_id is None) != (self.scope_audience is None):
            raise ValueError("principal and audience goal scope must be supplied together")
        if self.origin is GoalOrigin.USER:
            if self.scope_principal_id != self.owner_principal_id:
                raise ValueError("USER goals must be scoped to their authenticated owner")
        elif self.owner_principal_id != SOFIA_GOAL_OWNER_ID:
            raise ValueError("non-USER goals must be owned by Sofía")
        for name, value, maximum in (
            ("title", self.title, 180),
            ("reason", self.reason, 640),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
            ):
                raise ValueError(f"{name} must be bounded and nonempty")
        if not isinstance(self.status, GoalStatus):
            raise TypeError("status must be GoalStatus")
        for name, value in (
            ("base_priority", self.base_priority),
            ("confidence", self.confidence),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in 0..1")
        validate_time(self.created_at, "created_at")
        validate_time(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        validate_refs(self.evidence_refs, "evidence_refs")
        validate_refs(self.completion_evidence, "completion_evidence")
        if not isinstance(self.completion, GoalCompletionCondition):
            raise TypeError("completion must be GoalCompletionCondition")
        if (
            not isinstance(self.history, tuple)
            or not self.history
            or any(not isinstance(item, GoalLifecycleEvent) for item in self.history)
        ):
            raise ValueError("goal requires immutable lifecycle history")
        if self.history[-1].to_status is not self.status:
            raise ValueError("latest lifecycle event must match goal status")
        if self.parent_goal_id is not None:
            validate_identifier(self.parent_goal_id, "parent_goal_id")
            if self.parent_goal_id == self.id:
                raise ValueError("goal cannot parent itself")
        if self.blocked_reason is not None and (
            not isinstance(self.blocked_reason, str)
            or not self.blocked_reason.strip()
            or len(self.blocked_reason) > 320
        ):
            raise ValueError("blocked_reason must be bounded text")
        if self.status is GoalStatus.BLOCKED and self.blocked_reason is None:
            raise ValueError("blocked goals require a reason")
        if self.status is GoalStatus.COMPLETED and not self.completion_evidence:
            raise ValueError("completed goals require verified completion evidence")
        if self.expires_at is not None:
            validate_time(self.expires_at, "expires_at")
            if self.expires_at <= self.created_at:
                raise ValueError("expires_at must follow created_at")
        if (
            self.origin is not GoalOrigin.USER
            and self.status not in TERMINAL_GOAL_STATUSES
            and self.expires_at is None
        ):
            raise ValueError("autonomous goals require an explicit expiration")
        if self.status is GoalStatus.EXPIRED and (
            self.expires_at is None or self.updated_at < self.expires_at
        ):
            raise ValueError("expired goal requires reached expiration")
        if self.status is GoalStatus.SUPERSEDED:
            if self.superseded_by is None:
                raise ValueError("superseded goal requires replacement goal id")
            validate_identifier(self.superseded_by, "superseded_by")
        elif self.superseded_by is not None:
            raise ValueError("only superseded goals name a replacement")
        if not isinstance(self.run_state, GoalRunState):
            raise TypeError("run_state must be GoalRunState")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True, slots=True)
class GoalCandidate:
    candidate_id: str
    origin: GoalOrigin
    owner_principal_id: str
    scope_principal_id: str | None
    scope_audience: str | None
    title: str
    reason: str
    proposed_priority: float
    confidence: float
    urgency: float
    risk: GoalRisk
    cost: GoalCost
    evidence_refs: tuple[str, ...]
    source_activation: str
    completion: GoalCompletionCondition
    created_at: datetime
    expires_at: datetime | None
    parent_goal_id: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.candidate_id, "candidate_id")
        validate_identifier(self.owner_principal_id, "owner_principal_id")
        if not isinstance(self.origin, GoalOrigin):
            raise TypeError("origin must be GoalOrigin")
        if self.origin is GoalOrigin.USER:
            raise ValueError("NEURO candidates cannot impersonate USER goals")
        if self.owner_principal_id != SOFIA_GOAL_OWNER_ID:
            raise ValueError("autonomous candidates must be owned by Sofía")
        if self.scope_principal_id is not None:
            validate_identifier(self.scope_principal_id, "scope_principal_id")
        if self.scope_audience is not None:
            validate_identifier(self.scope_audience, "scope_audience")
        if (self.scope_principal_id is None) != (self.scope_audience is None):
            raise ValueError("candidate scope must provide principal and audience together")
        for name, value, maximum in (
            ("title", self.title, 180), ("reason", self.reason, 640),
            ("source_activation", self.source_activation, 160),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} must be bounded and nonempty")
        for name, value in (
            ("proposed_priority", self.proposed_priority),
            ("confidence", self.confidence), ("urgency", self.urgency),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in 0..1")
        if not isinstance(self.risk, GoalRisk) or not isinstance(self.cost, GoalCost):
            raise TypeError("candidate risk/cost must be typed")
        validate_refs(self.evidence_refs, "candidate evidence_refs")
        if not self.evidence_refs:
            raise ValueError("autonomous candidate requires host evidence references")
        if not isinstance(self.completion, GoalCompletionCondition):
            raise TypeError("candidate requires a typed completion condition")
        validate_time(self.created_at, "created_at")
        if self.expires_at is None:
            raise ValueError("autonomous candidate requires expiration")
        validate_time(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("candidate expiration must follow creation")
        if self.parent_goal_id is not None:
            validate_identifier(self.parent_goal_id, "parent_goal_id")


@dataclass(frozen=True, slots=True)
class GoalPolicyResult:
    decision: GoalPolicyDecision
    reason: str
    duplicate_goal_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.decision, GoalPolicyDecision):
            raise TypeError("decision must be GoalPolicyDecision")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("policy reason must be nonempty")
        if self.duplicate_goal_id is not None:
            validate_identifier(self.duplicate_goal_id, "duplicate_goal_id")
        if (self.decision is GoalPolicyDecision.MERGE) != (
            self.duplicate_goal_id is not None
        ):
            raise ValueError("MERGE alone requires a duplicate goal id")


@dataclass(frozen=True, slots=True)
class GoalPriority:
    value: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("effective priority must be bounded")
        if not self.reasons:
            raise ValueError("priority calculation requires diagnostics")


@dataclass(frozen=True, slots=True)
class GoalActionProposal:
    goal_id: str
    proposal: CapabilityProposal

    def __post_init__(self) -> None:
        validate_identifier(self.goal_id, "goal_id")
        if not isinstance(self.proposal, CapabilityProposal):
            raise TypeError("proposal must be CapabilityProposal")
