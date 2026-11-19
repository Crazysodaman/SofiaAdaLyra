"""Independent, persistent personality state for each Aegis Core.

This module owns *state and change governance*, not a central personality
controller.  Each Core holds its own :class:`PersonalityState`; no Core can
mutate another Core's personality through this module.  The module never
imports a model, provider or process handle, so personality continuity is
independent of the cognitive engine currently serving the Core.

Change classes are deliberately conservative:

``PROTECTED``
    Identity-bearing traits.  A change requires an injected owner
    authorization object.  The module cannot grant that authorization itself.

``STABLE``
    Enduring traits.  A change requires evidence and an explicit reviewer.

``ADAPTIVE``
    Traits that may move with experience.  A change requires evidence.

``TEMPORARY``
    Context-bound traits that expire.  An expiry horizon is mandatory.

Constructing any value here grants no execution authority and no access to
protected state.  Personality records describe modeled personal continuity;
they are not permissions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from sofia.core.multicore.contracts import EvidenceState


class PersonalityChangeClass(str, Enum):
    """How much scrutiny one personality change requires."""

    PROTECTED = "protected"
    STABLE = "stable"
    ADAPTIVE = "adaptive"
    TEMPORARY = "temporary"


class PersonalityError(RuntimeError):
    """Base failure for invalid or unsafe personality state."""


class PersonalityEvidenceError(PersonalityError):
    """A change lacks evidence of the required quality."""


class PersonalityAuthorizationError(PermissionError):
    """A protected personality change lacks injected owner authorization."""


class PersonalityContinuityError(PersonalityError):
    """A change would break the Core's continuous personality identity."""


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


def _ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
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


def _token(value: object, label: str) -> str:
    text = _text(value, label, maximum=80)
    if any(character.isspace() for character in text):
        raise ValueError(f"{label} must be one canonical token")
    return text


@dataclass(frozen=True, slots=True)
class PersonalityEvidence:
    """One evidence reference and its epistemic state.

    Evidence identifiers are opaque to this module.  Their source system
    remains the owner of the underlying evidence.
    """

    evidence_id: UUID
    state: EvidenceState = EvidenceState.REPORTED
    source: str = "observation"

    def __post_init__(self) -> None:
        _uuid(self.evidence_id, "evidence_id")
        if not isinstance(self.state, EvidenceState):
            raise TypeError("state must be EvidenceState")
        _token(self.source, "evidence source")

    @property
    def verified(self) -> bool:
        return self.state is EvidenceState.VERIFIED


@dataclass(frozen=True, slots=True)
class OwnerAuthorization:
    """Injected owner authorization for a protected change.

    The authorization is presented *to* this module; the module never mints,
    widens or infers one.  A scope of ``"*"`` authorizes every protected trait
    for that owner grant, while named scopes authorize only those traits.
    """

    authorization_id: UUID
    owner_principal_id: str
    scopes: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.authorization_id, "authorization_id")
        _text(self.owner_principal_id, "owner_principal_id", maximum=160)
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or any(not isinstance(scope, str) for scope in self.scopes)
        ):
            raise ValueError("scopes must be a nonempty tuple of strings")
        normalized = tuple(scope.strip() for scope in self.scopes)
        if any(not scope for scope in normalized):
            raise ValueError("scopes cannot contain empty entries")
        if len(set(normalized)) != len(normalized):
            raise ValueError("scopes must be distinct")
        object.__setattr__(self, "scopes", normalized)
        issued = _utc(self.issued_at, "issued_at")
        object.__setattr__(self, "issued_at", issued)
        if self.expires_at is not None:
            expires = _utc(self.expires_at, "expires_at")
            if expires <= issued:
                raise ValueError("expires_at must follow issued_at")
            object.__setattr__(self, "expires_at", expires)

    def authorizes(self, trait: str, *, now: datetime) -> bool:
        current = _utc(now, "now")
        if current < self.issued_at:
            return False
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return "*" in self.scopes or trait in self.scopes


