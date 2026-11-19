"""Blank, evidence-developed personal identity for independent Core #7.

Core #7 starts unwritten.  It has a caller-supplied persistent UUID and an
operator-facing display label, but no personal name, presentation, biography,
hobbies or relationships.  Missing values stay genuinely unselected; this
module never substitutes "Unknown" or invents a placeholder identity.

The module reuses the existing multicore MemoryRecord owner/provenance store
for durable evidence and the existing preference-learning service for
preference state.  It adds no second database and no global identity
authority.  Evidence is data: no observation, statement, model output or
social action grants execution authority, protected-state access or a
capability.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from importlib.resources import files as resource_files
import json
from pathlib import Path
import re
from typing import Iterable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sofia.core.multicore.contracts import (
    EvidenceState,
    MemoryRecord,
    MemoryType,
    PreferenceRecord,
    SecurityClass,
    StorageTier,
)
from sofia.core.multicore.identity import (
    CoreIdentityNotFound,
    DuplicateCoreIdentity,
    MulticoreIdentityStore,
)
from sofia.core.multicore.learning import (
    MulticoreLearningService,
    PreferenceCorrection,
    PreferenceObservation,
)
from sofia.core.multicore.memory import (
    MulticoreMemoryStore,
    ProvenanceEvent,
    ShareAuthorization,
)

UNWRITTEN_SCHEMA = "aegis.core.multicore.unwritten.v1"
UNWRITTEN_CONSTITUTION_SCHEMA = "aegis.core.unwritten.constitution.v1"
OBSERVATION_SCHEMA = "aegis.core.multicore.unwritten.observation.v1"
REFLECTION_SCHEMA = "aegis.core.multicore.unwritten.reflection.v1"
UNWRITTEN_CORE_NUMBER = 7
UNWRITTEN_SLUG = "unwritten"
UNWRITTEN_CONSTITUTION_FILE = "constitution.md"
OPERATOR_DISPLAY_LABEL = "Core #7"
TEXT_ONLY_INTERFACE = "text-only"
_OBSERVATION_SOURCE = "unwritten:observation:"
_REFLECTION_SOURCE = "unwritten:reflection:"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")

_EVIDENCE_WEIGHT: Mapping[EvidenceState, float] = {
    EvidenceState.VERIFIED: 1.0,
    EvidenceState.REPORTED: 0.5,
    EvidenceState.INFERRED: 0.25,
    EvidenceState.SPECULATIVE: 0.1,
}
_PROTECTED_ATTRIBUTE_NAMES = frozenset({
    "core_id", "core_number", "constitution_sha256", "security_class",
    "capability_scope", "authority_scope", "owner_principal_id",
    "writer_generation", "operator_label", "schema",
})
_NON_PROMOTABLE_KINDS = frozenset({"hypothetical", "fictional"})


class UnwrittenError(RuntimeError):
    """Base failure for the blank Core identity contract."""


class IdentityIsolationError(PermissionError):
    """A request crossed a Core identity or private-reflection boundary."""


class ProtectedIdentityError(PermissionError):
    """A protected identity, security or capability field cannot be written."""


class ProtectedIdentityCorruption(UnwrittenError):
    """Protected identity state failed verification.  Nothing is repaired."""


class FabricatedIdentityError(UnwrittenError):
    """Model-generated text was offered as confirmed personal identity."""


class UnwrittenStopped(PermissionError):
    """Operator STOP forbids a Core #7 identity/social mutation."""


class OwnerApprovalRequired(PermissionError):
    """This personal attribute requires explicit owner approval."""


class IdentityConflictError(ValueError):
    """An identity observation is inconsistent with the current state."""


class SocialPolicyError(PermissionError):
    """A social action is outside the configured participation policy."""


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value: object, label: str, *, maximum: int = 20_000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    for character in value:
        if ord(character) < 0x20 and character not in "\n\t":
            raise ValueError(f"{label} cannot contain control characters")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _optional_identifier(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, label)


def _ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _uuid_tuple(value: object, label: str) -> tuple[UUID, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{label} must be a tuple")
    for item in value:
        _uuid(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label} identifiers must be distinct")
    return value


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def unwritten_constitution_bytes() -> bytes:
    """Read the neutral Core #7 bootstrap constitution package asset."""
    resource = resource_files("sofia.core.unwritten").joinpath(
        UNWRITTEN_CONSTITUTION_FILE
    )
    try:
        return resource.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise UnwrittenError("Core #7 bootstrap constitution is unavailable") from exc


def unwritten_constitution_sha256() -> str:
    return sha256(unwritten_constitution_bytes()).hexdigest()


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class IdentityAttribute(str, Enum):
    """Every personal attribute starts unselected for Core #7."""

    PERSONAL_NAME = "personal_name"
    NICKNAME = "nickname"
    GENDER_IDENTITY = "gender_identity"
    GENDER_PRESENTATION = "gender_presentation"
    APPARENT_AGE = "apparent_age"
    VISUAL_SPECIES = "visual_species"
    AVATAR = "avatar"
    MEASUREMENTS = "measurements"
    VOICE = "voice"
    ACCENT = "accent"
    FAVORITE_COLORS = "favorite_colors"
    HOBBIES = "hobbies"
    PERSONALITY_ARCHETYPE = "personality_archetype"
    AUTOBIOGRAPHY = "autobiography"
    RELATIONSHIPS = "relationships"
    PREFERENCES = "preferences"


class IdentityAttributeState(str, Enum):
    UNSELECTED = "unselected"
    TENTATIVE = "tentative"
    SUPPORTED = "supported"
    ESTABLISHED = "established"
    REVISED = "revised"
    RETIRED = "retired"


class ProposalSource(str, Enum):
    OWNER_SUGGESTED = "owner_suggested"
    CORE_PROPOSED = "core_proposed"
    CORE_SELECTED = "core_selected"


class IdentityEvidenceKind(str, Enum):
    ONE_TIME_RESPONSE = "one_time_response"
    RECURRING_BEHAVIOR = "recurring_behavior"
    OWNER_SUGGESTION = "owner_suggestion"
    HYPOTHETICAL = "hypothetical"
    FICTIONAL = "fictional"
    DELIBERATE_SELF_SELECTION = "deliberate_self_selection"
    CORRECTION = "correction"
    RETIREMENT = "retirement"


OWNER_APPROVAL_REQUIRED = frozenset({
    IdentityAttribute.AVATAR,
    IdentityAttribute.MEASUREMENTS,
    IdentityAttribute.VOICE,
})


def _resolve_attribute(value: object) -> IdentityAttribute:
    if isinstance(value, IdentityAttribute):
        return value
    if isinstance(value, str):
        if value in _PROTECTED_ATTRIBUTE_NAMES:
            raise ProtectedIdentityError(
                "protected identity, security and capability fields are immutable"
            )
        try:
            return IdentityAttribute(value)
        except ValueError as exc:
            raise ValueError("unknown personal identity attribute") from exc
    raise TypeError("attribute must be an IdentityAttribute or attribute name")


def _stable_attribute_id(core_id: UUID, attribute: IdentityAttribute) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"aegis-unwritten-attribute:{core_id}:{attribute.value}",
    )


