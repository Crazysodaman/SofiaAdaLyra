"""Typed ownership boundaries for the Cognition v2 migration.

These immutable contracts do not execute models, acquire evidence, mutate
canonical state, or grant authority. They are the shared hand-off vocabulary
for the sequential replacement batches described in the architecture record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Protocol


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")


def _identifier(name: str, value: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded machine-safe identifier")
    return value


def _text(name: str, value: str, *, limit: int = 8000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")
    normalized = value.strip()
    if len(normalized) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return normalized


def _aware(name: str, value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _identifiers(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    normalized = tuple(_identifier(name, value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return normalized


class EpistemicState(str, Enum):
    """What relationship a claim has to truth and evidence."""

    OBSERVED = "observed"
    KNOWN = "known"
    USER_REPORTED = "user_reported"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"


class AcquisitionState(str, Enum):
    """Whether current evidence could be acquired and relied upon."""

    CURRENT = "current"
    NOT_SAMPLED = "not_sampled"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    FAILED = "failed"
    CONTRADICTED = "contradicted"
    REVOKED = "revoked"


class ModelWorkerRole(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class CognitiveTaskKind(str, Enum):
    DETERMINISTIC = "deterministic"
    EVIDENCE_ACQUISITION = "evidence_acquisition"
    SEMANTIC_ANALYSIS = "semantic_analysis"
    REASONING = "reasoning"
    CRITIQUE = "critique"
    SYNTHESIS = "synthesis"
    CLAIM_VALIDATION = "claim_validation"
    RENDERING = "rendering"


@dataclass(frozen=True, slots=True)
class TurnKernelInput:
    """Authenticated, channel-scoped input accepted by the future Turn Kernel."""

    turn_id: str
    session_id: str
    content: str
    created_at: datetime
    channel: str
    principal_id: str | None
    audience_id: str | None

    def __post_init__(self) -> None:
        _identifier("turn_id", self.turn_id)
        _identifier("session_id", self.session_id)
        _text("content", self.content)
        _aware("created_at", self.created_at)
        _identifier("channel", self.channel)
        if (self.principal_id is None) != (self.audience_id is None):
            raise ValueError(
                "principal_id and audience_id must both be present or absent"
            )
        if self.principal_id is not None:
            _identifier("principal_id", self.principal_id)
            _identifier("audience_id", self.audience_id or "")


@dataclass(frozen=True, slots=True)
class FocusReference:
    """A discourse reference, not proof that the referenced subject exists."""

    reference_id: str
    subject_id: str
    kind: str
    source_turn_id: str
    confidence: float
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("reference_id", "subject_id", "kind", "source_turn_id"):
            _identifier(name, getattr(self, name))
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("confidence must be in 0..1")
        _identifiers("evidence_refs", self.evidence_refs)


@dataclass(frozen=True, slots=True)
class ConversationFocus:
    """Structured discourse state scoped to one session and audience."""

    session_id: str
    audience_id: str | None
    revision: int
    primary_reference: FocusReference | None = None
    active_topic_ids: tuple[str, ...] = ()
    unresolved_request_ids: tuple[str, ...] = ()
    pending_action_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier("session_id", self.session_id)
        if self.audience_id is not None:
            _identifier("audience_id", self.audience_id)
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative int")
        if self.primary_reference is not None and not isinstance(
            self.primary_reference, FocusReference
        ):
            raise TypeError("primary_reference must be FocusReference or None")
        for name in (
            "active_topic_ids",
            "unresolved_request_ids",
            "pending_action_ids",
        ):
            _identifiers(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class EvidenceNeed:
    """A subject-scoped requirement; it is not acquired evidence."""

    need_id: str
    subject_id: str
    predicate: str
    scope_id: str
    max_age_seconds: float | None = None
    minimum_trust: float = 0.0

    def __post_init__(self) -> None:
        for name in ("need_id", "subject_id", "predicate", "scope_id"):
            _identifier(name, getattr(self, name))
        if self.max_age_seconds is not None and (
            isinstance(self.max_age_seconds, bool)
            or not isinstance(self.max_age_seconds, (int, float))
            or self.max_age_seconds <= 0
        ):
            raise ValueError("max_age_seconds must be positive or None")
        if (
            isinstance(self.minimum_trust, bool)
            or not isinstance(self.minimum_trust, (int, float))
            or not 0.0 <= float(self.minimum_trust) <= 1.0
        ):
            raise ValueError("minimum_trust must be in 0..1")


@dataclass(frozen=True, slots=True)
class EvidenceAtom:
    """One provenance-linked fact candidate with explicit subject identity."""

    evidence_id: str
    subject_id: str
    predicate: str
    value_json: str
    source_id: str
    observed_at: datetime
    scope_id: str
    trust: float
    epistemic_state: EpistemicState
    acquisition_state: AcquisitionState
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "subject_id",
            "predicate",
            "source_id",
            "scope_id",
        ):
            _identifier(name, getattr(self, name))
        _text("value_json", self.value_json)
        _aware("observed_at", self.observed_at)
        if self.expires_at is not None:
            _aware("expires_at", self.expires_at)
            if self.expires_at < self.observed_at:
                raise ValueError("expires_at cannot precede observed_at")
        if (
            isinstance(self.trust, bool)
            or not isinstance(self.trust, (int, float))
            or not 0.0 <= float(self.trust) <= 1.0
        ):
            raise ValueError("trust must be in 0..1")
        if not isinstance(self.epistemic_state, EpistemicState):
            raise TypeError("epistemic_state must be EpistemicState")
        if not isinstance(self.acquisition_state, AcquisitionState):
            raise TypeError("acquisition_state must be AcquisitionState")


@dataclass(frozen=True, slots=True)
class CognitiveTask:
    task_id: str
    kind: CognitiveTaskKind
    depends_on: tuple[str, ...] = ()
    preferred_roles: tuple[ModelWorkerRole, ...] = ()
    required: bool = True
    token_budget: int | None = None
    time_budget_ms: int | None = None

    def __post_init__(self) -> None:
        _identifier("task_id", self.task_id)
        if not isinstance(self.kind, CognitiveTaskKind):
            raise TypeError("kind must be CognitiveTaskKind")
        _identifiers("depends_on", self.depends_on)
        if not isinstance(self.preferred_roles, tuple) or any(
            not isinstance(role, ModelWorkerRole)
            for role in self.preferred_roles
        ):
            raise TypeError("preferred_roles must contain ModelWorkerRole values")
        if len(set(self.preferred_roles)) != len(self.preferred_roles):
            raise ValueError("preferred_roles must not contain duplicates")
        if type(self.required) is not bool:
            raise TypeError("required must be bool")
        for name in ("token_budget", "time_budget_ms"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive int or None")


@dataclass(frozen=True, slots=True)
class CognitiveSchedule:
    schedule_id: str
    tasks: tuple[CognitiveTask, ...]
    parallel_groups: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        _identifier("schedule_id", self.schedule_id)
        if not isinstance(self.tasks, tuple) or not self.tasks:
            raise ValueError("tasks must be a nonempty tuple")
        if any(not isinstance(task, CognitiveTask) for task in self.tasks):
            raise TypeError("tasks must contain CognitiveTask values")
        task_ids = tuple(task.task_id for task in self.tasks)
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("task ids must be unique")
        known = set(task_ids)
        for task in self.tasks:
            if not set(task.depends_on) <= known:
                raise ValueError("task dependency references an unknown task")
            if task.task_id in task.depends_on:
                raise ValueError("task cannot depend on itself")
        dependencies = {
            task.task_id: set(task.depends_on) for task in self.tasks
        }

        def visit(task_id: str, path: set[str], complete: set[str]) -> None:
            if task_id in path:
                raise ValueError("task dependency graph contains a cycle")
            if task_id in complete:
                return
            path.add(task_id)
            for dependency in dependencies[task_id]:
                visit(dependency, path, complete)
            path.remove(task_id)
            complete.add(task_id)

        complete: set[str] = set()
        for task_id in task_ids:
            visit(task_id, set(), complete)
        for group in self.parallel_groups:
            members = _identifiers("parallel_group", group)
            if len(members) < 2 or not set(members) <= known:
                raise ValueError(
                    "parallel groups require at least two known task ids"
                )
            if any(
                other in dependencies[member]
                for member in members
                for other in members
                if member != other
            ):
                raise ValueError(
                    "parallel group members cannot depend on each other"
                )


@dataclass(frozen=True, slots=True)
class TurnPlan:
    turn_id: str
    focus_revision: int
    domains: tuple[str, ...]
    evidence_needs: tuple[EvidenceNeed, ...]
    schedule: CognitiveSchedule
    response_strategy: str
    action_requires_authority: bool

    def __post_init__(self) -> None:
        _identifier("turn_id", self.turn_id)
        if type(self.focus_revision) is not int or self.focus_revision < 0:
            raise ValueError("focus_revision must be a nonnegative int")
        _identifiers("domains", self.domains)
        if not isinstance(self.evidence_needs, tuple) or any(
            not isinstance(item, EvidenceNeed) for item in self.evidence_needs
        ):
            raise TypeError("evidence_needs must contain EvidenceNeed values")
        if not isinstance(self.schedule, CognitiveSchedule):
            raise TypeError("schedule must be CognitiveSchedule")
        _identifier("response_strategy", self.response_strategy)
        if type(self.action_requires_authority) is not bool:
            raise TypeError("action_requires_authority must be bool")


@dataclass(frozen=True, slots=True)
class ClaimPlan:
    claim_id: str
    subject_id: str
    predicate: str
    rendered_value: str
    epistemic_state: EpistemicState
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("claim_id", "subject_id", "predicate"):
            _identifier(name, getattr(self, name))
        _text("rendered_value", self.rendered_value)
        if not isinstance(self.epistemic_state, EpistemicState):
            raise TypeError("epistemic_state must be EpistemicState")
        _identifiers("evidence_refs", self.evidence_refs)
        if (
            self.epistemic_state
            in {EpistemicState.OBSERVED, EpistemicState.KNOWN}
            and not self.evidence_refs
        ):
            raise ValueError("observed/known claims require evidence references")


@dataclass(frozen=True, slots=True)
class AnswerPlan:
    turn_id: str
    claims: tuple[ClaimPlan, ...]
    unknown_need_ids: tuple[str, ...] = ()
    execution_receipt_refs: tuple[str, ...] = ()
    personality_context_id: str | None = None

    def __post_init__(self) -> None:
        _identifier("turn_id", self.turn_id)
        if not isinstance(self.claims, tuple) or any(
            not isinstance(claim, ClaimPlan) for claim in self.claims
        ):
            raise TypeError("claims must contain ClaimPlan values")
        _identifiers("unknown_need_ids", self.unknown_need_ids)
        _identifiers("execution_receipt_refs", self.execution_receipt_refs)
        if self.personality_context_id is not None:
            _identifier("personality_context_id", self.personality_context_id)


class ConversationFocusStore(Protocol):
    """Audience-scoped focus persistence owned by the Turn Kernel."""

    def load(
        self,
        *,
        session_id: str,
        audience_id: str | None,
    ) -> ConversationFocus: ...

    def commit(
        self,
        focus: ConversationFocus,
        *,
        expected_revision: int,
    ) -> ConversationFocus: ...


class TurnKernel(Protocol):
    """Sole coordinator contract; it does not imply an implementation yet."""

    def plan(
        self,
        turn: TurnKernelInput,
        focus: ConversationFocus,
    ) -> TurnPlan: ...


class CognitiveScheduler(Protocol):
    def schedule(self, plan: TurnPlan) -> CognitiveSchedule: ...


class EvidenceAcquirer(Protocol):
    """Acquire through existing capability/authority owners."""

    def acquire(
        self,
        needs: tuple[EvidenceNeed, ...],
    ) -> tuple[EvidenceAtom, ...]: ...


class ClaimPlanner(Protocol):
    def build(
        self,
        plan: TurnPlan,
        evidence: tuple[EvidenceAtom, ...],
    ) -> AnswerPlan: ...


class ClaimValidator(Protocol):
    def validate(
        self,
        answer: AnswerPlan,
        evidence: tuple[EvidenceAtom, ...],
    ) -> AnswerPlan: ...


class PersonalityRenderer(Protocol):
    def render(self, answer: AnswerPlan, *, expression_context: object) -> str: ...
