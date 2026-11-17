"""Evidence-based, asymmetric relationships for independent Aegis Cores.

Each Core keeps its own view of each peer.  Two Cores may hold completely
different assessments of one another; nothing here synchronizes or averages
them.  Relationships start empty and carry no preset friendship, rivalry,
romance or family label.  A relationship never grants memory access, Fleet
access, execution permission or any other authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sofia.core.multicore.contracts import (
    EvidenceState,
    RelationshipDimensions,
    RelationshipRecord,
    SecurityClass,
)


class RelationshipError(RuntimeError):
    """Base failure for invalid or disallowed relationship state."""


class RelationshipEvidenceError(RelationshipError):
    """A relationship change lacks usable evidence."""


class RelationshipIsolationError(PermissionError):
    """A Core tried to read another Core's private reflections."""


class RelationshipChangeKind(str, Enum):
    DEVELOP = "develop"
    IMPROVE = "improve"
    DETERIORATE = "deteriorate"
    PAUSE = "pause"
    RECOVER = "recover"


class RelationshipStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


def _utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _delta(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not -1.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [-1, 1]")
    return number


def _text(value: object, label: str, *, maximum: int = 600) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise ValueError(f"{label} must be bounded single-line text")
    return value.strip()


def _ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _shift(value: float, delta: float) -> float:
    return round(min(1.0, max(0.0, value + delta)), 6)


@dataclass(frozen=True, slots=True)
class RelationshipAuthorityBoundary:
    """Explicit statement that relationships grant no operational rights."""

    authority: bool = False
    memory_access: bool = False
    fleet_access: bool = False
    execution_access: bool = False
    protected_state_access: bool = False
    identity_access: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("authority", self.authority),
            ("memory_access", self.memory_access),
            ("fleet_access", self.fleet_access),
            ("execution_access", self.execution_access),
            ("protected_state_access", self.protected_state_access),
            ("identity_access", self.identity_access),
        ):
            if type(value) is not bool:
                raise TypeError(f"{name} must be a bool")
            if value:
                raise ValueError("relationships cannot grant operational authority")


NO_RELATIONSHIP_AUTHORITY = RelationshipAuthorityBoundary()


@dataclass(frozen=True, slots=True)
class RelationshipReflection:
    """A private, evidence-linked thought about one peer.

    Reflections are owned by one Core only.  They never enter the peer's
    relationship record, shared context, memory or Fleet state.
    """

    reflection_id: UUID
    owner_core_id: UUID
    peer_id: UUID
    content: str
    evidence: tuple[UUID, ...]
    evidence_state: EvidenceState = EvidenceState.REPORTED
    recorded_at: datetime = field(default_factory=_now)
    security: SecurityClass = SecurityClass.PRIVATE

    def __post_init__(self) -> None:
        _uuid(self.reflection_id, "reflection_id")
        _uuid(self.owner_core_id, "owner_core_id")
        _uuid(self.peer_id, "peer_id")
        if self.owner_core_id == self.peer_id:
            raise ValueError("a reflection must concern a distinct peer")
        _text(self.content, "reflection content")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise RelationshipEvidenceError("reflections require evidence")
        for item in self.evidence:
            _uuid(item, "reflection evidence")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("reflection evidence identifiers must be distinct")
        if not isinstance(self.evidence_state, EvidenceState):
            raise TypeError("evidence_state must be EvidenceState")
        if self.evidence_state is EvidenceState.SPECULATIVE:
            raise RelationshipEvidenceError(
                "speculative evidence cannot anchor a private reflection"
            )
        object.__setattr__(
            self,
            "recorded_at",
            _utc(self.recorded_at, "recorded_at"),
        )
        if self.security is not SecurityClass.PRIVATE:
            raise ValueError("relationship reflections must remain private")