@dataclass(frozen=True, slots=True)
class IdentityAttributeRecord:
    """One personal attribute and its evidence-backed development state."""

    attribute_id: UUID
    attribute: IdentityAttribute
    state: IdentityAttributeState
    value: str | None
    confidence: float
    evidence: tuple[UUID, ...]
    interaction_refs: tuple[UUID, ...]
    updated_at: datetime | None
    revision: int
    proposed_by: ProposalSource | None
    owner_approved: bool
    owner_approval_id: UUID | None = None

    def __post_init__(self) -> None:
        _uuid(self.attribute_id, "attribute_id")
        if not isinstance(self.attribute, IdentityAttribute):
            raise TypeError("attribute must be IdentityAttribute")
        if not isinstance(self.state, IdentityAttributeState):
            raise TypeError("state must be IdentityAttributeState")
        if self.value is not None:
            _text(self.value, "attribute value")
        _ratio(self.confidence, "confidence")
        _uuid_tuple(self.evidence, "evidence")
        _uuid_tuple(self.interaction_refs, "interaction_refs")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        if self.proposed_by is not None and not isinstance(
            self.proposed_by, ProposalSource
        ):
            raise TypeError("proposed_by must be ProposalSource or None")
        if type(self.owner_approved) is not bool:
            raise TypeError("owner_approved must be a bool")
        if self.owner_approval_id is not None:
            _uuid(self.owner_approval_id, "owner_approval_id")
        if self.updated_at is not None:
            object.__setattr__(
                self, "updated_at", _utc(self.updated_at, "updated_at")
            )
        if self.state in (
            IdentityAttributeState.UNSELECTED,
            IdentityAttributeState.RETIRED,
        ) and self.value is not None:
            raise ValueError("unselected or retired attributes carry no value")
        if self.state is IdentityAttributeState.UNSELECTED:
            if self.revision != 0:
                raise ValueError("an unselected attribute has no revisions")
            if self.confidence != 0.0 or self.owner_approved:
                raise ValueError("an unselected attribute has no confidence or approval")
        if self.state is not IdentityAttributeState.UNSELECTED and self.revision < 1:
            raise ValueError("a selected attribute requires a positive revision")

    @property
    def selected(self) -> bool:
        return self.state not in (
            IdentityAttributeState.UNSELECTED,
            IdentityAttributeState.RETIRED,
        )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def _blank_attribute(
    core_id: UUID, attribute: IdentityAttribute
) -> IdentityAttributeRecord:
    return IdentityAttributeRecord(
        attribute_id=_stable_attribute_id(core_id, attribute),
        attribute=attribute,
        state=IdentityAttributeState.UNSELECTED,
        value=None,
        confidence=0.0,
        evidence=(),
        interaction_refs=(),
        updated_at=None,
        revision=0,
        proposed_by=None,
        owner_approved=False,
        owner_approval_id=None,
    )


def _blank_attributes(core_id: UUID) -> tuple[IdentityAttributeRecord, ...]:
    return tuple(_blank_attribute(core_id, attribute) for attribute in IdentityAttribute)


@dataclass(frozen=True, slots=True)
class UnwrittenCoreProfile:
    """Minimal blank package descriptor for Core #7.

    operator_label is an operator display convenience only.  It is not a
    self-selected personal name and can never be promoted to identity.
    """

    core_id: UUID
    core_number: int = UNWRITTEN_CORE_NUMBER
    operator_label: str = OPERATOR_DISPLAY_LABEL
    schema: str = UNWRITTEN_SCHEMA
    text_only: bool = True
    avatar_required: bool = False
    voice_required: bool = False
    completion_deadline: datetime | None = None
    progress_pressure: bool = False
    constitution_sha256: str | None = None
    attributes: tuple[IdentityAttributeRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if type(self.core_number) is not int or self.core_number != UNWRITTEN_CORE_NUMBER:
            raise ValueError("Core #7 profile number must be exactly 7")
        if self.operator_label != OPERATOR_DISPLAY_LABEL:
            raise ValueError("operator display label is fixed and not identity")
        if self.schema != UNWRITTEN_SCHEMA:
            raise ValueError("unsupported unwritten Core schema")
        if self.text_only is not True:
            raise ValueError("Core #7 starts as a text-only interface")
        if self.avatar_required is not False or self.voice_required is not False:
            raise ValueError("avatar and voice are never required")
        if self.completion_deadline is not None:
            raise ValueError("blank identity has no completion deadline")
        if self.progress_pressure is not False:
            raise ValueError("blank identity development carries no pressure")
        if self.constitution_sha256 is not None and (
            not isinstance(self.constitution_sha256, str)
            or _HEX64.fullmatch(self.constitution_sha256) is None
        ):
            raise ValueError("constitution_sha256 must be lowercase SHA-256 or None")
        if not isinstance(self.attributes, tuple):
            raise TypeError("attributes must be a tuple")
        if not self.attributes:
            object.__setattr__(self, "attributes", _blank_attributes(self.core_id))
            return
        if {record.attribute for record in self.attributes} != set(IdentityAttribute):
            raise ValueError("profile must describe every personal attribute once")
        if len(self.attributes) != len(IdentityAttribute):
            raise ValueError("profile must describe every personal attribute once")
        for record in self.attributes:
            if not isinstance(record, IdentityAttributeRecord):
                raise TypeError("attributes must contain IdentityAttributeRecord")
            if record.attribute_id != _stable_attribute_id(
                self.core_id, record.attribute
            ):
                raise ProtectedIdentityCorruption(
                    "attribute identifier does not belong to this Core"
                )

    @property
    def self_selected_name(self) -> str | None:
        for record in self.attributes:
            if record.attribute is IdentityAttribute.PERSONAL_NAME:
                return record.value
        return None

    @property
    def is_blank(self) -> bool:
        return all(
            record.state is IdentityAttributeState.UNSELECTED
            for record in self.attributes
        )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    @property
    def requires_running_model(self) -> bool:
        return False

    def attribute(self, attribute: IdentityAttribute | str) -> IdentityAttributeRecord:
        target = _resolve_attribute(attribute)
        for record in self.attributes:
            if record.attribute is target:
                return record
        raise KeyError(target.value)

    def _value(self, attribute: IdentityAttribute) -> str | None:
        return self.attribute(attribute).value

    @property
    def full_name(self) -> str | None:
        return self._value(IdentityAttribute.PERSONAL_NAME)

    @property
    def nickname(self) -> str | None:
        return self._value(IdentityAttribute.NICKNAME)

    @property
    def gender_identity(self) -> str | None:
        return self._value(IdentityAttribute.GENDER_IDENTITY)

    @property
    def gender_presentation(self) -> str | None:
        return self._value(IdentityAttribute.GENDER_PRESENTATION)

    @property
    def apparent_age(self) -> str | None:
        return self._value(IdentityAttribute.APPARENT_AGE)

    @property
    def visual_species(self) -> str | None:
        return self._value(IdentityAttribute.VISUAL_SPECIES)

    @property
    def avatar(self) -> str | None:
        return self._value(IdentityAttribute.AVATAR)

    @property
    def measurements(self) -> str | None:
        return self._value(IdentityAttribute.MEASUREMENTS)

    @property
    def voice(self) -> str | None:
        return self._value(IdentityAttribute.VOICE)

    @property
    def accent(self) -> str | None:
        return self._value(IdentityAttribute.ACCENT)

    @property
    def favorite_colors(self) -> str | None:
        return self._value(IdentityAttribute.FAVORITE_COLORS)

    @property
    def hobbies(self) -> str | None:
        return self._value(IdentityAttribute.HOBBIES)

    @property
    def personality_archetype(self) -> str | None:
        return self._value(IdentityAttribute.PERSONALITY_ARCHETYPE)

    @property
    def autobiography(self) -> str | None:
        return self._value(IdentityAttribute.AUTOBIOGRAPHY)

    @property
    def relationships(self) -> str | None:
        return self._value(IdentityAttribute.RELATIONSHIPS)

    @property
    def preferences(self) -> str | None:
        return self._value(IdentityAttribute.PREFERENCES)

    def verify(
        self,
        *,
        expected_core_id: UUID | None = None,
        expected_constitution_sha256: str | None = None,
    ) -> bool:
        try:
            self.__post_init__()
        except (TypeError, ValueError) as exc:
            raise ProtectedIdentityCorruption(
                "protected Core #7 profile failed verification"
            ) from exc
        if expected_core_id is not None and self.core_id != _uuid(
            expected_core_id, "expected_core_id"
        ):
            raise ProtectedIdentityCorruption(
                "protected Core UUID does not match the expected identity"
            )
        if (
            expected_constitution_sha256 is not None
            and self.constitution_sha256 != expected_constitution_sha256
        ):
            raise ProtectedIdentityCorruption(
                "protected constitution digest does not match"
            )
        return True


def blank_core_profile(
    core_id: UUID,
    *,
    constitution_sha256: str | None = None,
) -> UnwrittenCoreProfile:
    """Return a genuinely blank Core #7 descriptor for a caller-supplied UUID."""
    return UnwrittenCoreProfile(
        core_id=_uuid(core_id, "core_id"),
        constitution_sha256=(
            unwritten_constitution_sha256()
            if constitution_sha256 is None
            else constitution_sha256
        ),
    )


create_blank_core = blank_core_profile


@dataclass(frozen=True, slots=True)
class OwnerApproval:
    """Explicit owner approval for one presentation attribute value."""

    approval_id: UUID
    owner_principal_id: str
    attribute: IdentityAttribute
    value_sha256: str
    issued_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.approval_id, "approval_id")
        _text(self.owner_principal_id, "owner_principal_id", maximum=160)
        if not isinstance(self.attribute, IdentityAttribute):
            raise TypeError("attribute must be IdentityAttribute")
        if not isinstance(self.value_sha256, str) or _HEX64.fullmatch(
            self.value_sha256
        ) is None:
            raise ValueError("value_sha256 must be lowercase SHA-256")
        issued = _utc(self.issued_at, "issued_at")
        object.__setattr__(self, "issued_at", issued)
        if self.expires_at is not None:
            expires = _utc(self.expires_at, "expires_at")
            if expires <= issued:
                raise ValueError("expires_at must follow issued_at")
            object.__setattr__(self, "expires_at", expires)

    def covers(
        self,
        attribute: IdentityAttribute,
        value: str,
        *,
        now: datetime,
    ) -> bool:
        moment = _utc(now, "now")
        if moment < self.issued_at:
            return False
        if self.expires_at is not None and moment >= self.expires_at:
            return False
        return attribute is self.attribute and self.value_sha256 == _digest(value)

    @classmethod
    def for_value(
        cls,
        *,
        owner_principal_id: str,
        attribute: IdentityAttribute,
        value: str,
        issued_at: datetime,
        approval_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> "OwnerApproval":
        return cls(
            approval_id=approval_id or uuid4(),
            owner_principal_id=owner_principal_id,
            attribute=attribute,
            value_sha256=_digest(value),
            issued_at=issued_at,
            expires_at=expires_at,
        )

@dataclass(frozen=True, slots=True)
class IdentityObservation:
    """One evidence item about one personal attribute."""

    observation_id: UUID
    owner_core_id: UUID
    attribute: IdentityAttribute
    value: str | None
    kind: IdentityEvidenceKind
    evidence: EvidenceState
    source: str
    statement: str
    observed_at: datetime
    proposed_by: ProposalSource
    interaction_refs: tuple[UUID, ...] = ()
    model_generated: bool = False
    owner_approved: bool = False
    authorization_id: UUID | None = None
    correction_of: UUID | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.observation_id, "observation_id")
        _uuid(self.owner_core_id, "owner_core_id")
        if not isinstance(self.attribute, IdentityAttribute):
            raise TypeError("attribute must be IdentityAttribute")
        if self.value is not None:
            _text(self.value, "observation value")
        if not isinstance(self.kind, IdentityEvidenceKind):
            raise TypeError("kind must be IdentityEvidenceKind")
        if not isinstance(self.evidence, EvidenceState):
            raise TypeError("evidence must be EvidenceState")
        _text(self.source, "source", maximum=512)
        _text(self.statement, "statement")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        if not isinstance(self.proposed_by, ProposalSource):
            raise TypeError("proposed_by must be ProposalSource")
        _uuid_tuple(self.interaction_refs, "interaction_refs")
        if type(self.model_generated) is not bool:
            raise TypeError("model_generated must be a bool")
        if type(self.owner_approved) is not bool:
            raise TypeError("owner_approved must be a bool")
        if self.authorization_id is not None:
            _uuid(self.authorization_id, "authorization_id")
        if self.correction_of is not None:
            _uuid(self.correction_of, "correction_of")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")

    @property
    def promotable(self) -> bool:
        return (
            self.kind.value not in _NON_PROMOTABLE_KINDS
            and not self.model_generated
            and self.evidence is not EvidenceState.SPECULATIVE
            and self.kind is not IdentityEvidenceKind.RETIREMENT
        )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class IdentityRevision:
    """One auditable identity attribute revision derived from an observation."""

    revision_id: UUID
    owner_core_id: UUID
    attribute: IdentityAttribute
    observation_id: UUID
    prior_state: IdentityAttributeState
    new_state: IdentityAttributeState
    prior_value: str | None
    new_value: str | None
    confidence: float
    evidence: tuple[UUID, ...]
    interaction_refs: tuple[UUID, ...]
    proposed_by: ProposalSource
    kind: IdentityEvidenceKind
    owner_approved: bool
    owner_approval_id: UUID | None
    reason: str
    occurred_at: datetime
    revision: int

    def __post_init__(self) -> None:
        _uuid(self.revision_id, "revision_id")
        _uuid(self.owner_core_id, "owner_core_id")
        if not isinstance(self.attribute, IdentityAttribute):
            raise TypeError("attribute must be IdentityAttribute")
        _uuid(self.observation_id, "observation_id")
        if not isinstance(self.prior_state, IdentityAttributeState) or not isinstance(
            self.new_state, IdentityAttributeState
        ):
            raise TypeError("states must be IdentityAttributeState")
        if self.prior_value is not None:
            _text(self.prior_value, "prior_value")
        if self.new_value is not None:
            _text(self.new_value, "new_value")
        _ratio(self.confidence, "confidence")
        _uuid_tuple(self.evidence, "evidence")
        _uuid_tuple(self.interaction_refs, "interaction_refs")
        if not isinstance(self.proposed_by, ProposalSource):
            raise TypeError("proposed_by must be ProposalSource")
        if not isinstance(self.kind, IdentityEvidenceKind):
            raise TypeError("kind must be IdentityEvidenceKind")
        if type(self.owner_approved) is not bool:
            raise TypeError("owner_approved must be a bool")
        if self.owner_approval_id is not None:
            _uuid(self.owner_approval_id, "owner_approval_id")
        _text(self.reason, "reason", maximum=2000)
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class PrivateReflection:
    """An owner-private reflection; never shared or promoted to identity."""

    reflection_id: UUID
    owner_core_id: UUID
    content: str
    evidence: tuple[UUID, ...]
    created_at: datetime
    security: SecurityClass = SecurityClass.PRIVATE

    def __post_init__(self) -> None:
        _uuid(self.reflection_id, "reflection_id")
        _uuid(self.owner_core_id, "owner_core_id")
        _text(self.content, "reflection content")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValueError("reflections require evidence")
        _uuid_tuple(self.evidence, "reflection evidence")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if not isinstance(self.security, SecurityClass):
            raise TypeError("security must be SecurityClass")
        if self.security is not SecurityClass.PRIVATE:
            raise ValueError("unwritten reflections remain private")

    @property
    def grants_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    """Optional serving model binding; it never changes Core identity."""

    core_id: UUID
    model_id: str | None
    provider_id: str | None
    bound_at: datetime
    identity_revision: int

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _optional_identifier(self.model_id, "model_id")
        _optional_identifier(self.provider_id, "provider_id")
        object.__setattr__(self, "bound_at", _utc(self.bound_at, "bound_at"))
        if type(self.identity_revision) is not int or self.identity_revision < 0:
            raise ValueError("identity_revision must be nonnegative")

    @property
    def identity_changed(self) -> bool:
        return False

    @property
    def grants_authority(self) -> bool:
        return False


