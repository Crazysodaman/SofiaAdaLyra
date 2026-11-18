"""Versioned, authority-free universal Core capability contracts.

Every independently authenticated Aegis Core has the same *interface and
capability family possibilities*.  A contract records what is declared,
installed, available, currently authorized and effective for one Core; it never
grants authority, instantiates cognition, proves an asset exists, or claims a
renderer executed anything.

The five states are deliberately separate:

* ``declared``   - the Core's definition exposes the family interface.
* ``installed``  - the owning component is present in this installation.
* ``available``  - required optional assets/services can be reached.
* ``authorized`` - the existing authority boundary currently permits use.
* ``effective``  - an authenticated caller may act now (all four above hold).

``effective`` is never inferred from the mere presence of a capability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping
from uuid import UUID

CORE_CAPABILITIES_SCHEMA = "aegis.core.capabilities.v1"
CAPABILITY_RECEIPT_SCHEMA = "aegis.core.capability_receipt.v1"
MAX_CAPABILITY_FAMILIES = 64
_MAX_PAYLOAD_BYTES = 32_768
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class CapabilityError(ValueError):
    """A capability declaration or receipt is malformed."""


class CapabilityFamily(str, Enum):
    """Reviewed capability families; all are available to every Core."""

    CORE_REQUIREMENTS = "core_requirements"
    COGNITION = "cognition"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    EMOTION = "emotion"
    ROMANCE = "romance"
    SEXUALITY = "sexuality"
    GESTURE = "gesture"
    VOICE = "voice"
    AVATAR = "avatar"
    WARDROBE = "wardrobe"
    ARMOR = "armor"
    SOCIAL = "social"
    GOVERNANCE = "governance"
    GOALS = "goals"
    DEVELOPER_TOOLS = "developer_tools"


UNIVERSAL_CAPABILITY_FAMILIES: tuple[CapabilityFamily, ...] = tuple(CapabilityFamily)


class CapabilityOutcome(str, Enum):
    """Honest outcome vocabulary for a represented capability effect."""

    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    DECLINED = "declined"
    QUEUED = "queued"
    RENDERED = "rendered"
    CANCELED = "canceled"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RendererCapability(str, Enum):
    """Optional renderer surfaces; absence is normal and must stay absent-safe."""

    TEXT = "text"
    TWO_D = "2d"
    THREE_D = "3d"
    VTUBE = "vtube"
    HAPTIC = "haptic"


class BodyCapability(str, Enum):
    """Body/rig predicates used to gate anatomy-specific represented motion.

    A body capability is declared anatomy, never proof of a compatible mesh,
    asset, collision rig or rendered playback.
    """

    HUMAN_FORM = "human_form"
    FOX_EARS = "fox_ears"
    FOX_TAIL = "fox_tail"
    WINGS = "wings"


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise CapabilityError(f"{label} must be a nonzero UUID")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise CapabilityError(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise CapabilityError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CapabilityError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise CapabilityError(f"{label} must be boolean")
    return value


@dataclass(frozen=True, slots=True)
class BodyCapabilityProfile:
    """Declared body/rig features for one Core; never a renderer/asset claim."""

    features: frozenset[BodyCapability]
    rig_id: str = "human"

    def __post_init__(self) -> None:
        if not isinstance(self.features, frozenset) or not self.features:
            raise CapabilityError("body features must be a nonempty frozenset")
        if any(not isinstance(item, BodyCapability) for item in self.features):
            raise CapabilityError("body features must be BodyCapability values")
        _identifier(self.rig_id, "rig_id")

    @classmethod
    def human_only(cls, rig_id: str = "human") -> "BodyCapabilityProfile":
        return cls(frozenset({BodyCapability.HUMAN_FORM}), rig_id)

    @classmethod
    def sofia_fox(cls, rig_id: str = "human-fox") -> "BodyCapabilityProfile":
        return cls(
            frozenset({
                BodyCapability.HUMAN_FORM,
                BodyCapability.FOX_EARS,
                BodyCapability.FOX_TAIL,
            }),
            rig_id,
        )

    def supports(self, feature: BodyCapability) -> bool:
        if not isinstance(feature, BodyCapability):
            raise CapabilityError("feature must be a BodyCapability")
        return feature in self.features

    def missing(
        self, required: Iterable[BodyCapability],
    ) -> tuple[BodyCapability, ...]:
        required_items = tuple(required)
        if any(not isinstance(item, BodyCapability) for item in required_items):
            raise CapabilityError("required body capabilities must be typed")
        return tuple(item for item in required_items if item not in self.features)

    def supports_all(self, required: Iterable[BodyCapability]) -> bool:
        return not self.missing(required)


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Five separately evidenced capability states for one family."""

    declared: bool = True
    installed: bool = False
    available: bool = False
    authorized: bool = False
    effective: bool = False

    def __post_init__(self) -> None:
        for name in ("declared", "installed", "available", "authorized", "effective"):
            _bool(getattr(self, name), name)
        if self.effective and not all(
            (self.declared, self.installed, self.available, self.authorized)
        ):
            raise CapabilityError(
                "effective requires declared, installed, available and authorized"
            )

    @classmethod
    def declared_only(cls) -> "CapabilityState":
        return cls(declared=True)

    @classmethod
    def unavailable(cls) -> "CapabilityState":
        return cls(declared=True, installed=False)

    def can_attempt(self) -> bool:
        """Return whether an authenticated caller may attempt the family now."""
        return self.effective

    def to_payload(self) -> dict[str, bool]:
        return {
            "declared": self.declared,
            "installed": self.installed,
            "available": self.available,
            "authorized": self.authorized,
            "effective": self.effective,
        }

    @classmethod
    def from_payload(cls, value: object) -> "CapabilityState":
        fields = frozenset({"declared", "installed", "available", "authorized", "effective"})
        if not isinstance(value, Mapping) or set(value) != fields:
            raise CapabilityError("capability state fields differ")
        return cls(**{name: value[name] for name in fields})