@dataclass(frozen=True, slots=True)
class PersonalityTraitState:
    """The current modeled weight and governance class of one trait."""

    name: str
    weight: float
    change_class: PersonalityChangeClass
    evidence: tuple[PersonalityEvidence, ...] = ()
    updated_at: datetime = field(default_factory=_now)
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _token(self.name, "trait name")
        _ratio(self.weight, "trait weight")
        if not isinstance(self.change_class, PersonalityChangeClass):
            raise TypeError("change_class must be PersonalityChangeClass")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        for item in self.evidence:
            if not isinstance(item, PersonalityEvidence):
                raise TypeError("evidence entries must be PersonalityEvidence")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("trait evidence identifiers must be distinct")
        updated = _utc(self.updated_at, "updated_at")
        object.__setattr__(self, "updated_at", updated)
        if self.expires_at is not None:
            expires = _utc(self.expires_at, "expires_at")
            if expires <= updated:
                raise ValueError("a temporary change must expire after it was set")
            object.__setattr__(self, "expires_at", expires)

    def active(self, now: datetime) -> bool:
        return self.expires_at is None or _utc(now, "now") < self.expires_at


@dataclass(frozen=True, slots=True)
class PersonalityState:
    """One Core's current personality, independent of any runtime provider."""

    core_id: UUID
    core_number: int
    full_name: str
    continuity_key: str
    traits: tuple[PersonalityTraitState, ...]
    revision: int = 1
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if type(self.core_number) is not int or self.core_number < 2:
            raise ValueError("core_number must be an integer >= 2")
        _text(self.full_name, "full_name", maximum=160)
        _token(self.continuity_key, "continuity_key")
        if not isinstance(self.traits, tuple) or not self.traits:
            raise ValueError("traits must be a nonempty tuple")
        for trait in self.traits:
            if not isinstance(trait, PersonalityTraitState):
                raise TypeError("traits must be PersonalityTraitState values")
        names = tuple(trait.name for trait in self.traits)
        if len(set(names)) != len(names):
            raise ValueError("trait names must be distinct")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))

    def trait(self, name: str) -> PersonalityTraitState | None:
        target = _token(name, "trait name")
        for trait in self.traits:
            if trait.name == target:
                return trait
        return None

    def active_traits(self, now: datetime) -> tuple[PersonalityTraitState, ...]:
        return tuple(
            trait for trait in self.traits
            if trait.active(now)
        )

    def weight(self, name: str, *, now: datetime | None = None) -> float:
        trait = self.trait(name)
        if trait is None:
            return 0.0
        if now is not None and not trait.active(now):
            return 0.0
        return trait.weight

    def weights(self, *, now: datetime | None = None) -> Mapping[str, float]:
        traits = self.traits if now is None else self.active_traits(now)
        return MappingProxyType({trait.name: trait.weight for trait in traits})


@dataclass(frozen=True, slots=True)
class PersonalityTraitSeed:
    """One baseline trait in a Core personality profile."""

    name: str
    weight: float
    change_class: PersonalityChangeClass

    def __post_init__(self) -> None:
        _token(self.name, "seed trait name")
        _ratio(self.weight, "seed trait weight")
        if not isinstance(self.change_class, PersonalityChangeClass):
            raise TypeError("change_class must be PersonalityChangeClass")