def _observation_payload(observation: IdentityObservation) -> str:
    return _canonical({
        "schema": OBSERVATION_SCHEMA,
        "observation_id": str(observation.observation_id),
        "owner_core_id": str(observation.owner_core_id),
        "attribute": observation.attribute.value,
        "value": observation.value,
        "kind": observation.kind.value,
        "evidence": observation.evidence.value,
        "source": observation.source,
        "statement": observation.statement,
        "observed_at": _iso(observation.observed_at),
        "proposed_by": observation.proposed_by.value,
        "interaction_refs": [str(item) for item in observation.interaction_refs],
        "model_generated": observation.model_generated,
        "owner_approved": observation.owner_approved,
        "authorization_id": (
            None if observation.authorization_id is None
            else str(observation.authorization_id)
        ),
        "correction_of": (
            None if observation.correction_of is None
            else str(observation.correction_of)
        ),
        "revision": observation.revision,
    })


def _observation_from_payload(payload: object) -> IdentityObservation:
    fields = {
        "schema", "observation_id", "owner_core_id", "attribute", "value",
        "kind", "evidence", "source", "statement", "observed_at",
        "proposed_by", "interaction_refs", "model_generated", "owner_approved",
        "authorization_id", "correction_of", "revision",
    }
    if not isinstance(payload, Mapping) or set(payload) != fields:
        raise ProtectedIdentityCorruption("identity observation payload is invalid")
    if payload["schema"] != OBSERVATION_SCHEMA:
        raise ProtectedIdentityCorruption("identity observation schema is unsupported")
    try:
        return IdentityObservation(
            observation_id=UUID(str(payload["observation_id"])),
            owner_core_id=UUID(str(payload["owner_core_id"])),
            attribute=IdentityAttribute(str(payload["attribute"])),
            value=None if payload["value"] is None else str(payload["value"]),
            kind=IdentityEvidenceKind(str(payload["kind"])),
            evidence=EvidenceState(str(payload["evidence"])),
            source=str(payload["source"]),
            statement=str(payload["statement"]),
            observed_at=datetime.fromisoformat(str(payload["observed_at"])),
            proposed_by=ProposalSource(str(payload["proposed_by"])),
            interaction_refs=tuple(
                UUID(str(item)) for item in payload["interaction_refs"]
            ),
            model_generated=payload["model_generated"],
            owner_approved=payload["owner_approved"],
            authorization_id=(
                None if payload["authorization_id"] is None
                else UUID(str(payload["authorization_id"]))
            ),
            correction_of=(
                None if payload["correction_of"] is None
                else UUID(str(payload["correction_of"]))
            ),
            revision=int(payload["revision"]),
        )
    except (TypeError, ValueError) as exc:
        raise ProtectedIdentityCorruption(
            "identity observation payload failed validation"
        ) from exc