@dataclass(frozen=True, slots=True)
class RelationshipChange:
    """One evidence-bearing movement in a Core's view of one peer."""

    kind: RelationshipChangeKind
    reason: str
    evidence: tuple[UUID, ...]
    evidence_state: EvidenceState = EvidenceState.REPORTED
    familiarity_delta: float = 0.0
    reliability_delta: float = 0.0
    technical_trust_delta: float = 0.0
    boundary_respect_delta: float = 0.0
    conversational_comfort_delta: float = 0.0
    respect_delta: float = 0.0
    shared_experience: bool = False
    disagreement: bool = False
    disagreement_resolved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RelationshipChangeKind):
            raise TypeError("kind must be RelationshipChangeKind")
        _text(self.reason, "reason")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise RelationshipEvidenceError(
                "relationship changes require evidence"
            )
        for item in self.evidence:
            _uuid(item, "relationship evidence")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("relationship evidence identifiers must be distinct")
        if not isinstance(self.evidence_state, EvidenceState):
            raise TypeError("evidence_state must be EvidenceState")
        if self.evidence_state is EvidenceState.SPECULATIVE:
            raise RelationshipEvidenceError(
                "speculative evidence cannot change a relationship"
            )
        for label, value in (
            ("familiarity_delta", self.familiarity_delta),
            ("reliability_delta", self.reliability_delta),
            ("technical_trust_delta", self.technical_trust_delta),
            ("boundary_respect_delta", self.boundary_respect_delta),
            ("conversational_comfort_delta", self.conversational_comfort_delta),
            ("respect_delta", self.respect_delta),
        ):
            _delta(value, label)
        for label, value in (
            ("shared_experience", self.shared_experience),
            ("disagreement", self.disagreement),
            ("disagreement_resolved", self.disagreement_resolved),
        ):
            if type(value) is not bool:
                raise TypeError(f"{label} must be a bool")
        if self.disagreement and self.disagreement_resolved:
            raise ValueError(
                "one change cannot create and resolve the same disagreement"
            )

    @property
    def has_positive_movement(self) -> bool:
        return any(value > 0.0 for value in (
            self.familiarity_delta,
            self.reliability_delta,
            self.technical_trust_delta,
            self.boundary_respect_delta,
            self.conversational_comfort_delta,
            self.respect_delta,
        )) or self.shared_experience

    @property
    def has_negative_movement(self) -> bool:
        return any(value < 0.0 for value in (
            self.familiarity_delta,
            self.reliability_delta,
            self.technical_trust_delta,
            self.boundary_respect_delta,
            self.conversational_comfort_delta,
            self.respect_delta,
        )) or self.disagreement

    @property
    def has_dimensional_movement(self) -> bool:
        return any(value != 0.0 for value in (
            self.familiarity_delta,
            self.reliability_delta,
            self.technical_trust_delta,
            self.boundary_respect_delta,
            self.conversational_comfort_delta,
            self.respect_delta,
        )) or self.shared_experience or self.disagreement or self.disagreement_resolved


@dataclass(frozen=True, slots=True)
class RelationshipRevision:
    """One append-only revision of a Core's relationship with one peer."""

    owner_core_id: UUID
    peer_id: UUID
    revision: int
    kind: RelationshipChangeKind
    status: RelationshipStatus
    dimensions: RelationshipDimensions
    evidence: tuple[UUID, ...]
    evidence_state: EvidenceState
    reason: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.owner_core_id, "owner_core_id")
        _uuid(self.peer_id, "peer_id")
        if self.owner_core_id == self.peer_id:
            raise ValueError("a Core cannot hold a peer relationship with itself")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.kind, RelationshipChangeKind):
            raise TypeError("kind must be RelationshipChangeKind")
        if not isinstance(self.status, RelationshipStatus):
            raise TypeError("status must be RelationshipStatus")
        if not isinstance(self.dimensions, RelationshipDimensions):
            raise TypeError("dimensions must be RelationshipDimensions")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise RelationshipEvidenceError("revisions require evidence")
        for item in self.evidence:
            _uuid(item, "revision evidence")
        if not isinstance(self.evidence_state, EvidenceState):
            raise TypeError("evidence_state must be EvidenceState")
        _text(self.reason, "reason")
        object.__setattr__(
            self,
            "recorded_at",
            _utc(self.recorded_at, "recorded_at"),
        )

    def as_record(self) -> RelationshipRecord:
        """Project the canonical contract record for this revision."""
        return RelationshipRecord(
            owner_core_id=self.owner_core_id,
            peer_id=self.peer_id,
            dimensions=self.dimensions,
            evidence=self.evidence,
            updated_at=self.recorded_at,
            revision=self.revision,
        )