@dataclass(frozen=True, slots=True)
class CorePersonalityProfile:
    """A Core's declared baseline personality, not a central controller.

    Profiles describe how one Core starts.  They do not grant authority and
    they do not create a second identity for the same person.  ``continuity_key``
    is the stable personality identity across model, provider and process
    changes; display aliases are presentation metadata only.
    """

    continuity_key: str
    core_number: int
    full_name: str
    baseline_traits: tuple[PersonalityTraitSeed, ...]
    seriousness_context: Mapping[str, float]
    flaw: str
    aliases: tuple[str, ...] = ()
    forbidden_aliases: tuple[str, ...] = ()
    fabricated_biography_allowed: bool = False
    fabricated_memories_allowed: bool = False
    preset_hobbies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token(self.continuity_key, "continuity_key")
        if type(self.core_number) is not int or self.core_number < 2:
            raise ValueError("core_number must be an integer >= 2")
        _text(self.full_name, "full_name", maximum=160)
        if not isinstance(self.baseline_traits, tuple) or not self.baseline_traits:
            raise ValueError("baseline_traits must be a nonempty tuple")
        names = []
        for trait in self.baseline_traits:
            if not isinstance(trait, PersonalityTraitSeed):
                raise TypeError("baseline_traits must be PersonalityTraitSeed values")
            names.append(trait.name)
        if len(set(names)) != len(names):
            raise ValueError("baseline trait names must be distinct")
        if not isinstance(self.seriousness_context, Mapping):
            raise TypeError("seriousness_context must be a mapping")
        contexts = {
            _token(key, "seriousness context"): _ratio(value, "seriousness weight")
            for key, value in self.seriousness_context.items()
        }
        object.__setattr__(
            self,
            "seriousness_context",
            MappingProxyType(contexts),
        )
        _text(self.flaw, "flaw", maximum=160)
        for label, values in (
            ("aliases", self.aliases),
            ("forbidden_aliases", self.forbidden_aliases),
            ("preset_hobbies", self.preset_hobbies),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{label} must be a tuple")
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"{label} must contain nonempty text")
        if len({value.casefold() for value in self.aliases}) != len(self.aliases):
            raise ValueError("aliases must be distinct")
        if len({
            value.casefold() for value in self.forbidden_aliases
        }) != len(self.forbidden_aliases):
            raise ValueError("forbidden_aliases must be distinct")
        if set(value.casefold() for value in self.aliases) & set(
            value.casefold() for value in self.forbidden_aliases
        ):
            raise ValueError("a name cannot be both an alias and a forbidden alias")
        if type(self.fabricated_biography_allowed) is not bool:
            raise TypeError("fabricated_biography_allowed must be a bool")
        if type(self.fabricated_memories_allowed) is not bool:
            raise TypeError("fabricated_memories_allowed must be a bool")
        if self.fabricated_biography_allowed or self.fabricated_memories_allowed:
            raise ValueError(
                "fabricated biography or memories cannot become Core identity"
            )

    def alias_allowed(self, alias: str) -> bool:
        """Return whether ``alias`` may label this same continuous Core.

        A forbidden alias never becomes a second personality identity.  Only
        the declared name, its parts and explicit aliases are accepted; an
        arbitrary new name is not a second identity.  This check is about
        continuity of one person, not about whether a language model can
        pronounce a name.
        """
        target = alias.strip().casefold()
        if not target:
            return False
        allowed = {self.full_name.casefold()}
        allowed.update(part.casefold() for part in self.full_name.split())
        allowed.update(value.casefold() for value in self.aliases)
        forbidden = {value.casefold() for value in self.forbidden_aliases}
        return target in allowed and target not in forbidden

    def seed_state(self, core_id: UUID, *, now: datetime) -> PersonalityState:
        stamp = _utc(now, "now")
        traits = tuple(
            PersonalityTraitState(
                name=seed.name,
                weight=seed.weight,
                change_class=seed.change_class,
                updated_at=stamp,
            )
            for seed in self.baseline_traits
        )
        return PersonalityState(
            core_id=_uuid(core_id, "core_id"),
            core_number=self.core_number,
            full_name=self.full_name,
            continuity_key=self.continuity_key,
            traits=traits,
            updated_at=stamp,
        )


def __getattr__(name: str):
    """Legacy lazy re-exports; Core-owned baselines live in per-Core modules."""
    if name == "MACK_FULLER_PROFILE":
        from sofia.core.mack.personality import MACK_FULLER_PROFILE

        globals()[name] = MACK_FULLER_PROFILE
        return MACK_FULLER_PROFILE
    if name == "NOVA_ARDEN_PROFILE":
        from sofia.core.nova.personality import NOVA_ARDEN_PROFILE

        globals()[name] = NOVA_ARDEN_PROFILE
        return NOVA_ARDEN_PROFILE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True, slots=True)
class PersonalityChange:
    """A proposed, still-unapproved change to one trait."""

    trait: str
    weight: float
    change_class: PersonalityChangeClass
    reason: str
    evidence: tuple[PersonalityEvidence, ...] = ()
    reviewed_by: str | None = None
    temporary_until: datetime | None = None
    correction_of_revision: int | None = None

    def __post_init__(self) -> None:
        _token(self.trait, "trait")
        _ratio(self.weight, "weight")
        if not isinstance(self.change_class, PersonalityChangeClass):
            raise TypeError("change_class must be PersonalityChangeClass")
        _text(self.reason, "reason")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        for item in self.evidence:
            if not isinstance(item, PersonalityEvidence):
                raise TypeError("evidence entries must be PersonalityEvidence")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence identifiers must be distinct")
        if self.reviewed_by is not None:
            _text(self.reviewed_by, "reviewed_by", maximum=160)
        if self.temporary_until is not None:
            _utc(self.temporary_until, "temporary_until")
        if self.correction_of_revision is not None and (
            type(self.correction_of_revision) is not int
            or self.correction_of_revision < 1
        ):
            raise ValueError("correction_of_revision must be a positive integer")

    @property
    def verified_evidence(self) -> tuple[PersonalityEvidence, ...]:
        return tuple(item for item in self.evidence if item.verified)