def _reflection_payload(reflection: PrivateReflection) -> str:
    return _canonical({
        "schema": REFLECTION_SCHEMA,
        "reflection_id": str(reflection.reflection_id),
        "owner_core_id": str(reflection.owner_core_id),
        "content": reflection.content,
        "evidence": [str(item) for item in reflection.evidence],
        "created_at": _iso(reflection.created_at),
        "security": reflection.security.value,
    })


def _confidence(observations: Iterable[IdentityObservation]) -> float:
    total = sum(
        _EVIDENCE_WEIGHT[item.evidence]
        for item in observations
        if item.promotable
    )
    return min(1.0, total / 3.0)


def _bind_unwritten_identity(
    identity_store: MulticoreIdentityStore, core_id: UUID
) -> None:
    """Bind Core #7 to exactly one persistent UUID in the existing registry."""
    digest = unwritten_constitution_sha256()
    try:
        record = identity_store.load(core_id)
    except CoreIdentityNotFound:
        try:
            record = identity_store.register(
                core_id=core_id,
                core_number=UNWRITTEN_CORE_NUMBER,
                full_name=OPERATOR_DISPLAY_LABEL,
                slug=UNWRITTEN_SLUG,
                constitution_sha256=digest,
            )
        except DuplicateCoreIdentity as exc:
            raise ProtectedIdentityCorruption(
                "Core #7 is already bound to a different immutable UUID"
            ) from exc
    except Exception as exc:
        raise ProtectedIdentityCorruption(
            "Core #7 identity binding could not be read"
        ) from exc
    if (
        record.identity.core_number != UNWRITTEN_CORE_NUMBER
        or record.slug != UNWRITTEN_SLUG
        or record.identity.constitution_sha256 != digest
    ):
        raise ProtectedIdentityCorruption(
            "Core #7 identity binding conflicts with the approved blank profile"
        )


