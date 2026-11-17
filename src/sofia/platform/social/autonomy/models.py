"""Per-Core social state models; none of them is a shared relationship score."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from uuid import UUID

from sofia.core.rel.impressions import ImpressionKind


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,119}$")


def _utc(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class PeerFacet(str, Enum):
    HONESTY = "honesty"
    RELIABILITY = "reliability"
    TECHNICAL_COMPETENCE = "technical_competence"
    PRIVACY_RESPECT = "privacy_respect"
    INTELLECTUAL_RESPECT = "intellectual_respect"
    GOODWILL = "goodwill"
    AFFINITY = "affinity"
    EMOTIONAL_STANCE = "emotional_stance"
    COLLABORATION_WILLINGNESS = "collaboration_willingness"
    CONTACT_PREFERENCE = "contact_preference"


FACET_IMPRESSION: dict[PeerFacet, tuple[ImpressionKind, float]] = {
    PeerFacet.HONESTY: (ImpressionKind.TRUST, 1.0),
    PeerFacet.RELIABILITY: (ImpressionKind.TRUST, 1.0),
    PeerFacet.TECHNICAL_COMPETENCE: (ImpressionKind.RESPECT, 1.0),
    PeerFacet.PRIVACY_RESPECT: (ImpressionKind.GUARDEDNESS, -1.0),
    PeerFacet.INTELLECTUAL_RESPECT: (ImpressionKind.RESPECT, 1.0),
    PeerFacet.GOODWILL: (ImpressionKind.APPRECIATION, 1.0),
    PeerFacet.AFFINITY: (ImpressionKind.AFFECTION, 1.0),
    PeerFacet.EMOTIONAL_STANCE: (ImpressionKind.APPRECIATION, 1.0),
    PeerFacet.COLLABORATION_WILLINGNESS: (ImpressionKind.TRUST, 1.0),
    PeerFacet.CONTACT_PREFERENCE: (ImpressionKind.GUARDEDNESS, -1.0),
}


@dataclass(frozen=True, slots=True)
class FacetStance:
    impression_id: str
    facet: PeerFacet
    kind: ImpressionKind
    level: float
    polarity: float
    reason: str
    evidence_refs: tuple[str, ...]
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.facet, PeerFacet):
            raise TypeError("facet must be PeerFacet")
        if not isinstance(self.kind, ImpressionKind):
            raise TypeError("kind must be ImpressionKind")
        if not 0.0 <= self.level <= 1.0:
            raise ValueError("level must be in 0..1")
        if self.polarity not in {-1.0, 1.0}:
            raise ValueError("polarity must be -1 or 1")

    @property
    def effective(self) -> float:
        return self.level if self.polarity > 0 else 1.0 - self.level


@dataclass(frozen=True, slots=True)
class PeerRelationship:
    core_id: UUID
    peer_core_id: UUID
    stances: tuple[FacetStance, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if not isinstance(self.peer_core_id, UUID):
            raise TypeError("peer_core_id must be a UUID")

    def stance(self, facet: PeerFacet) -> FacetStance | None:
        for item in self.stances:
            if item.facet is facet:
                return item
        return None

    def effective(self, facet: PeerFacet) -> float | None:
        stance = self.stance(facet)
        return None if stance is None else stance.effective

    @property
    def is_friend(self) -> bool:
        affinity = self.effective(PeerFacet.AFFINITY)
        return affinity is not None and affinity >= 0.75

    @property
    def known(self) -> bool:
        return bool(self.stances)


@dataclass(frozen=True, slots=True)
class Interest:
    name: str
    strength: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _IDENTIFIER.fullmatch(self.name) is None:
            raise ValueError("interest name must be a bounded identifier")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("interest strength must be in 0..1")


@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    description: str
    priority: float
    active: bool

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or _IDENTIFIER.fullmatch(self.goal_id) is None:
            raise ValueError("goal_id must be a bounded identifier")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description.strip()) > 500
        ):
            raise ValueError("goal description must be bounded nonempty text")
        if not 0.0 <= self.priority <= 1.0:
            raise ValueError("goal priority must be in 0..1")
        if type(self.active) is not bool:
            raise ValueError("active must be a bool")


class BoundaryKind(str, Enum):
    NO_CONTACT = "no_contact"
    NO_PRIVATE = "no_private"
    NO_TOPIC = "no_topic"


@dataclass(frozen=True, slots=True)
class Boundary:
    peer_core_id: UUID | None
    kind: BoundaryKind
    value: str | None

    def __post_init__(self) -> None:
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if not isinstance(self.kind, BoundaryKind):
            raise TypeError("kind must be BoundaryKind")
        if self.value is not None and (
            not isinstance(self.value, str)
            or _IDENTIFIER.fullmatch(self.value) is None
        ):
            raise ValueError("boundary value must be a bounded identifier")


class TopicStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    PAUSED = "paused"


@dataclass(frozen=True, slots=True)
class UnresolvedTopic:
    topic_key: str
    peer_core_id: UUID | None
    room_id: str | None
    summary: str
    status: TopicStatus
    opened_at: datetime
    last_activity_at: datetime
    next_revisit_at: datetime
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.topic_key, str) or _IDENTIFIER.fullmatch(
            self.topic_key
        ) is None:
            raise ValueError("topic_key must be a bounded identifier")
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if self.room_id is not None and _IDENTIFIER.fullmatch(self.room_id) is None:
            raise ValueError("room_id must be a bounded identifier")
        if (
            not isinstance(self.summary, str)
            or not self.summary.strip()
            or len(self.summary.strip()) > 500
        ):
            raise ValueError("topic summary must be bounded nonempty text")
        if not isinstance(self.status, TopicStatus):
            raise TypeError("status must be TopicStatus")
        for name in ("opened_at", "last_activity_at", "next_revisit_at"):
            value = getattr(self, name)
            if _utc(value, name) != value:
                raise ValueError(f"{name} must be an exact UTC instant")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")

    @property
    def unresolved(self) -> bool:
        return self.status is TopicStatus.OPEN


@dataclass(frozen=True, slots=True)
class EmotionalAppraisal:
    appraisal_id: str
    core_id: UUID
    peer_core_id: UUID | None
    topic: str | None
    labels: tuple[str, ...]
    valence: float
    intensity: float
    evidence_ref: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.appraisal_id, str)
            or not self.appraisal_id.startswith("appraisal:")
            or len(self.appraisal_id) > 120
        ):
            raise ValueError("appraisal_id must be a canonical appraisal id")
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if self.topic is not None and _IDENTIFIER.fullmatch(self.topic) is None:
            raise ValueError("topic must be a bounded identifier")
        if (
            not isinstance(self.labels, tuple)
            or not 1 <= len(self.labels) <= 4
            or len(set(self.labels)) != len(self.labels)
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item.strip()) > 40
                for item in self.labels
            )
        ):
            raise ValueError("labels must be 1..4 distinct bounded labels")
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError("valence must be in -1..1")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("intensity must be in 0..1")
        if not isinstance(self.evidence_ref, str) or _IDENTIFIER.fullmatch(
            self.evidence_ref
        ) is None:
            raise ValueError("evidence_ref must be a bounded identifier")
        if _utc(self.recorded_at, "recorded_at") != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")

@dataclass(frozen=True, slots=True)
class Opinion:
    opinion_id: str
    core_id: UUID
    peer_core_id: UUID | None
    topic: str
    statement: str
    stance: float
    confidence: float
    evidence_refs: tuple[str, ...]
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.opinion_id, str)
            or not self.opinion_id.startswith("opinion:")
            or len(self.opinion_id) > 120
        ):
            raise ValueError("opinion_id must be a canonical opinion id")
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if not isinstance(self.topic, str) or _IDENTIFIER.fullmatch(self.topic) is None:
            raise ValueError("topic must be a bounded identifier")
        if (
            not isinstance(self.statement, str)
            or not self.statement.strip()
            or len(self.statement.strip()) > 1000
        ):
            raise ValueError("opinion statement must be bounded nonempty text")
        if not -1.0 <= self.stance <= 1.0:
            raise ValueError("stance must be in -1..1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in 0..1")
        if (
            not isinstance(self.evidence_refs, tuple)
            or not 1 <= len(self.evidence_refs) <= 8
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
            or any(
                not isinstance(item, str)
                or _IDENTIFIER.fullmatch(item) is None
                for item in self.evidence_refs
            )
        ):
            raise ValueError("evidence_refs must be 1..8 distinct references")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        if _utc(self.recorded_at, "recorded_at") != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")