@dataclass(frozen=True, slots=True)
class PersonalityChangeRecord:
    """An auditable personality revision.  History is append-only in intent."""

    core_id: UUID
    revision: int
    trait: str
    previous_weight: float
    new_weight: float
    change_class: PersonalityChangeClass
    reason: str
    evidence_ids: tuple[UUID, ...]
    evidence_states: tuple[EvidenceState, ...]
    authorized_by: str | None
    reviewed_by: str | None
    correction_of_revision: int | None
    temporary_until: datetime | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        _token(self.trait, "trait")
        _ratio(self.previous_weight, "previous_weight")
        _ratio(self.new_weight, "new_weight")
        if not isinstance(self.change_class, PersonalityChangeClass):
            raise TypeError("change_class must be PersonalityChangeClass")
        _text(self.reason, "reason")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not isinstance(self.evidence_states, tuple)
            or len(self.evidence_ids) != len(self.evidence_states)
        ):
            raise ValueError("evidence ids and states must align")
        for item in self.evidence_ids:
            _uuid(item, "evidence id")
        for item in self.evidence_states:
            if not isinstance(item, EvidenceState):
                raise TypeError("evidence_states must contain EvidenceState")
        if self.authorized_by is not None:
            _text(self.authorized_by, "authorized_by", maximum=160)
        if self.reviewed_by is not None:
            _text(self.reviewed_by, "reviewed_by", maximum=160)
        if self.correction_of_revision is not None and (
            type(self.correction_of_revision) is not int
            or self.correction_of_revision < 1
        ):
            raise ValueError("correction_of_revision must be a positive integer")
        if self.temporary_until is not None:
            _utc(self.temporary_until, "temporary_until")
        object.__setattr__(
            self,
            "recorded_at",
            _utc(self.recorded_at, "recorded_at"),
        )


@dataclass(frozen=True, slots=True)
class PersonalityChangeResult:
    """The new state plus the auditable revision that produced it."""

    state: PersonalityState
    record: PersonalityChangeRecord


_FLAW_REQUIRES_VERIFIED_CORRECTION = {
    "mack-fuller": "stubbornness",
    "nova-arden": "impulsiveness",
}


def _validate_evidence(
    change: PersonalityChange,
    *,
    require_review: bool,
) -> None:
    if not change.evidence:
        raise PersonalityEvidenceError(
            f"{change.change_class.value} personality changes require evidence"
        )
    if require_review and change.reviewed_by is None:
        raise PersonalityEvidenceError(
            "stable personality changes require an explicit reviewer"
        )