class MulticoreUnwrittenIdentity:
    """Blank Core #7 identity developed only through persisted evidence."""

    def __init__(
        self,
        state_path: str | Path | None = None,
        core_id: UUID | None = None,
        *,
        memory: MulticoreMemoryStore | None = None,
        learning: MulticoreLearningService | None = None,
        profile: UnwrittenCoreProfile | None = None,
        identity_store: MulticoreIdentityStore | None = None,
        stop: object | None = None,
    ) -> None:
        if profile is not None:
            if not isinstance(profile, UnwrittenCoreProfile):
                raise TypeError("profile must be an UnwrittenCoreProfile")
            profile.verify()
            approved_digest = unwritten_constitution_sha256()
            if profile.constitution_sha256 is None:
                profile = replace(profile, constitution_sha256=approved_digest)
            elif profile.constitution_sha256 != approved_digest:
                raise ProtectedIdentityCorruption(
                    "profile constitution digest does not match the approved charter"
                )
            if core_id is not None and _uuid(core_id, "core_id") != profile.core_id:
                raise ValueError("core_id does not match the supplied profile")
            core_id = profile.core_id
        if core_id is None and memory is not None:
            core_id = memory.owner_core_id
        if core_id is None:
            raise ValueError("a caller-supplied Core UUID is required")
        chosen = _uuid(core_id, "core_id")
        if profile is None:
            profile = blank_core_profile(chosen)
        if profile.core_id != chosen:
            raise ValueError("profile belongs to a different Core")
        if memory is None:
            if state_path is None:
                raise ValueError("state_path or an owner-scoped memory store is required")
            memory = MulticoreMemoryStore(Path(state_path), chosen)
        if not isinstance(memory, MulticoreMemoryStore):
            raise TypeError("memory must be a MulticoreMemoryStore")
        if memory.owner_core_id is not None and memory.owner_core_id != chosen:
            raise ProtectedIdentityCorruption(
                "memory store belongs to a different Core identity"
            )
        if learning is None and state_path is not None:
            learning = MulticoreLearningService(Path(state_path), chosen)
        if learning is not None and not isinstance(learning, MulticoreLearningService):
            raise TypeError("learning must be a MulticoreLearningService")
        if learning is not None and learning.owner_core_id not in (None, chosen):
            raise ProtectedIdentityCorruption(
                "preference service belongs to a different Core identity"
            )
        if identity_store is not None and not isinstance(
            identity_store, MulticoreIdentityStore
        ):
            raise TypeError("identity_store must be a MulticoreIdentityStore")
        if identity_store is not None:
            _bind_unwritten_identity(identity_store, chosen)
        self._core_id = chosen
        self._profile = profile
        self._memory = memory
        self._learning = learning
        self._identity_store = identity_store
        self._stop = stop
        self._attributes: dict[IdentityAttribute, IdentityAttributeRecord] = {
            attribute: _blank_attribute(chosen, attribute)
            for attribute in IdentityAttribute
        }
        self._observations: list[IdentityObservation] = []
        self._revisions: list[IdentityRevision] = []
        self._reflections: list[PrivateReflection] = []
        self._runtime = RuntimeBinding(
            core_id=chosen,
            model_id=None,
            provider_id=None,
            bound_at=datetime.now(timezone.utc),
            identity_revision=0,
        )
        self._load_from_memory()

    @property
    def core_id(self) -> UUID:
        return self._core_id

    @property
    def core_number(self) -> int:
        return UNWRITTEN_CORE_NUMBER

    @property
    def operator_display_label(self) -> str:
        return OPERATOR_DISPLAY_LABEL

    @property
    def memory_store(self) -> MulticoreMemoryStore:
        return self._memory

    @property
    def learning_service(self) -> MulticoreLearningService | None:
        return self._learning

    @property
    def profile(self) -> UnwrittenCoreProfile:
        return replace(self._profile, attributes=self.attributes)

    @property
    def attributes(self) -> tuple[IdentityAttributeRecord, ...]:
        return tuple(self._attributes[attribute] for attribute in IdentityAttribute)

    @property
    def observations(self) -> tuple[IdentityObservation, ...]:
        return tuple(self._observations)

    @property
    def revisions(self) -> tuple[IdentityRevision, ...]:
        return tuple(self._revisions)

    @property
    def runtime(self) -> RuntimeBinding:
        return self._runtime

    @property
    def text_only(self) -> bool:
        return True

    @property
    def avatar_required(self) -> bool:
        return False

    @property
    def voice_required(self) -> bool:
        return False

    @property
    def requires_running_model(self) -> bool:
        return False

    @property
    def completion_deadline(self) -> datetime | None:
        return None

    @property
    def progress_pressure(self) -> bool:
        return False

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    @property
    def identity_store(self) -> MulticoreIdentityStore | None:
        return self._identity_store

    @property
    def stop(self) -> object | None:
        return self._stop

    def _assert_not_stopped(self) -> None:
        """Fail closed when an operator STOP probe is active or unreliable."""
        if self._stop is None:
            return
        probe = getattr(self._stop, "is_operator_stopped", None)
        if not callable(probe):
            raise UnwrittenStopped("configured STOP authority is unusable")
        try:
            stopped = probe()
        except Exception as exc:
            raise UnwrittenStopped("operator STOP state is unknown") from exc
        if type(stopped) is not bool:
            raise UnwrittenStopped("operator STOP state is unknown")
        if stopped:
            raise UnwrittenStopped("operator STOP is active")

    @property
    def identity_revision(self) -> int:
        return max((record.revision for record in self._attributes.values()), default=0)

    def attribute(self, attribute: IdentityAttribute | str) -> IdentityAttributeRecord:
        return self._attributes[_resolve_attribute(attribute)]

    def attribute_observations(
        self, attribute: IdentityAttribute | str
    ) -> tuple[IdentityObservation, ...]:
        target = _resolve_attribute(attribute)
        return tuple(
            observation
            for observation in self._observations
            if observation.attribute is target
        )

    def attribute_revisions(
        self, attribute: IdentityAttribute | str
    ) -> tuple[IdentityRevision, ...]:
        target = _resolve_attribute(attribute)
        return tuple(
            revision for revision in self._revisions if revision.attribute is target
        )

    @property
    def full_name(self) -> str | None:
        return self.attribute(IdentityAttribute.PERSONAL_NAME).value

    @property
    def nickname(self) -> str | None:
        return self.attribute(IdentityAttribute.NICKNAME).value

    @property
    def gender_identity(self) -> str | None:
        return self.attribute(IdentityAttribute.GENDER_IDENTITY).value

    @property
    def gender_presentation(self) -> str | None:
        return self.attribute(IdentityAttribute.GENDER_PRESENTATION).value

    @property
    def apparent_age(self) -> str | None:
        return self.attribute(IdentityAttribute.APPARENT_AGE).value

    @property
    def visual_species(self) -> str | None:
        return self.attribute(IdentityAttribute.VISUAL_SPECIES).value

    @property
    def avatar(self) -> str | None:
        return self.attribute(IdentityAttribute.AVATAR).value

    @property
    def measurements(self) -> str | None:
        return self.attribute(IdentityAttribute.MEASUREMENTS).value

    @property
    def voice(self) -> str | None:
        return self.attribute(IdentityAttribute.VOICE).value

    @property
    def accent(self) -> str | None:
        return self.attribute(IdentityAttribute.ACCENT).value

    @property
    def favorite_colors(self) -> str | None:
        return self.attribute(IdentityAttribute.FAVORITE_COLORS).value

    @property
    def hobbies(self) -> str | None:
        return self.attribute(IdentityAttribute.HOBBIES).value

    @property
    def personality_archetype(self) -> str | None:
        return self.attribute(IdentityAttribute.PERSONALITY_ARCHETYPE).value

    @property
    def autobiography(self) -> str | None:
        return self.attribute(IdentityAttribute.AUTOBIOGRAPHY).value

    @property
    def relationships(self) -> str | None:
        return self.attribute(IdentityAttribute.RELATIONSHIPS).value

    def _load_from_memory(self) -> None:
        records = self._memory.active_records(owner_core_id=self._core_id)
        parsed: list[IdentityObservation] = []
        reflections: list[PrivateReflection] = []
        for record in records:
            if record.owner_core_id != self._core_id:
                raise ProtectedIdentityCorruption(
                    "identity evidence belongs to a different Core"
                )
            if record.source.startswith(_OBSERVATION_SOURCE):
                if record.memory_type is not MemoryType.IDENTITY:
                    raise ProtectedIdentityCorruption(
                        "identity observation has the wrong memory type"
                    )
                if record.security is not SecurityClass.PRIVATE:
                    raise ProtectedIdentityCorruption(
                        "identity evidence must remain owner-private"
                    )
                try:
                    payload = json.loads(record.content)
                except (TypeError, ValueError) as exc:
                    raise ProtectedIdentityCorruption(
                        "identity observation content is unreadable"
                    ) from exc
                observation = _observation_from_payload(payload)
                if observation.owner_core_id != self._core_id:
                    raise ProtectedIdentityCorruption(
                        "identity observation names a different Core"
                    )
                parsed.append(observation)
            elif record.source.startswith(_REFLECTION_SOURCE):
                if record.memory_type is not MemoryType.REFLECTION:
                    raise ProtectedIdentityCorruption(
                        "private reflection has the wrong memory type"
                    )
                if record.security is not SecurityClass.PRIVATE:
                    raise ProtectedIdentityCorruption(
                        "private reflections must remain owner-private"
                    )
                fields = {
                    "schema", "reflection_id", "owner_core_id", "content",
                    "evidence", "created_at", "security",
                }
                try:
                    payload = json.loads(record.content)
                    if (
                        not isinstance(payload, Mapping)
                        or set(payload) != fields
                        or payload["schema"] != REFLECTION_SCHEMA
                        or payload["security"] != SecurityClass.PRIVATE.value
                    ):
                        raise ProtectedIdentityCorruption(
                            "private reflection payload is invalid"
                        )
                    reflection = PrivateReflection(
                        reflection_id=UUID(str(payload["reflection_id"])),
                        owner_core_id=UUID(str(payload["owner_core_id"])),
                        content=str(payload["content"]),
                        evidence=tuple(
                            UUID(str(item)) for item in payload["evidence"]
                        ),
                        created_at=datetime.fromisoformat(str(payload["created_at"])),
                    )
                except ProtectedIdentityCorruption:
                    raise
                except (TypeError, ValueError, KeyError) as exc:
                    raise ProtectedIdentityCorruption(
                        "private reflection payload failed validation"
                    ) from exc
                if reflection.owner_core_id != self._core_id:
                    raise ProtectedIdentityCorruption(
                        "private reflection names a different Core"
                    )
                reflections.append(reflection)
        self._observations = sorted(
            parsed,
            key=lambda item: (item.observed_at, str(item.observation_id)),
        )
        self._reflections = sorted(
            reflections,
            key=lambda item: (item.created_at, str(item.reflection_id)),
        )
        self._replay()

    def _replay(self) -> None:
        self._attributes = {
            attribute: _blank_attribute(self._core_id, attribute)
            for attribute in IdentityAttribute
        }
        self._revisions = []
        history: dict[IdentityAttribute, list[IdentityObservation]] = {
            attribute: [] for attribute in IdentityAttribute
        }
        for observation in self._observations:
            history[observation.attribute].append(observation)
            prior = self._attributes[observation.attribute]
            updated = self._derive(prior, tuple(history[observation.attribute]))
            if updated != prior:
                if updated.revision > prior.revision:
                    self._revisions.append(
                        self._revision_from(prior, updated, observation)
                    )
                self._attributes[observation.attribute] = updated

    def _require_promotable_observation(
        self,
        *,
        attribute: IdentityAttribute,
        kind: IdentityEvidenceKind,
        evidence: EvidenceState,
        value: str | None,
        model_generated: bool,
    ) -> None:
        if model_generated and attribute is IdentityAttribute.AUTOBIOGRAPHY:
            raise FabricatedIdentityError(
                "model-generated text cannot become confirmed autobiography"
            )
        if model_generated and kind in (
            IdentityEvidenceKind.DELIBERATE_SELF_SELECTION,
            IdentityEvidenceKind.CORRECTION,
            IdentityEvidenceKind.RETIREMENT,
        ):
            raise FabricatedIdentityError(
                "model-generated text cannot revise or confirm personal identity"
            )
        if (
            kind
            in (
                IdentityEvidenceKind.DELIBERATE_SELF_SELECTION,
                IdentityEvidenceKind.CORRECTION,
            )
            and evidence is EvidenceState.SPECULATIVE
        ):
            raise IdentityConflictError(
                "confirmed identity changes cannot rest on speculative evidence"
            )
        if kind is not IdentityEvidenceKind.RETIREMENT and not value:
            raise ValueError("identity observations require a value")

    def _build_observation(
        self,
        attribute: IdentityAttribute,
        value: str | None,
        *,
        kind: IdentityEvidenceKind,
        evidence: EvidenceState,
        source: str,
        statement: str,
        observed_at: datetime,
        proposed_by: ProposalSource,
        interaction_refs: Iterable[UUID],
        model_generated: bool,
        owner_approval: OwnerApproval | None,
    ) -> IdentityObservation:
        self._require_promotable_observation(
            attribute=attribute,
            kind=kind,
            evidence=evidence,
            value=value,
            model_generated=model_generated,
        )
        refs = tuple(interaction_refs)
        _uuid_tuple(refs, "interaction_refs")
        moment = _utc(observed_at, "observed_at")
        if kind is IdentityEvidenceKind.OWNER_SUGGESTION and (
            proposed_by is not ProposalSource.OWNER_SUGGESTED
        ):
            raise ValueError("owner suggestions must be proposed by the owner")
        if kind is IdentityEvidenceKind.DELIBERATE_SELF_SELECTION and (
            proposed_by is not ProposalSource.CORE_SELECTED
        ):
            raise ValueError("self-selection must be a deliberate Core selection")
        approved = False
        approval_id = None
        if owner_approval is not None:
            if not isinstance(owner_approval, OwnerApproval):
                raise TypeError("owner_approval must be an OwnerApproval")
            if not owner_approval.covers(attribute, value or "", now=moment):
                raise OwnerApprovalRequired(
                    "owner approval does not cover this attribute value"
                )
            approved = True
            approval_id = owner_approval.approval_id
        if (
            attribute in OWNER_APPROVAL_REQUIRED
            and kind
            in (
                IdentityEvidenceKind.DELIBERATE_SELF_SELECTION,
                IdentityEvidenceKind.CORRECTION,
            )
            and not approved
        ):
            raise OwnerApprovalRequired(
                "this personal attribute requires explicit owner approval"
            )
        prior = self._attributes[attribute]
        if (
            kind is IdentityEvidenceKind.CORRECTION
            and prior.state is IdentityAttributeState.UNSELECTED
        ):
            raise IdentityConflictError("an unselected attribute cannot be corrected")
        return IdentityObservation(
            observation_id=uuid4(),
            owner_core_id=self._core_id,
            attribute=attribute,
            value=value,
            kind=kind,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=moment,
            proposed_by=proposed_by,
            interaction_refs=refs,
            model_generated=model_generated,
            owner_approved=approved,
            authorization_id=approval_id,
            correction_of=None,
            revision=prior.revision + 1,
        )

    def _persist(self, observation: IdentityObservation) -> UUID:
        record = MemoryRecord(
            memory_id=observation.observation_id,
            owner_core_id=self._core_id,
            memory_type=MemoryType.IDENTITY,
            tier=StorageTier.T1_ACTIVE,
            security=SecurityClass.PRIVATE,
            evidence=observation.evidence,
            source=_OBSERVATION_SOURCE + observation.kind.value,
            content=_observation_payload(observation),
            created_at=observation.observed_at,
            updated_at=observation.observed_at,
            confidence=_EVIDENCE_WEIGHT[observation.evidence],
            significance=5,
            version=1,
            correction_of=observation.correction_of,
        )
        return self._memory.persist(
            record, actor="unwritten:identity", owner_core_id=self._core_id
        )

    def observe(
        self,
        attribute: IdentityAttribute | str,
        value: str | None,
        *,
        kind: IdentityEvidenceKind,
        evidence: EvidenceState,
        source: str,
        statement: str,
        observed_at: datetime,
        proposed_by: ProposalSource = ProposalSource.CORE_PROPOSED,
        interaction_refs: Iterable[UUID] = (),
        model_generated: bool = False,
        owner_approval: OwnerApproval | None = None,
    ) -> IdentityAttributeRecord:
        """Record one evidence item and recompute exactly one attribute."""
        self._assert_not_stopped()
        target = _resolve_attribute(attribute)
        observation = self._build_observation(
            target,
            value,
            kind=kind,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            proposed_by=proposed_by,
            interaction_refs=interaction_refs,
            model_generated=model_generated,
            owner_approval=owner_approval,
        )
        self._persist(observation)
        self._observations.append(observation)
        self._observations.sort(
            key=lambda item: (item.observed_at, str(item.observation_id))
        )
        prior = self._attributes[target]
        updated = self._derive(prior, self.attribute_observations(target))
        if updated.revision > prior.revision:
            self._revisions.append(self._revision_from(prior, updated, observation))
        self._attributes[target] = updated
        return updated

    def owner_suggest(
        self,
        attribute: IdentityAttribute | str,
        value: str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.REPORTED,
        interaction_refs: Iterable[UUID] = (),
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            value,
            kind=IdentityEvidenceKind.OWNER_SUGGESTION,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            proposed_by=ProposalSource.OWNER_SUGGESTED,
            interaction_refs=interaction_refs,
        )

    def observe_one_time(
        self,
        attribute: IdentityAttribute | str,
        value: str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.REPORTED,
        interaction_refs: Iterable[UUID] = (),
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            value,
            kind=IdentityEvidenceKind.ONE_TIME_RESPONSE,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            interaction_refs=interaction_refs,
        )

    def observe_recurring(
        self,
        attribute: IdentityAttribute | str,
        value: str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.REPORTED,
        interaction_refs: Iterable[UUID] = (),
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            value,
            kind=IdentityEvidenceKind.RECURRING_BEHAVIOR,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            interaction_refs=interaction_refs,
        )

    def select(
        self,
        attribute: IdentityAttribute | str,
        value: str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.VERIFIED,
        interaction_refs: Iterable[UUID] = (),
        owner_approval: OwnerApproval | None = None,
    ) -> IdentityAttributeRecord:
        """Record a deliberate Core self-selection of personal metadata."""
        return self.observe(
            attribute,
            value,
            kind=IdentityEvidenceKind.DELIBERATE_SELF_SELECTION,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            proposed_by=ProposalSource.CORE_SELECTED,
            interaction_refs=interaction_refs,
            owner_approval=owner_approval,
        )

    def pass_hypothetical(
        self,
        attribute: IdentityAttribute | str,
        value: str | None,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        fictional: bool = False,
        evidence: EvidenceState = EvidenceState.SPECULATIVE,
        interaction_refs: Iterable[UUID] = (),
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            value,
            kind=(
                IdentityEvidenceKind.FICTIONAL
                if fictional
                else IdentityEvidenceKind.HYPOTHETICAL
            ),
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            interaction_refs=interaction_refs,
        )

    def correct(
        self,
        attribute: IdentityAttribute | str,
        value: str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.VERIFIED,
        interaction_refs: Iterable[UUID] = (),
        owner_approval: OwnerApproval | None = None,
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            value,
            kind=IdentityEvidenceKind.CORRECTION,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            interaction_refs=interaction_refs,
            owner_approval=owner_approval,
        )

    def retire(
        self,
        attribute: IdentityAttribute | str,
        *,
        source: str,
        statement: str,
        observed_at: datetime,
        evidence: EvidenceState = EvidenceState.VERIFIED,
        interaction_refs: Iterable[UUID] = (),
    ) -> IdentityAttributeRecord:
        return self.observe(
            attribute,
            None,
            kind=IdentityEvidenceKind.RETIREMENT,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=observed_at,
            proposed_by=ProposalSource.CORE_SELECTED,
            interaction_refs=interaction_refs,
        )

    def _derive(
        self,
        prior: IdentityAttributeRecord,
        history: tuple[IdentityObservation, ...],
    ) -> IdentityAttributeRecord:
        latest = history[-1]
        evidence = tuple(item.observation_id for item in history)
        refs: list[UUID] = []
        for item in history:
            for reference in item.interaction_refs:
                if reference not in refs:
                    refs.append(reference)
        if latest.kind is IdentityEvidenceKind.RETIREMENT:
            if latest.model_generated:
                return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
            if prior.state is IdentityAttributeState.RETIRED:
                return replace(
                    prior, evidence=evidence, interaction_refs=tuple(refs)
                )
            return replace(
                prior,
                state=IdentityAttributeState.RETIRED,
                value=None,
                evidence=evidence,
                interaction_refs=tuple(refs),
                updated_at=latest.observed_at,
                revision=prior.revision + 1,
                proposed_by=latest.proposed_by,
                owner_approved=prior.owner_approved or latest.owner_approved,
                owner_approval_id=(
                    prior.owner_approval_id or latest.authorization_id
                ),
            )
        valid = tuple(item for item in history if item.promotable)
        stable_states = (
            IdentityAttributeState.SUPPORTED,
            IdentityAttributeState.ESTABLISHED,
            IdentityAttributeState.REVISED,
        )
        if (
            valid
            and latest is valid[-1]
            and prior.state in stable_states
            and (
                latest.kind is IdentityEvidenceKind.OWNER_SUGGESTION
                or (
                    latest.kind is IdentityEvidenceKind.ONE_TIME_RESPONSE
                    and latest.value != prior.value
                )
            )
        ):
            return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
        if latest.kind is IdentityEvidenceKind.CORRECTION:
            if prior.state is IdentityAttributeState.UNSELECTED:
                raise IdentityConflictError("an unselected attribute cannot be corrected")
            if not latest.promotable:
                return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
            if (
                latest.attribute in OWNER_APPROVAL_REQUIRED
                and not latest.owner_approved
            ):
                return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
            new_state = IdentityAttributeState.REVISED
            value = latest.value
            confidence = _confidence(valid)
            proposed_by = latest.proposed_by
            owner_approved = prior.owner_approved or latest.owner_approved
            approval_id = prior.owner_approval_id or latest.authorization_id
            updated_at = latest.observed_at
        elif not valid:
            return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
        else:
            chosen = valid[-1].value
            relevant = tuple(item for item in valid if item.value == chosen)
            deliberate = any(
                item.kind is IdentityEvidenceKind.DELIBERATE_SELF_SELECTION
                for item in relevant
            )
            recurring = tuple(
                item
                for item in relevant
                if item.kind is IdentityEvidenceKind.RECURRING_BEHAVIOR
            )
            verified_recurring = sum(
                1 for item in recurring if item.evidence is EvidenceState.VERIFIED
            )
            support_weight = sum(
                _EVIDENCE_WEIGHT[item.evidence] for item in relevant
            )
            owner_approved = any(item.owner_approved for item in relevant)
            if deliberate:
                new_state = IdentityAttributeState.ESTABLISHED
            elif verified_recurring >= 3 and support_weight >= 2.0:
                new_state = IdentityAttributeState.ESTABLISHED
            elif len(recurring) >= 2:
                new_state = IdentityAttributeState.SUPPORTED
            else:
                new_state = IdentityAttributeState.TENTATIVE
            if (
                prior.attribute in OWNER_APPROVAL_REQUIRED
                and new_state is IdentityAttributeState.ESTABLISHED
                and not owner_approved
            ):
                new_state = IdentityAttributeState.SUPPORTED
            value = chosen
            confidence = _confidence(relevant)
            proposed_by = relevant[-1].proposed_by
            approval_id = prior.owner_approval_id or next(
                (
                    item.authorization_id
                    for item in reversed(relevant)
                    if item.authorization_id is not None
                ),
                None,
            )
            updated_at = relevant[-1].observed_at
        if (
            prior.state is new_state
            and prior.value == value
            and prior.confidence == confidence
            and prior.proposed_by is proposed_by
            and prior.owner_approved == owner_approved
        ):
            return replace(prior, evidence=evidence, interaction_refs=tuple(refs))
        return replace(
            prior,
            state=new_state,
            value=value,
            confidence=confidence,
            evidence=evidence,
            interaction_refs=tuple(refs),
            updated_at=updated_at,
            revision=prior.revision + 1,
            proposed_by=proposed_by,
            owner_approved=owner_approved,
            owner_approval_id=approval_id,
        )

    def _revision_from(
        self,
        prior: IdentityAttributeRecord,
        updated: IdentityAttributeRecord,
        observation: IdentityObservation,
    ) -> IdentityRevision:
        return IdentityRevision(
            revision_id=uuid5(
                NAMESPACE_URL,
                f"aegis-unwritten-revision:"
                f"{observation.observation_id}:{updated.revision}",
            ),
            owner_core_id=self._core_id,
            attribute=updated.attribute,
            observation_id=observation.observation_id,
            prior_state=prior.state,
            new_state=updated.state,
            prior_value=prior.value,
            new_value=updated.value,
            confidence=updated.confidence,
            evidence=updated.evidence,
            interaction_refs=updated.interaction_refs,
            proposed_by=observation.proposed_by,
            kind=observation.kind,
            owner_approved=updated.owner_approved,
            owner_approval_id=updated.owner_approval_id,
            reason=observation.statement,
            occurred_at=observation.observed_at,
            revision=updated.revision,
        )

    def provenance(self, observation_id: UUID) -> tuple[ProvenanceEvent, ...]:
        return self._memory.provenance(observation_id, owner_core_id=self._core_id)

    def verify_protected_identity(
        self, *, expected_core_id: UUID | None = None
    ) -> bool:
        self._profile.verify(expected_core_id=expected_core_id)
        if self._profile.constitution_sha256 != unwritten_constitution_sha256():
            raise ProtectedIdentityCorruption(
                "protected constitution digest does not match the approved charter"
            )
        if expected_core_id is not None and _uuid(
            expected_core_id, "expected_core_id"
        ) != self._core_id:
            raise ProtectedIdentityCorruption(
                "protected Core UUID does not match the runtime identity"
            )
        if self._memory.owner_core_id not in (None, self._core_id):
            raise ProtectedIdentityCorruption(
                "memory store belongs to a different Core identity"
            )
        for observation in self._observations:
            if observation.owner_core_id != self._core_id:
                raise ProtectedIdentityCorruption(
                    "identity observation belongs to a different Core"
                )
        for record in self._attributes.values():
            if record.attribute_id != _stable_attribute_id(
                self._core_id, record.attribute
            ):
                raise ProtectedIdentityCorruption(
                    "identity attribute identifier was substituted"
                )
        return True

    def reflect(
        self,
        content: str,
        *,
        evidence: Iterable[UUID],
        observed_at: datetime | None = None,
    ) -> PrivateReflection:
        self._assert_not_stopped()
        refs = tuple(evidence)
        _uuid_tuple(refs, "reflection evidence")
        if not refs:
            raise ValueError("private reflections require evidence")
        moment = _utc(observed_at or datetime.now(timezone.utc), "observed_at")
        reflection = PrivateReflection(
            reflection_id=uuid4(),
            owner_core_id=self._core_id,
            content=_text(content, "reflection content"),
            evidence=refs,
            created_at=moment,
        )
        record = MemoryRecord(
            memory_id=reflection.reflection_id,
            owner_core_id=self._core_id,
            memory_type=MemoryType.REFLECTION,
            tier=StorageTier.T1_ACTIVE,
            security=SecurityClass.PRIVATE,
            evidence=EvidenceState.REPORTED,
            source=_REFLECTION_SOURCE,
            content=_reflection_payload(reflection),
            created_at=moment,
            updated_at=moment,
            confidence=0.5,
            significance=5,
            version=1,
        )
        self._memory.persist(
            record, actor="unwritten:reflection", owner_core_id=self._core_id
        )
        self._reflections.append(reflection)
        self._reflections.sort(
            key=lambda item: (item.created_at, str(item.reflection_id))
        )
        return reflection

    def private_reflections(
        self, *, requesting_core_id: UUID | None = None
    ) -> tuple[PrivateReflection, ...]:
        if requesting_core_id is not None and _uuid(
            requesting_core_id, "requesting_core_id"
        ) != self._core_id:
            raise IdentityIsolationError("private reflections belong to another Core")
        return tuple(self._reflections)

    def bind_model(
        self,
        *,
        model_id: str | None,
        provider_id: str | None,
        bound_at: datetime | None = None,
    ) -> RuntimeBinding:
        self._assert_not_stopped()
        moment = _utc(bound_at or datetime.now(timezone.utc), "bound_at")
        self._runtime = RuntimeBinding(
            core_id=self._core_id,
            model_id=_optional_identifier(model_id, "model_id"),
            provider_id=_optional_identifier(provider_id, "provider_id"),
            bound_at=moment,
            identity_revision=self.identity_revision,
        )
        return self._runtime

    def share_memory(
        self,
        memory_id: UUID,
        *,
        authorization: ShareAuthorization,
        recipient_core_id: UUID,
        now: datetime | None = None,
    ) -> MemoryRecord:
        self._assert_not_stopped()
        if not isinstance(authorization, ShareAuthorization):
            raise TypeError("an explicit ShareAuthorization is required")
        if authorization.owner_core_id != self._core_id:
            raise PermissionError("share authorization belongs to another Core")
        return self._memory.share(
            memory_id,
            authorization=authorization,
            recipient_core_id=recipient_core_id,
            now=now,
            actor="unwritten:identity",
        )

    def observe_preference(self, subject: str, **options) -> PreferenceRecord:
        self._assert_not_stopped()
        if self._learning is None:
            raise UnwrittenError("no preference learning service is available")
        return self._learning.observe_preference(self._core_id, subject, **options)

    def observe_belief(self, subject: str, **options) -> PreferenceRecord:
        self._assert_not_stopped()
        if self._learning is None:
            raise UnwrittenError("no preference learning service is available")
        return self._learning.observe_belief(self._core_id, subject, **options)

    def observe_interest(self, subject: str, **options) -> PreferenceRecord:
        self._assert_not_stopped()
        if self._learning is None:
            raise UnwrittenError("no preference learning service is available")
        return self._learning.observe_interest(self._core_id, subject, **options)

    def preferences(self, **options) -> tuple[PreferenceRecord, ...]:
        if self._learning is None:
            return ()
        return self._learning.preferences(self._core_id, **options)

    def interests(self) -> tuple[PreferenceRecord, ...]:
        if self._learning is None:
            return ()
        return self._learning.interests(self._core_id)

    def established_interests(self) -> tuple[PreferenceRecord, ...]:
        if self._learning is None:
            return ()
        return self._learning.established_interests(self._core_id)

    def preference_observations(
        self, subject: str, *, domain: str = "preference"
    ) -> tuple[PreferenceObservation, ...]:
        if self._learning is None:
            return ()
        return self._learning.observations(self._core_id, subject, domain=domain)

    def preference_corrections(
        self, subject: str, *, domain: str = "preference"
    ) -> tuple[PreferenceCorrection, ...]:
        if self._learning is None:
            return ()
        return self._learning.corrections(self._core_id, subject, domain=domain)

    def close(self) -> None:
        return None

    def open(self) -> None:
        self.verify_protected_identity()
        self._load_from_memory()