@dataclass(frozen=True, slots=True)
class CoreCapabilityContract:
    """Inert per-Core capability declaration and effective-state projection."""

    core_id: UUID
    core_number: int
    definition_digest: str
    states: Mapping[CapabilityFamily, CapabilityState]
    renderers: tuple[RendererCapability, ...] = (RendererCapability.TEXT,)
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if type(self.core_number) is not int or self.core_number < 1:
            raise CapabilityError("core_number must be a positive integer")
        _digest(self.definition_digest, "definition_digest")
        if not isinstance(self.states, Mapping):
            raise CapabilityError("states must be a mapping")
        if set(self.states) != set(CapabilityFamily):
            raise CapabilityError("every universal capability family must be declared")
        for family, state in self.states.items():
            if not isinstance(family, CapabilityFamily):
                raise CapabilityError("capability family keys must be typed")
            if not isinstance(state, CapabilityState):
                raise CapabilityError("capability values must be CapabilityState")
            if not state.declared:
                raise CapabilityError("universal families must be declared for every Core")
        if not isinstance(self.renderers, tuple):
            raise CapabilityError("renderers must be a tuple")
        if not self.renderers or len(set(self.renderers)) != len(self.renderers):
            raise CapabilityError("renderers must be unique and nonempty")
        if any(not isinstance(item, RendererCapability) for item in self.renderers):
            raise CapabilityError("renderers must be RendererCapability values")
        if RendererCapability.TEXT not in self.renderers:
            raise CapabilityError("text operation is always available")
        if type(self.revision) is not int or self.revision < 1:
            raise CapabilityError("revision must be a positive integer")

    @classmethod
    def universal(
        cls,
        *,
        core_id: UUID,
        core_number: int,
        definition_digest: str,
        renderers: tuple[RendererCapability, ...] = (RendererCapability.TEXT,),
        revision: int = 1,
    ) -> "CoreCapabilityContract":
        """Declare equal potential without claiming installed assets/authority."""
        return cls(
            core_id=core_id,
            core_number=core_number,
            definition_digest=definition_digest,
            states={family: CapabilityState.declared_only() for family in CapabilityFamily},
            renderers=renderers,
            revision=revision,
        )

    def state(self, family: CapabilityFamily) -> CapabilityState:
        if not isinstance(family, CapabilityFamily):
            raise CapabilityError("family must be a CapabilityFamily")
        return self.states[family]

    def supports(self, family: CapabilityFamily) -> bool:
        return self.state(family).declared

    def is_effective(self, family: CapabilityFamily) -> bool:
        return self.state(family).effective

    def renderer_available(self, renderer: RendererCapability) -> bool:
        """Return whether the optional renderer surface is declared present."""
        if not isinstance(renderer, RendererCapability):
            raise CapabilityError("renderer must be a RendererCapability")
        return renderer in self.renderers

    def missing_renderers(
        self, required: Iterable[RendererCapability],
    ) -> tuple[RendererCapability, ...]:
        required_items = tuple(required)
        if any(not isinstance(item, RendererCapability) for item in required_items):
            raise CapabilityError("required renderers must be typed")
        return tuple(item for item in required_items if item not in self.renderers)

    def body_supports(
        self,
        body: BodyCapabilityProfile,
        required: Iterable[BodyCapability],
    ) -> bool:
        """Declared gesture anatomy interface plus a compatible body/rig."""
        if not isinstance(body, BodyCapabilityProfile):
            raise CapabilityError("body must be a BodyCapabilityProfile")
        return self.supports(CapabilityFamily.GESTURE) and body.supports_all(required)

    def with_state(
        self, family: CapabilityFamily, state: CapabilityState
    ) -> "CoreCapabilityContract":
        if not isinstance(family, CapabilityFamily) or not isinstance(state, CapabilityState):
            raise CapabilityError("typed family and state are required")
        if not state.declared:
            raise CapabilityError("universal families cannot be undeclared")
        updated = dict(self.states)
        updated[family] = state
        return CoreCapabilityContract(
            core_id=self.core_id,
            core_number=self.core_number,
            definition_digest=self.definition_digest,
            states=updated,
            renderers=self.renderers,
            revision=self.revision + 1,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": CORE_CAPABILITIES_SCHEMA,
            "core_id": str(self.core_id),
            "core_number": self.core_number,
            "definition_digest": self.definition_digest,
            "states": {
                family.value: self.states[family].to_payload()
                for family in CapabilityFamily
            },
            "renderers": [renderer.value for renderer in self.renderers],
            "revision": self.revision,
        }

    @classmethod
    def from_payload(cls, value: object) -> "CoreCapabilityContract":
        fields = frozenset({
            "schema", "core_id", "core_number", "definition_digest",
            "states", "renderers", "revision",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise CapabilityError("capability contract fields differ")
        if value["schema"] != CORE_CAPABILITIES_SCHEMA:
            raise CapabilityError("unsupported capability contract schema")
        raw_states = value["states"]
        if not isinstance(raw_states, Mapping):
            raise CapabilityError("states must be a mapping")
        try:
            states = {
                CapabilityFamily(name): CapabilityState.from_payload(state)
                for name, state in raw_states.items()
            }
            renderers = tuple(RendererCapability(item) for item in value["renderers"])
            return cls(
                core_id=_uuid(UUID(str(value["core_id"])), "core_id"),
                core_number=value["core_number"],
                definition_digest=value["definition_digest"],
                states=states,
                renderers=renderers,
                revision=value["revision"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, CapabilityError):
                raise
            raise CapabilityError("capability contract payload is invalid") from exc

    @property
    def canonical_bytes(self) -> bytes:
        raw = json.dumps(
            self.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        if len(raw) > _MAX_PAYLOAD_BYTES:
            raise CapabilityError("capability contract exceeds its size bound")
        return raw

    @property
    def digest(self) -> str:
        return sha256(b"aegis.core.capabilities.v1\x00" + self.canonical_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class CapabilityReceipt:
    """Explicit evidence that an effect was unavailable, denied or completed."""

    receipt_id: UUID
    core_id: UUID
    family: CapabilityFamily
    outcome: CapabilityOutcome
    reason: str
    evidence_ref: str
    occurred_at: datetime
    renderer: RendererCapability | None = None
    asset_ref: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.receipt_id, "receipt_id")
        _uuid(self.core_id, "core_id")
        if not isinstance(self.family, CapabilityFamily):
            raise CapabilityError("family must be CapabilityFamily")
        if not isinstance(self.outcome, CapabilityOutcome):
            raise CapabilityError("outcome must be CapabilityOutcome")
        _identifier(self.evidence_ref, "evidence_ref")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 1024:
            raise CapabilityError("reason must be bounded nonempty text")
        _utc(self.occurred_at, "occurred_at")
        if self.renderer is not None and not isinstance(self.renderer, RendererCapability):
            raise CapabilityError("renderer must be RendererCapability")
        if self.asset_ref is not None:
            _identifier(self.asset_ref, "asset_ref")
        if self.outcome in {CapabilityOutcome.RENDERED, CapabilityOutcome.QUEUED} and self.renderer is None:
            raise CapabilityError("queued/rendered receipts require a renderer")
        if self.outcome is CapabilityOutcome.RENDERED and self.asset_ref is None:
            raise CapabilityError("rendered receipts require an asset reference")

    @property
    def claims_rendered(self) -> bool:
        return self.outcome is CapabilityOutcome.RENDERED

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": CAPABILITY_RECEIPT_SCHEMA,
            "receipt_id": str(self.receipt_id),
            "core_id": str(self.core_id),
            "family": self.family.value,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "evidence_ref": self.evidence_ref,
            "occurred_at": self.occurred_at.isoformat(),
            "renderer": None if self.renderer is None else self.renderer.value,
            "asset_ref": self.asset_ref,
        }

    @classmethod
    def from_payload(cls, value: object) -> "CapabilityReceipt":
        fields = frozenset({
            "schema", "receipt_id", "core_id", "family", "outcome", "reason",
            "evidence_ref", "occurred_at", "renderer", "asset_ref",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise CapabilityError("capability receipt fields differ")
        if value["schema"] != CAPABILITY_RECEIPT_SCHEMA:
            raise CapabilityError("unsupported capability receipt schema")
        renderer = value["renderer"]
        return cls(
            receipt_id=_uuid(UUID(str(value["receipt_id"])), "receipt_id"),
            core_id=_uuid(UUID(str(value["core_id"])), "core_id"),
            family=CapabilityFamily(value["family"]),
            outcome=CapabilityOutcome(value["outcome"]),
            reason=value["reason"],
            evidence_ref=value["evidence_ref"],
            occurred_at=datetime.fromisoformat(str(value["occurred_at"])),
            renderer=None if renderer is None else RendererCapability(renderer),
            asset_ref=value["asset_ref"],
        )


def _source_core_id(source: object) -> UUID | None:
    candidate = getattr(source, "core_id", None)
    if isinstance(candidate, UUID):
        return candidate
    identity = getattr(source, "identity", None)
    if identity is not None:
        for attribute in ("identity_id", "core_id"):
            candidate = getattr(identity, attribute, None)
            if isinstance(candidate, UUID):
                return candidate
    descriptor = getattr(source, "descriptor", None)
    if descriptor is not None:
        candidate = getattr(descriptor, "core_id", None)
        if isinstance(candidate, UUID):
            return candidate
    return None


def _source_core_number(source: object) -> int | None:
    for owner in (source, getattr(source, "spec", None), getattr(source, "descriptor", None)):
        if owner is None:
            continue
        candidate = getattr(owner, "core_number", None)
        if type(candidate) is int:
            return candidate
    return None


def definition_digest_for(source: object) -> str:
    """Derive a stable definition digest without allocating or authenticating."""
    candidate = getattr(source, "digest", None)
    if isinstance(candidate, str) and _DIGEST.fullmatch(candidate) is not None:
        return candidate
    constitution = getattr(source, "constitution_sha256", None)
    personality = getattr(source, "personality_sha256", None)
    if (
        isinstance(constitution, str)
        and _DIGEST.fullmatch(constitution) is not None
        and isinstance(personality, str)
        and _DIGEST.fullmatch(personality) is not None
    ):
        return sha256(
            b"aegis.core.profile.v1\x00"
            + constitution.encode("ascii")
            + b"\x00"
            + personality.encode("ascii")
        ).hexdigest()
    raise CapabilityError(
        "source must expose a CoreDefinition digest or profile asset digests"
    )


def derive_core_capability_contract(
    source: object,
    *,
    core_id: UUID | None = None,
    core_number: int | None = None,
    definition_digest: str | None = None,
    renderers: tuple[RendererCapability, ...] = (RendererCapability.TEXT,),
    revision: int = 1,
) -> CoreCapabilityContract:
    """Derive equal universal capability declarations for an existing Core.

    The caller-supplied ``core_id`` is authoritative; a conflicting identity in
    ``source`` is rejected instead of being cloned or silently replaced. Every
    family is declared, while installed/available/authorized/effective remain
    false: this helper never grants authority or claims an optional renderer.
    """
    source_id = _source_core_id(source)
    if core_id is None:
        core_id = source_id
    elif source_id is not None and source_id != core_id:
        raise CapabilityError("supplied core_id differs from the source identity")
    if core_id is None:
        raise CapabilityError("an externally supplied core_id is required")
    _uuid(core_id, "core_id")

    number = core_number if core_number is not None else _source_core_number(source)
    if number is None:
        raise CapabilityError("a core_number is required")
    if type(number) is not int or number < 1:
        raise CapabilityError("core_number must be a positive integer")

    digest = (
        definition_digest
        if definition_digest is not None
        else definition_digest_for(source)
    )
    _digest(digest, "definition_digest")

    return CoreCapabilityContract.universal(
        core_id=core_id,
        core_number=number,
        definition_digest=digest,
        renderers=renderers,
        revision=revision,
    )


def unavailable_receipt(
    *,
    receipt_id: UUID,
    core_id: UUID,
    family: CapabilityFamily,
    reason: str,
    evidence_ref: str,
    occurred_at: datetime,
    renderer: RendererCapability | None = None,
) -> CapabilityReceipt:
    """Return an honest UNAVAILABLE receipt without fabricating an effect."""
    return CapabilityReceipt(
        receipt_id=receipt_id,
        core_id=core_id,
        family=family,
        outcome=CapabilityOutcome.UNAVAILABLE,
        reason=reason,
        evidence_ref=evidence_ref,
        occurred_at=occurred_at,
        renderer=renderer,
    )


__all__ = [
    "CAPABILITY_RECEIPT_SCHEMA",
    "CORE_CAPABILITIES_SCHEMA",
    "MAX_CAPABILITY_FAMILIES",
    "BodyCapability",
    "BodyCapabilityProfile",
    "CapabilityError",
    "CapabilityFamily",
    "CapabilityOutcome",
    "CapabilityReceipt",
    "CapabilityState",
    "CoreCapabilityContract",
    "RendererCapability",
    "UNIVERSAL_CAPABILITY_FAMILIES",
    "definition_digest_for",
    "derive_core_capability_contract",
    "unavailable_receipt",
]