def apply_personality_change(
    state: PersonalityState,
    change: PersonalityChange,
    *,
    now: datetime,
    owner_authorization: OwnerAuthorization | None = None,
) -> PersonalityChangeResult:
    """Apply one governed personality change to exactly one Core.

    No authority is inferred from the change, the profile, or the caller.
    Protected changes require a separately injected owner authorization.
    """
    if not isinstance(state, PersonalityState):
        raise TypeError("state must be PersonalityState")
    if not isinstance(change, PersonalityChange):
        raise TypeError("change must be PersonalityChange")
    stamp = _utc(now, "now")
    if stamp < state.updated_at:
        raise ValueError("personality clock cannot move backward")

    current = state.trait(change.trait)
    effective_class = change.change_class
    if current is not None and current.change_class is not change.change_class:
        if (
            change.change_class is PersonalityChangeClass.TEMPORARY
            and current.change_class is not PersonalityChangeClass.PROTECTED
        ):
            # A temporary change may overlay an adaptive or stable trait
            # without retyping its enduring governance class.
            effective_class = current.change_class
        elif (
            current.change_class is PersonalityChangeClass.TEMPORARY
            and change.change_class in {
                PersonalityChangeClass.ADAPTIVE,
                PersonalityChangeClass.STABLE,
            }
        ):
            effective_class = change.change_class
        else:
            raise PersonalityContinuityError(
                "an existing trait cannot silently change governance class"
            )

    if change.change_class is PersonalityChangeClass.ADAPTIVE:
        _validate_evidence(change, require_review=False)
    elif change.change_class is PersonalityChangeClass.STABLE:
        _validate_evidence(change, require_review=True)
    elif change.change_class is PersonalityChangeClass.PROTECTED:
        if not isinstance(owner_authorization, OwnerAuthorization):
            raise PersonalityAuthorizationError(
                "protected personality changes require injected owner authorization"
            )
        if not owner_authorization.authorizes(change.trait, now=stamp):
            raise PersonalityAuthorizationError(
                "owner authorization does not cover this protected trait"
            )
    elif change.change_class is PersonalityChangeClass.TEMPORARY:
        if change.temporary_until is None:
            raise PersonalityEvidenceError(
                "temporary personality changes require an expiry horizon"
            )
        expires = _utc(change.temporary_until, "temporary_until")
        if expires <= stamp:
            raise ValueError("temporary_until must be in the future")
    else:  # pragma: no cover - exhaustively handled above
        raise ValueError("unknown personality change class")

    if change.correction_of_revision is not None and not change.verified_evidence:
        raise PersonalityEvidenceError(
            "recording a correction requires at least one verified evidence item"
        )

    previous_weight = 0.0 if current is None else current.weight
    flaw = _FLAW_REQUIRES_VERIFIED_CORRECTION.get(state.continuity_key)
    if (
        flaw == change.trait
        and change.weight < previous_weight
        and not change.verified_evidence
    ):
        raise PersonalityEvidenceError(
            "this Core's defining flaw can only be reduced by verified evidence"
        )

    authorized_by = (
        None
        if owner_authorization is None
        else owner_authorization.owner_principal_id
    )
    trait = PersonalityTraitState(
        name=change.trait,
        weight=change.weight,
        change_class=effective_class,
        evidence=change.evidence,
        updated_at=stamp,
        expires_at=(
            change.temporary_until
            if change.change_class is PersonalityChangeClass.TEMPORARY
            else None
        ),
    )
    traits = tuple(
        trait if existing.name == change.trait else existing
        for existing in state.traits
    )
    if current is None:
        traits = (*state.traits, trait)
    next_state = PersonalityState(
        core_id=state.core_id,
        core_number=state.core_number,
        full_name=state.full_name,
        continuity_key=state.continuity_key,
        traits=traits,
        revision=state.revision + 1,
        updated_at=stamp,
    )
    record = PersonalityChangeRecord(
        core_id=state.core_id,
        revision=next_state.revision,
        trait=change.trait,
        previous_weight=previous_weight,
        new_weight=change.weight,
        change_class=change.change_class,
        reason=change.reason,
        evidence_ids=tuple(item.evidence_id for item in change.evidence),
        evidence_states=tuple(item.state for item in change.evidence),
        authorized_by=authorized_by,
        reviewed_by=change.reviewed_by,
        correction_of_revision=change.correction_of_revision,
        temporary_until=(
            change.temporary_until
            if change.change_class is PersonalityChangeClass.TEMPORARY
            else None
        ),
        recorded_at=stamp,
    )
    return PersonalityChangeResult(state=next_state, record=record)


def correct_personality_flaw(
    state: PersonalityState,
    *,
    trait: str,
    weight: float,
    reason: str,
    verified_evidence: tuple[PersonalityEvidence, ...],
    now: datetime,
) -> PersonalityChangeResult:
    """Record a verified correction to the Core's defining flaw.

    This is the narrow path by which stubbornness (Mack) or impulsiveness
    (Nova) may be reduced.  The correction names the revision it corrects so
    the earlier trait state remains historically visible to callers that keep
    the returned audit records.
    """
    if not verified_evidence:
        raise PersonalityEvidenceError(
            "flaw corrections require verified contrary evidence"
        )
    if any(not item.verified for item in verified_evidence):
        raise PersonalityEvidenceError(
            "flaw corrections require verified contrary evidence"
        )
    current = state.trait(trait)
    if current is None:
        raise KeyError(trait)
    change = PersonalityChange(
        trait=trait,
        weight=weight,
        change_class=current.change_class,
        reason=reason,
        evidence=verified_evidence,
        correction_of_revision=state.revision,
    )
    return apply_personality_change(state, change, now=now)


def personality_is_same_continuous_identity(
    left: PersonalityState,
    right: PersonalityState,
) -> bool:
    """Return whether two states describe the same continuous Core identity."""
    if not isinstance(left, PersonalityState) or not isinstance(right, PersonalityState):
        raise TypeError("both states must be PersonalityState")
    return (
        left.core_id == right.core_id
        and left.core_number == right.core_number
        and left.continuity_key == right.continuity_key
    )