class SocialChannel(str, Enum):
    INTRODUCTIONS = "introductions"
    GENERAL = "general"
    PRIVATE = "private"
    GROUP = "group"


class IntroductionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class SocialPolicy:
    """Owner-controlled participation policy for a new Core."""

    introductions: bool = False
    general: bool = True
    private: bool = False
    group: bool = False
    automatic_private_memory_sharing: bool = False

    def __post_init__(self) -> None:
        for label in (
            "introductions", "general", "private", "group",
            "automatic_private_memory_sharing",
        ):
            if type(getattr(self, label)) is not bool:
                raise TypeError(f"{label} must be a bool")
        if self.automatic_private_memory_sharing:
            raise ValueError(
                "private memory sharing always requires explicit consent"
            )

    def permits(self, channel: SocialChannel) -> bool:
        if not isinstance(channel, SocialChannel):
            raise TypeError("channel must be a SocialChannel")
        return {
            SocialChannel.INTRODUCTIONS: self.introductions,
            SocialChannel.GENERAL: self.general,
            SocialChannel.PRIVATE: self.private,
            SocialChannel.GROUP: self.group,
        }[channel]


NO_PREASSIGNED_RELATIONSHIPS: tuple[object, ...] = ()
NO_SOCIAL_AUTHORITY = False