class RelationshipLedger:
    """Per-Core append-only relationship history and private reflections.

    A ledger is bound to exactly one owner Core.  Constructing it does not
    create relationships, trust or authority.  The owner must record evidence
    through :meth:`apply` before a peer relationship exists.
    """

    def __init__(self, owner_core_id: UUID) -> None:
        self._owner_core_id = _uuid(owner_core_id, "owner_core_id")
        self._history: dict[UUID, list[RelationshipRevision]] = {}
        self._reflections: dict[UUID, list[RelationshipReflection]] = {}

    @property
    def owner_core_id(self) -> UUID:
        return self._owner_core_id

    @property
    def authority_boundary(self) -> RelationshipAuthorityBoundary:
        return NO_RELATIONSHIP_AUTHORITY

    def _require_owner(self, requesting_core_id: UUID) -> None:
        if requesting_core_id != self._owner_core_id:
            raise RelationshipIsolationError(
                "relationship state belongs to another Core"
            )

    def history(self, peer_id: UUID) -> tuple[RelationshipRevision, ...]:
        peer = _uuid(peer_id, "peer_id")
        return tuple(self._history.get(peer, ()))

    def status(self, peer_id: UUID) -> RelationshipStatus | None:
        history = self.history(peer_id)
        return None if not history else history[-1].status

    def current(self, peer_id: UUID) -> RelationshipRecord | None:
        history = self.history(peer_id)
        return None if not history else history[-1].as_record()

    def apply(
        self,
        peer_id: UUID,
        change: RelationshipChange,
        *,
        now: datetime,
    ) -> RelationshipRecord:
        """Apply exactly one evidence-backed change for this ledger's owner."""
        peer = _uuid(peer_id, "peer_id")
        if peer == self._owner_core_id:
            raise ValueError("a Core cannot hold a peer relationship with itself")
        if not isinstance(change, RelationshipChange):
            raise TypeError("change must be RelationshipChange")
        stamp = _utc(now, "now")
        previous = self.current(peer)
        previous_status = self.status(peer)
        if previous is not None and stamp < previous.updated_at:
            raise ValueError("relationship clock cannot move backward")

        if previous is None:
            if change.kind in {
                RelationshipChangeKind.PAUSE,
                RelationshipChangeKind.RECOVER,
            }:
                raise RelationshipError(
                    "a new relationship cannot begin paused or recovering"
                )
            dimensions = RelationshipDimensions()
            status = RelationshipStatus.ACTIVE
        else:
            dimensions = previous.dimensions
            status = previous_status or RelationshipStatus.ACTIVE

        if status is RelationshipStatus.PAUSED:
            if change.kind is not RelationshipChangeKind.RECOVER:
                raise RelationshipError(
                    "a paused relationship accepts only an evidence-backed recover"
                )
        elif change.kind is RelationshipChangeKind.RECOVER:
            raise RelationshipError("only a paused relationship can recover")

        if change.kind in {
            RelationshipChangeKind.DEVELOP,
            RelationshipChangeKind.IMPROVE,
        } and not change.has_positive_movement:
            raise RelationshipEvidenceError(
                f"{change.kind.value} requires positive movement or a shared experience"
            )
        if change.kind is RelationshipChangeKind.DETERIORATE and (
            not change.has_negative_movement
        ):
            raise RelationshipEvidenceError(
                "deteriorate requires negative movement or an unresolved disagreement"
            )
        if change.kind in {
            RelationshipChangeKind.PAUSE,
            RelationshipChangeKind.RECOVER,
        } and change.has_dimensional_movement:
            raise RelationshipEvidenceError(
                f"{change.kind.value} must not silently rewrite dimensional state"
            )

        familiarity = _shift(dimensions.familiarity, change.familiarity_delta)
        reliability = _shift(dimensions.reliability, change.reliability_delta)
        technical_trust = _shift(
            dimensions.technical_trust, change.technical_trust_delta
        )
        boundary_respect = _shift(
            dimensions.boundary_respect, change.boundary_respect_delta
        )
        conversational_comfort = _shift(
            dimensions.conversational_comfort,
            change.conversational_comfort_delta,
        )
        respect = _shift(dimensions.respect, change.respect_delta)
        shared = dimensions.shared_experiences + (
            1 if change.shared_experience else 0
        )
        unresolved = dimensions.unresolved_disagreements + (
            1 if change.disagreement else 0
        )
        if change.disagreement_resolved and unresolved > 0:
            unresolved -= 1
        next_dimensions = RelationshipDimensions(
            familiarity=familiarity,
            reliability=reliability,
            technical_trust=technical_trust,
            boundary_respect=boundary_respect,
            conversational_comfort=conversational_comfort,
            respect=respect,
            shared_experiences=shared,
            unresolved_disagreements=unresolved,
        )
        if change.kind is RelationshipChangeKind.PAUSE:
            status = RelationshipStatus.PAUSED
        elif change.kind is RelationshipChangeKind.RECOVER:
            status = RelationshipStatus.ACTIVE

        revision = RelationshipRevision(
            owner_core_id=self._owner_core_id,
            peer_id=peer,
            revision=1 if previous is None else previous.revision + 1,
            kind=change.kind,
            status=status,
            dimensions=next_dimensions,
            evidence=change.evidence,
            evidence_state=change.evidence_state,
            reason=change.reason,
            recorded_at=stamp,
        )
        self._history.setdefault(peer, []).append(revision)
        return revision.as_record()

    def reflect(
        self,
        peer_id: UUID,
        *,
        content: str,
        evidence: tuple[UUID, ...],
        now: datetime,
        evidence_state: EvidenceState = EvidenceState.REPORTED,
    ) -> RelationshipReflection:
        """Record one private reflection without changing the relationship."""
        peer = _uuid(peer_id, "peer_id")
        if peer == self._owner_core_id:
            raise ValueError("a reflection must concern a distinct peer")
        if not isinstance(evidence_state, EvidenceState):
            raise TypeError("evidence_state must be EvidenceState")
        reflection = RelationshipReflection(
            reflection_id=uuid4(),
            owner_core_id=self._owner_core_id,
            peer_id=peer,
            content=content,
            evidence=evidence,
            evidence_state=evidence_state,
            recorded_at=now,
        )
        self._reflections.setdefault(peer, []).append(reflection)
        return reflection

    def reflections(
        self,
        peer_id: UUID,
        *,
        requesting_core_id: UUID,
    ) -> tuple[RelationshipReflection, ...]:
        """Read private reflections only for the owning Core."""
        self._require_owner(_uuid(requesting_core_id, "requesting_core_id"))
        peer = _uuid(peer_id, "peer_id")
        return tuple(self._reflections.get(peer, ()))
