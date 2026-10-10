"""Typed contracts for Sofía's optional, evidence-grounded digital life."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Mapping


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


def identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def text(value: str, label: str, maximum: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value.strip()


def aware(value: datetime, label: str = "timestamp") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def refs(values: tuple[str, ...], label: str, maximum: int = 32) -> tuple[str, ...]:
    if (
        not isinstance(values, tuple) or not values or len(values) > maximum
        or len(set(values)) != len(values)
        or any(not isinstance(value, str) or not value.strip() or len(value) > 300 for value in values)
    ):
        raise ValueError(f"{label} must contain distinct bounded references")
    return values


class ProjectScope(str, Enum):
    PERSONAL_PRIVATE = "personal_private"
    COLLABORATIVE = "collaborative"
    USER_ASSIGNMENT = "user_assignment"
    OPERATIONAL_DUTY = "operational_duty"


class ProjectStatus(str, Enum):
    IDEA = "idea"
    PROPOSED = "proposed"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"
    ABANDONED = "abandoned"
    ARCHIVED = "archived"
    FAILED = "failed"
    SUPERSEDED = "superseded"


TERMINAL_PROJECT_STATUSES = frozenset({
    ProjectStatus.ARCHIVED,
    ProjectStatus.SUPERSEDED,
})


PROJECT_TRANSITIONS = {
    ProjectStatus.IDEA: frozenset({
        ProjectStatus.PROPOSED, ProjectStatus.REJECTED,
        ProjectStatus.ABANDONED, ProjectStatus.ARCHIVED,
    }),
    ProjectStatus.PROPOSED: frozenset({
        ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.REJECTED,
        ProjectStatus.ABANDONED, ProjectStatus.ARCHIVED,
    }),
    ProjectStatus.ACTIVE: frozenset({
        ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.FAILED,
        ProjectStatus.ABANDONED, ProjectStatus.ARCHIVED,
        ProjectStatus.SUPERSEDED,
    }),
    ProjectStatus.PAUSED: frozenset({
        ProjectStatus.ACTIVE, ProjectStatus.ABANDONED,
        ProjectStatus.ARCHIVED, ProjectStatus.SUPERSEDED,
    }),
    ProjectStatus.COMPLETED: frozenset({
        ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED,
        ProjectStatus.SUPERSEDED,
    }),
    ProjectStatus.REJECTED: frozenset({
        ProjectStatus.PROPOSED, ProjectStatus.ARCHIVED,
    }),
    ProjectStatus.ABANDONED: frozenset({
        ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED,
    }),
    ProjectStatus.FAILED: frozenset({
        ProjectStatus.ACTIVE, ProjectStatus.ABANDONED,
        ProjectStatus.ARCHIVED, ProjectStatus.SUPERSEDED,
    }),
}


class SelectionKind(str, Enum):
    PROJECT = "project"
    INACTIVITY = "inactivity"
    DEFERRED = "deferred"


class TechnicalOutcome(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    INCONCLUSIVE = "inconclusive"


class PersonalJudgment(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    MIXED = "mixed"
    INDIFFERENT = "indifferent"
    UNKNOWN = "unknown"


class InterestStatus(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"


class MilestoneStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    cpu_percent: int = 20
    gpu_percent: int = 20
    memory_mb: int = 1024
    storage_bytes: int = 512 * 1024**2
    daily_seconds: int = 1800
    concurrent_jobs: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.cpu_percent <= 100 or not 0 <= self.gpu_percent <= 100:
            raise ValueError("CPU/GPU budgets must be bounded percentages")
        if not 64 <= self.memory_mb <= 1_048_576:
            raise ValueError("memory budget must be in 64..1048576 MB")
        if not 1024 <= self.storage_bytes <= 1024**4:
            raise ValueError("storage budget must be bounded")
        if not 60 <= self.daily_seconds <= 86_400:
            raise ValueError("daily time budget must be in 60..86400 seconds")
        if not 1 <= self.concurrent_jobs <= 8:
            raise ValueError("concurrent job budget must be in 1..8")


@dataclass(frozen=True, slots=True)
class ProjectIdea:
    idea_id: str
    name: str
    description: str
    originating_interest: str
    objectives: tuple[str, ...]
    optional_success_criteria: tuple[str, ...]
    requested_artifact_kind: str
    evidence_refs: tuple[str, ...]
    confidence: float
    curiosity: float
    created_at: datetime

    def __post_init__(self) -> None:
        identifier(self.idea_id, "idea_id")
        text(self.name, "project name", 180)
        text(self.description, "project description", 2000)
        identifier(self.originating_interest, "originating_interest")
        if not 1 <= len(self.objectives) <= 16 or any(not item.strip() or len(item) > 500 for item in self.objectives):
            raise ValueError("project idea requires 1..16 bounded objectives")
        if len(self.optional_success_criteria) > 16 or any(
            not item.strip() or len(item) > 500 for item in self.optional_success_criteria
        ):
            raise ValueError("success criteria must be bounded")
        identifier(self.requested_artifact_kind, "requested_artifact_kind")
        refs(self.evidence_refs, "idea evidence_refs")
        for name in ("confidence", "curiosity"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in 0..1")
        aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ProjectBrief:
    objectives: tuple[str, ...]
    optional_success_criteria: tuple[str, ...]
    required_tools: tuple[str, ...]
    permission_requirements: tuple[str, ...]
    resource_budget: ResourceBudget
    associated_space_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.objectives or len(self.objectives) > 16:
            raise ValueError("project brief requires bounded objectives")
        if len(self.optional_success_criteria) > 16:
            raise ValueError("project criteria must be bounded")
        for values, label in (
            (self.required_tools, "required_tools"),
            (self.permission_requirements, "permission_requirements"),
            (self.associated_space_ids, "associated_space_ids"),
        ):
            if len(values) > 32 or len(set(values)) != len(values):
                raise ValueError(f"{label} must be distinct and bounded")
            for value in values:
                identifier(value, label)
        if not isinstance(self.resource_budget, ResourceBudget):
            raise TypeError("ResourceBudget required")


@dataclass(frozen=True, slots=True)
class LifeProject:
    project_id: str
    name: str
    description: str
    creator_principal_id: str
    owner_principal_id: str
    audience_id: str
    scope: ProjectScope
    originating_interest: str
    status: ProjectStatus
    brief: ProjectBrief
    goal_id: str | None
    priority: float
    confidence: float
    created_at: datetime
    updated_at: datetime
    revision: int = 1
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.project_id, "project_id"),
            (self.creator_principal_id, "creator_principal_id"),
            (self.owner_principal_id, "owner_principal_id"),
            (self.originating_interest, "originating_interest"),
        ):
            identifier(value, label)
        text(self.name, "project name", 180)
        text(self.description, "project description", 2000)
        text(self.audience_id, "audience_id", 160)
        if not isinstance(self.scope, ProjectScope) or not isinstance(self.status, ProjectStatus):
            raise TypeError("project scope/status are invalid")
        if not isinstance(self.brief, ProjectBrief):
            raise TypeError("ProjectBrief required")
        if self.goal_id is not None:
            identifier(self.goal_id, "goal_id")
        for name in ("priority", "confidence"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in 0..1")
        aware(self.created_at, "created_at"); aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at or self.revision < 1:
            raise ValueError("invalid project revision/timestamps")
        if self.status is ProjectStatus.SUPERSEDED:
            identifier(self.superseded_by or "", "superseded_by")
        elif self.superseded_by is not None:
            raise ValueError("only superseded projects name a replacement")


@dataclass(frozen=True, slots=True)
class ProjectEvent:
    event_id: str
    project_id: str
    from_status: ProjectStatus | None
    to_status: ProjectStatus
    decision: str
    reason: str
    evidence_refs: tuple[str, ...]
    actor_principal_id: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        identifier(self.event_id, "event_id"); identifier(self.project_id, "project_id")
        identifier(self.actor_principal_id, "actor_principal_id")
        text(self.decision, "decision", 120); text(self.reason, "reason", 1000)
        refs(self.evidence_refs, "project event evidence_refs")
        aware(self.occurred_at, "occurred_at")


@dataclass(frozen=True, slots=True)
class ArtifactEvaluation:
    evaluation_id: str
    project_id: str
    artifact_id: str
    artifact_revision: int
    technical_outcome: TechnicalOutcome
    personal_judgment: PersonalJudgment
    objective_results: Mapping[str, bool | None]
    reason: str
    evidence_refs: tuple[str, ...]
    preserve_for_research: bool
    evaluated_at: datetime

    def __post_init__(self) -> None:
        identifier(self.evaluation_id, "evaluation_id"); identifier(self.project_id, "project_id")
        identifier(self.artifact_id, "artifact_id")
        if self.artifact_revision < 1:
            raise ValueError("artifact_revision must be positive")
        if not isinstance(self.technical_outcome, TechnicalOutcome) or not isinstance(self.personal_judgment, PersonalJudgment):
            raise TypeError("evaluation outcome/judgment invalid")
        if len(self.objective_results) > 32 or any(
            not isinstance(key, str) or not key.strip() or value not in {True, False, None}
            for key, value in self.objective_results.items()
        ):
            raise ValueError("objective results must be bounded tri-state values")
        text(self.reason, "evaluation reason", 1500)
        refs(self.evidence_refs, "evaluation evidence_refs")
        aware(self.evaluated_at, "evaluated_at")


@dataclass(frozen=True, slots=True)
class LifeSelection:
    selection_id: str
    kind: SelectionKind
    project_id: str | None
    reason: str
    resource_pressure: float
    busy: bool
    selected_at: datetime

    def __post_init__(self) -> None:
        identifier(self.selection_id, "selection_id")
        if self.project_id is not None:
            identifier(self.project_id, "project_id")
        if self.kind is SelectionKind.PROJECT and self.project_id is None:
            raise ValueError("project selection requires project_id")
        if self.kind is not SelectionKind.PROJECT and self.project_id is not None:
            raise ValueError("non-project selection cannot name a project")
        text(self.reason, "selection reason", 500)
        if not 0 <= self.resource_pressure <= 1 or not isinstance(self.busy, bool):
            raise ValueError("invalid selection context")
        aware(self.selected_at, "selected_at")


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    experience_id: str
    project_id: str | None
    kind: str
    summary: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    private: bool
    occurred_at: datetime
    recorded_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.experience_id, "experience_id")
        if self.project_id is not None:
            identifier(self.project_id, "project_id")
        identifier(self.kind, "experience kind")
        text(self.summary, "experience summary", 1200)
        refs(self.evidence_refs, "experience evidence_refs")
        text(self.audience_id, "audience_id", 160)
        aware(self.occurred_at, "occurred_at"); aware(self.recorded_at, "recorded_at")
        if self.occurred_at > self.recorded_at:
            raise ValueError("experience cannot be recorded before it occurred")


@dataclass(frozen=True, slots=True)
class InterestRecord:
    interest_id: str
    name: str
    context: str
    strength: float
    confidence: float
    status: InterestStatus
    reason: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        identifier(self.interest_id, "interest_id")
        text(self.name, "interest name", 180); identifier(self.context, "interest context")
        if not 0 <= self.strength <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("interest strength/confidence must be in 0..1")
        if not isinstance(self.status, InterestStatus):
            raise TypeError("InterestStatus required")
        text(self.reason, "interest reason", 1000)
        refs(self.evidence_refs, "interest evidence_refs")
        text(self.audience_id, "audience_id", 160)
        if self.revision < 1:
            raise ValueError("interest revision must be positive")
        aware(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class ProjectMilestone:
    milestone_id: str
    project_id: str
    title: str
    status: MilestoneStatus
    ordinal: int
    evidence_refs: tuple[str, ...]
    result: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        identifier(self.milestone_id, "milestone_id"); identifier(self.project_id, "project_id")
        text(self.title, "milestone title", 500)
        if not isinstance(self.status, MilestoneStatus) or not 0 <= self.ordinal <= 100:
            raise ValueError("invalid milestone status/ordinal")
        if self.evidence_refs:
            refs(self.evidence_refs, "milestone evidence_refs")
        if self.result is not None:
            text(self.result, "milestone result", 1200)
        aware(self.updated_at, "updated_at")