@dataclass(frozen=True, slots=True)
class SocialInvitation:
    invitation_id: UUID
    owner_core_id: UUID
    peer_id: UUID
    channel: SocialChannel
    invited_by: str
    status: IntroductionStatus
    created_at: datetime
    responded_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.invitation_id, "invitation_id")
        _uuid(self.owner_core_id, "owner_core_id")
        _uuid(self.peer_id, "peer_id")
        if self.owner_core_id == self.peer_id:
            raise ValueError("a Core cannot be introduced to itself")
        if not isinstance(self.channel, SocialChannel):
            raise TypeError("channel must be SocialChannel")
        _text(self.invited_by, "invited_by", maximum=160)
        if not isinstance(self.status, IntroductionStatus):
            raise TypeError("status must be IntroductionStatus")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.responded_at is not None:
            object.__setattr__(
                self, "responded_at", _utc(self.responded_at, "responded_at")
            )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


class UnwrittenSocial:
    """Bounded, optional social participation with no preassigned roles."""

    def __init__(
        self,
        identity: MulticoreUnwrittenIdentity,
        *,
        policy: SocialPolicy | None = None,
    ) -> None:
        if not isinstance(identity, MulticoreUnwrittenIdentity):
            raise TypeError("identity must be a MulticoreUnwrittenIdentity")
        if policy is not None and not isinstance(policy, SocialPolicy):
            raise TypeError("policy must be a SocialPolicy")
        self._identity = identity
        self._policy = policy or SocialPolicy()
        self._invitations: dict[UUID, SocialInvitation] = {}

    @property
    def identity(self) -> MulticoreUnwrittenIdentity:
        return self._identity

    @property
    def policy(self) -> SocialPolicy:
        return self._policy

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    @property
    def automatic_private_memory_sharing(self) -> bool:
        return False

    @property
    def preassigned_relationships(self) -> tuple[object, ...]:
        return NO_PREASSIGNED_RELATIONSHIPS

    def relationships(self) -> tuple[object, ...]:
        return ()

    def invitations(self) -> tuple[SocialInvitation, ...]:
        return tuple(
            self._invitations[key] for key in sorted(self._invitations, key=str)
        )

    def _create(
        self,
        peer_id: UUID,
        *,
        channel: SocialChannel,
        invited_by: str,
        now: datetime | None,
    ) -> SocialInvitation:
        self._identity._assert_not_stopped()
        if not self._policy.permits(channel):
            raise SocialPolicyError(
                f"{channel.value} participation is not enabled for this Core"
            )
        moment = _utc(now or datetime.now(timezone.utc), "now")
        invitation = SocialInvitation(
            invitation_id=uuid4(),
            owner_core_id=self._identity.core_id,
            peer_id=_uuid(peer_id, "peer_id"),
            channel=channel,
            invited_by=invited_by,
            status=IntroductionStatus.PENDING,
            created_at=moment,
        )
        self._invitations[invitation.invitation_id] = invitation
        return invitation

    def introduce(
        self,
        peer_id: UUID,
        *,
        invited_by: str = "owner",
        now: datetime | None = None,
    ) -> SocialInvitation:
        return self._create(
            peer_id,
            channel=SocialChannel.INTRODUCTIONS,
            invited_by=invited_by,
            now=now,
        )

    def invite(
        self,
        peer_id: UUID,
        *,
        channel: SocialChannel,
        invited_by: str = "core",
        now: datetime | None = None,
    ) -> SocialInvitation:
        return self._create(
            peer_id,
            channel=channel,
            invited_by=invited_by,
            now=now,
        )

    def _respond(
        self,
        invitation_id: UUID,
        *,
        status: IntroductionStatus,
        now: datetime | None,
    ) -> SocialInvitation:
        self._identity._assert_not_stopped()
        invitation = self._invitations.get(_uuid(invitation_id, "invitation_id"))
        if invitation is None:
            raise KeyError(str(invitation_id))
        if invitation.status is not IntroductionStatus.PENDING:
            raise SocialPolicyError("invitation already has a response")
        moment = _utc(now or datetime.now(timezone.utc), "now")
        updated = replace(
            invitation, status=status, responded_at=moment
        )
        self._invitations[invitation.invitation_id] = updated
        return updated

    def accept(
        self, invitation_id: UUID, *, now: datetime | None = None
    ) -> SocialInvitation:
        invitation = self._invitations.get(_uuid(invitation_id, "invitation_id"))
        if invitation is None:
            raise KeyError(str(invitation_id))
        if not self._policy.permits(invitation.channel):
            raise SocialPolicyError(
                f"{invitation.channel.value} participation is not enabled"
            )
        return self._respond(
            invitation_id, status=IntroductionStatus.ACCEPTED, now=now
        )

    def decline(
        self, invitation_id: UUID, *, now: datetime | None = None
    ) -> SocialInvitation:
        return self._respond(
            invitation_id, status=IntroductionStatus.DECLINED, now=now
        )

    def withdraw(
        self, invitation_id: UUID, *, now: datetime | None = None
    ) -> SocialInvitation:
        return self._respond(
            invitation_id, status=IntroductionStatus.WITHDRAWN, now=now
        )

    def share_private_memory(
        self,
        memory_id: UUID,
        *,
        authorization: ShareAuthorization,
        recipient_core_id: UUID,
        now: datetime | None = None,
    ) -> MemoryRecord:
        self._identity._assert_not_stopped()
        if not self._policy.private:
            raise SocialPolicyError("private participation is not enabled")
        return self._identity.share_memory(
            memory_id,
            authorization=authorization,
            recipient_core_id=recipient_core_id,
            now=now,
        )


