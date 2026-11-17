"""Shared versioned contracts for independent persistent Aegis Cores.

These values describe identity, personal metadata, memory, preference and
relationship state.  Constructing or decoding one grants no execution
authority, no protected-memory access and no lifecycle permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Mapping
from uuid import UUID

MULTICORE_SCHEMA = "aegis.core.multicore.v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class MemoryType(str, Enum):
    IDENTITY = "identity"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"
    AFFECTIVE = "affective"
    REFLECTION = "reflection"
    WORKING = "working"


class StorageTier(str, Enum):
    T0_WORKING = "t0_working"
    T1_ACTIVE = "t1_active"
    T2_ARCHIVE = "t2_archive"


class SecurityClass(str, Enum):
    PRIVATE = "private"
    PROTECTED = "protected"
    SHAREABLE = "shareable"
    AUTHORIZED_SHARED_COPY = "authorized_shared_copy"


class EvidenceState(str, Enum):
    VERIFIED = "verified"
    REPORTED = "reported"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"


class PreferenceState(str, Enum):
    UNEXPLORED = "unexplored"
    TENTATIVE = "tentative"
    DEVELOPING = "developing"
    ESTABLISHED = "established"
    DORMANT = "dormant"
    REVISED = "revised"


class ChannelKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    CORE_TO_CORE = "core_to_core"
    GROUP = "group"


class LifecycleState(str, Enum):
    DEFINED = "defined"
    REGISTERED = "registered"
    ACTIVE = "active"
    STOPPED = "stopped"
    DETACHED = "detached"
    REMOVED = "removed"


def _text(value: object, label: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    if any(ord(character) < 0x20 for character in value):
        raise ValueError(f"{label} cannot contain control characters")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _ratio(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


@dataclass(frozen=True, slots=True)
class AvatarMetadata:
    age_years: int
    height_inches: float
    weight_pounds: float
    build: str
    head_proportions: float
    measurements: Mapping[str, float]
    hair: str
    outfit: str
    default_expression: str
    colors: Mapping[str, str]
    materials: Mapping[str, str]
    pbr: Mapping[str, float]
    accessory: str | None = None

    def __post_init__(self) -> None:
        if type(self.age_years) is not int or self.age_years < 1:
            raise ValueError("age_years must be a positive integer")
        for label, value in (
            ("height_inches", self.height_inches),
            ("weight_pounds", self.weight_pounds),
            ("head_proportions", self.head_proportions),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{label} must be positive")
        for label, value in (
            ("build", self.build), ("hair", self.hair), ("outfit", self.outfit),
            ("default_expression", self.default_expression),
        ):
            _text(value, label)
        for name, value in self.measurements.items():
            _identifier(name, "measurement")
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError("measurements must be positive")
        for name, value in self.colors.items():
            _identifier(name, "color name")
            if not isinstance(value, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
                raise ValueError("colors must be six-digit hex strings")
        for name, value in self.materials.items():
            _identifier(name, "material name")
            _text(value, "material")
        for name, value in self.pbr.items():
            _identifier(name, "pbr name")
            _ratio(value, "pbr value")
        if self.accessory is not None:
            _text(self.accessory, "accessory")


@dataclass(frozen=True, slots=True)
class VoiceMetadata:
    target: str
    register: str
    accent: str | None
    cadence: str
    serious_delivery: str
    model_id: str | None = None
    assets_created: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("target", self.target), ("register", self.register),
            ("cadence", self.cadence), ("serious_delivery", self.serious_delivery),
        ):
            _text(value, label)
        if self.accent is not None:
            _text(self.accent, "accent")
        if self.model_id is not None:
            _identifier(self.model_id, "voice model_id")
        if self.assets_created is not False:
            raise ValueError("voice assets are deferred and must not be claimed present")


@dataclass(frozen=True, slots=True)
class CoreDescriptor:
    core_number: int
    full_name: str
    nickname: str | None
    gender: str
    presentation_species: str
    apparent_age: int
    identity_concept: str
    personality_traits: tuple[str, ...]
    motivations: tuple[str, ...]
    character_flaw: str
    constitutional_priorities: tuple[str, ...]
    avatar: AvatarMetadata
    voice: VoiceMetadata
    core_id: UUID | None = None

    def __post_init__(self) -> None:
        if type(self.core_number) is not int or self.core_number < 2:
            raise ValueError("core_number must be an integer >= 2")
        _text(self.full_name, "full_name")
        if self.nickname is not None:
            _text(self.nickname, "nickname")
        _text(self.gender, "gender")
        _text(self.presentation_species, "presentation_species")
        if type(self.apparent_age) is not int or self.apparent_age < 1:
            raise ValueError("apparent_age must be positive")
        _text(self.identity_concept, "identity_concept")
        for label, values in (
            ("personality_traits", self.personality_traits),
            ("motivations", self.motivations),
            ("constitutional_priorities", self.constitutional_priorities),
        ):
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{label} must be a nonempty tuple")
            for value in values:
                _text(value, label)
        _text(self.character_flaw, "character_flaw")
        if self.core_id is not None:
            _uuid(self.core_id, "core_id")

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.full_name.casefold()).strip("-")


@dataclass(frozen=True, slots=True)
class PersistentCoreIdentity:
    core_id: UUID
    core_number: int
    full_name: str
    slug: str
    generation: int
    constitution_sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if type(self.core_number) is not int or self.core_number < 1:
            raise ValueError("core_number must be a positive integer")
        _text(self.full_name, "full_name")
        _identifier(self.slug, "slug")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        if not isinstance(self.constitution_sha256, str) or _HEX64.fullmatch(self.constitution_sha256) is None:
            raise ValueError("constitution_sha256 must be lowercase SHA-256")
        _utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: UUID
    owner_core_id: UUID
    memory_type: MemoryType
    tier: StorageTier
    security: SecurityClass
    evidence: EvidenceState
    source: str
    content: str
    created_at: datetime
    updated_at: datetime
    confidence: float
    significance: int
    version: int = 1
    correction_of: UUID | None = None
    retention_seconds: int | None = None

    def __post_init__(self) -> None:
        _uuid(self.memory_id, "memory_id")
        _uuid(self.owner_core_id, "owner_core_id")
        if not isinstance(self.memory_type, MemoryType):
            raise TypeError("memory_type must be MemoryType")
        if not isinstance(self.tier, StorageTier):
            raise TypeError("tier must be StorageTier")
        if not isinstance(self.security, SecurityClass):
            raise TypeError("security must be SecurityClass")
        if not isinstance(self.evidence, EvidenceState):
            raise TypeError("evidence must be EvidenceState")
        _text(self.source, "source", maximum=512)
        _text(self.content, "content", maximum=1_000_000)
        _utc(self.created_at, "created_at")
        _utc(self.updated_at, "updated_at")
        _ratio(self.confidence, "confidence")
        if type(self.significance) is not int or not 0 <= self.significance <= 10:
            raise ValueError("significance must be in [0, 10]")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version must be positive")
        if self.correction_of is not None:
            _uuid(self.correction_of, "correction_of")
        if self.retention_seconds is not None and (
            type(self.retention_seconds) is not int or self.retention_seconds < 1
        ):
            raise ValueError("retention_seconds must be positive")


@dataclass(frozen=True, slots=True)
class PreferenceRecord:
    preference_id: UUID
    owner_core_id: UUID
    subject: str
    state: PreferenceState
    confidence: float
    evidence: tuple[UUID, ...]
    updated_at: datetime
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.preference_id, "preference_id")
        _uuid(self.owner_core_id, "owner_core_id")
        _text(self.subject, "subject")
        if not isinstance(self.state, PreferenceState):
            raise TypeError("state must be PreferenceState")
        _ratio(self.confidence, "confidence")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        for item in self.evidence:
            _uuid(item, "evidence")
        _utc(self.updated_at, "updated_at")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")


@dataclass(frozen=True, slots=True)
class RelationshipDimensions:
    familiarity: float = 0.0
    reliability: float = 0.0
    technical_trust: float = 0.0
    boundary_respect: float = 0.0
    conversational_comfort: float = 0.0
    respect: float = 0.0
    shared_experiences: int = 0
    unresolved_disagreements: int = 0

    def __post_init__(self) -> None:
        for label in (
            "familiarity", "reliability", "technical_trust", "boundary_respect",
            "conversational_comfort", "respect",
        ):
            _ratio(getattr(self, label), label)
        for label in ("shared_experiences", "unresolved_disagreements"):
            value = getattr(self, label)
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    owner_core_id: UUID
    peer_id: UUID
    dimensions: RelationshipDimensions
    evidence: tuple[UUID, ...] = field(default_factory=tuple)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.owner_core_id, "owner_core_id")
        _uuid(self.peer_id, "peer_id")
        if self.owner_core_id == self.peer_id:
            raise ValueError("a Core cannot hold a peer relationship with itself")
        if not isinstance(self.dimensions, RelationshipDimensions):
            raise TypeError("dimensions must be RelationshipDimensions")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        for item in self.evidence:
            _uuid(item, "relationship evidence")
        _utc(self.updated_at, "updated_at")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