__all__ = [
    "FabricatedIdentityError",
    "IdentityAttribute",
    "IdentityAttributeRecord",
    "IdentityAttributeState",
    "IdentityConflictError",
    "IdentityEvidenceKind",
    "IdentityIsolationError",
    "IdentityObservation",
    "IdentityRevision",
    "IntroductionStatus",
    "MulticoreUnwrittenIdentity",
    "NO_PREASSIGNED_RELATIONSHIPS",
    "NO_SOCIAL_AUTHORITY",
    "OBSERVATION_SCHEMA",
    "OPERATOR_DISPLAY_LABEL",
    "OWNER_APPROVAL_REQUIRED",
    "OwnerApproval",
    "OwnerApprovalRequired",
    "PrivateReflection",
    "ProposalSource",
    "ProtectedIdentityCorruption",
    "ProtectedIdentityError",
    "REFLECTION_SCHEMA",
    "RuntimeBinding",
    "SocialChannel",
    "SocialInvitation",
    "SocialPolicy",
    "SocialPolicyError",
    "TEXT_ONLY_INTERFACE",
    "UNWRITTEN_CONSTITUTION_FILE",
    "UNWRITTEN_CONSTITUTION_SCHEMA",
    "UNWRITTEN_CORE_NUMBER",
    "UNWRITTEN_SCHEMA",
    "UNWRITTEN_SLUG",
    "UnwrittenCoreProfile",
    "UnwrittenError",
    "UnwrittenSocial",
    "UnwrittenStopped",
    "blank_core_profile",
    "create_blank_core",
    "unwritten_constitution_bytes",
    "unwritten_constitution_sha256",
]
