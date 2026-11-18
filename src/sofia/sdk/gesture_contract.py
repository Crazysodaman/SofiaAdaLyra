"""Versioned, authority-free universal gesture and intimate-semantics contracts.

These contracts describe *reviewed represented semantics*.  They never grant
consent or authority, never infer willingness or arousal, never contact another
Core, and never claim that a renderer played a motion back.

The only playback evidence is an authenticated renderer event with an exact
event reference, renderer capability, asset reference, generation and a STOP
state.  Typed or spoken stage directions are descriptions, not playback proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4

from sofia.sdk.core_capabilities import (
    BodyCapability,
    BodyCapabilityProfile,
    CapabilityError,
    CapabilityOutcome,
    RendererCapability,
)

GESTURE_CONTRACT_SCHEMA = "aegis.avatar.gesture.v1"
GESTURE_RECEIPT_SCHEMA = "aegis.avatar.gesture_receipt.v1"
ADULT_SCENE_SCHEMA = "aegis.avatar.adult_scene.v1"
ADULT_REVIEWED_POLICY = "aegis.adult.reviewed.v1"
_MAX_TEXT = 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PHASES = frozenset({"begin", "update", "end", "cancel"})
_TERMINAL = frozenset({
    CapabilityOutcome.RENDERED,
    CapabilityOutcome.DECLINED,
    CapabilityOutcome.CANCELED,
    CapabilityOutcome.FAILED,
    CapabilityOutcome.UNAVAILABLE,
})
_ALLOWED_TRANSITIONS: Mapping[CapabilityOutcome, frozenset[CapabilityOutcome]] = {
    CapabilityOutcome.PROPOSED: frozenset({
        CapabilityOutcome.AUTHORIZED,
        CapabilityOutcome.DECLINED,
        CapabilityOutcome.CANCELED,
        CapabilityOutcome.FAILED,
        CapabilityOutcome.UNAVAILABLE,
    }),
    CapabilityOutcome.AUTHORIZED: frozenset({
        CapabilityOutcome.QUEUED,
        CapabilityOutcome.DECLINED,
        CapabilityOutcome.CANCELED,
        CapabilityOutcome.FAILED,
        CapabilityOutcome.UNAVAILABLE,
    }),
    CapabilityOutcome.QUEUED: frozenset({
        CapabilityOutcome.RENDERED,
        CapabilityOutcome.CANCELED,
        CapabilityOutcome.FAILED,
        CapabilityOutcome.UNAVAILABLE,
    }),
}


class GestureError(ValueError):
    """A gesture definition, compatibility request or receipt is malformed."""


class GestureStateError(GestureError):
    """A gesture outcome transition is not allowed."""


class GestureClass(str, Enum):
    UNIVERSAL = "universal"
    ANATOMY_SPECIFIC = "anatomy_specific"
    PERSONAL = "personal"


class GesturePrivacy(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ADULT_PRIVATE = "adult_private"


class GesturePartyKind(str, Enum):
    CORE = "core"
    USER = "user"
    EXTERNAL = "external"


class GestureEvidence(str, Enum):
    DESCRIPTION = "description"
    RENDERER = "renderer"
    PLAYBACK = "playback"


class GestureCompatibilityStatus(str, Enum):
    ACCEPTED = "accepted"
    ANATOMY_MISMATCH = "anatomy_mismatch"
    RENDERER_UNAVAILABLE = "renderer_unavailable"
    PRIVACY_UNAVAILABLE = "privacy_unavailable"


class AdultEligibility(str, Enum):
    ADULT = "adult"
    MINOR = "minor"
    UNKNOWN = "unknown"


class SceneAudience(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    UNKNOWN = "unknown"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GestureError(f"{label} must be a bounded identifier")
    return value


def _text(value: object, label: str, *, maximum: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GestureError(f"{label} must be bounded nonempty text")
    if any(ord(character) < 0x20 for character in value):
        raise GestureError(f"{label} cannot contain control characters")
    return value


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise GestureError(f"{label} must be a nonzero UUID")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GestureError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GestureError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise GestureError(f"{label} must be boolean")
    return value


def _ratio(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise GestureError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise GestureError(f"{label} must be in [0, 1]")
    return number


def _typed_tuple(value: object, item_type: type, label: str) -> tuple:
    if not isinstance(value, tuple) or not value:
        raise GestureError(f"{label} must be a nonempty tuple")
    if any(not isinstance(item, item_type) for item in value):
        raise GestureError(f"{label} entries must be typed")
    if len(set(value)) != len(value):
        raise GestureError(f"{label} entries must be unique")
    return value


@dataclass(frozen=True, slots=True)
class GestureParty:
    """Explicit actor or target; never inferred from display text."""

    kind: GesturePartyKind
    reference: str
    core_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, GesturePartyKind):
            raise GestureError("kind must be a GesturePartyKind")
        _identifier(self.reference, "party reference")
        if self.kind is GesturePartyKind.CORE:
            if self.core_id is None:
                raise GestureError("core parties require an explicit Core UUID")
            _uuid(self.core_id, "core_id")
        elif self.core_id is not None:
            raise GestureError("only core parties carry a Core UUID")

    @classmethod
    def core(cls, core_id: UUID) -> "GestureParty":
        _uuid(core_id, "core_id")
        return cls(GesturePartyKind.CORE, str(core_id), core_id)

    @classmethod
    def user(cls) -> "GestureParty":
        return cls(GesturePartyKind.USER, "user")

    @classmethod
    def any_core(cls) -> "GestureParty":
        return cls(GesturePartyKind.EXTERNAL, "any-core")

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "reference": self.reference,
            "core_id": None if self.core_id is None else str(self.core_id),
        }

    @classmethod
    def from_payload(cls, value: object) -> "GestureParty":
        fields = frozenset({"kind", "reference", "core_id"})
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureError("gesture party fields differ")
        try:
            raw_core = value["core_id"]
            return cls(
                kind=GesturePartyKind(value["kind"]),
                reference=value["reference"],
                core_id=None if raw_core is None else UUID(str(raw_core)),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, GestureError):
                raise
            raise GestureError("gesture party is invalid") from exc


@dataclass(frozen=True, slots=True)
class GestureDefinition:
    """Canonical versioned gesture/action/expression semantics."""

    gesture_id: str
    version: int
    gesture_class: GestureClass
    actor: GestureParty
    target: GestureParty
    required_body: tuple[BodyCapability, ...] = (BodyCapability.HUMAN_FORM,)
    renderer_capabilities: tuple[RendererCapability, ...] = (RendererCapability.TEXT,)
    phases: tuple[str, ...] = ("begin", "update", "end", "cancel")
    privacy: GesturePrivacy = GesturePrivacy.PUBLIC
    provenance: str = "aegis.gesture.v1"
    aliases: tuple[str, ...] = ()
    semantic_parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier(self.gesture_id, "gesture_id")
        if type(self.version) is not int or self.version < 1:
            raise GestureError("version must be a positive integer")
        if not isinstance(self.gesture_class, GestureClass):
            raise GestureError("gesture_class must be a GestureClass")
        if not isinstance(self.actor, GestureParty) or not isinstance(self.target, GestureParty):
            raise GestureError("actor and target must be GestureParty values")
        if not isinstance(self.required_body, tuple) or any(
            not isinstance(item, BodyCapability) for item in self.required_body
        ):
            raise GestureError("required_body must contain typed body capabilities")
        if len(set(self.required_body)) != len(self.required_body):
            raise GestureError("required_body entries must be unique")
        if not isinstance(self.renderer_capabilities, tuple) or not self.renderer_capabilities:
            raise GestureError("renderer_capabilities must be a nonempty tuple")
        if any(
            not isinstance(item, RendererCapability)
            for item in self.renderer_capabilities
        ):
            raise GestureError("renderer capabilities must be typed")
        if len(set(self.renderer_capabilities)) != len(self.renderer_capabilities):
            raise GestureError("renderer capabilities must be unique")
        if not isinstance(self.phases, tuple) or not self.phases:
            raise GestureError("phases must be a nonempty tuple")
        if any(not isinstance(phase, str) or phase not in _PHASES for phase in self.phases):
            raise GestureError("phases must use the reviewed phase vocabulary")
        if len(set(self.phases)) != len(self.phases):
            raise GestureError("phases must be unique")
        if not isinstance(self.privacy, GesturePrivacy):
            raise GestureError("privacy must be a GesturePrivacy")
        _identifier(self.provenance, "provenance")
        if not isinstance(self.aliases, tuple):
            raise GestureError("aliases must be a tuple")
        for alias in self.aliases:
            _text(alias, "alias", maximum=120)
        if len(set(self.aliases)) != len(self.aliases):
            raise GestureError("aliases must be unique")
        if self.gesture_id in self.aliases:
            raise GestureError("the canonical id cannot also be an alias")
        if not isinstance(self.semantic_parameters, Mapping):
            raise GestureError("semantic_parameters must be a mapping")
        parameters: dict[str, str] = {}
        for key, value in self.semantic_parameters.items():
            _identifier(key, "semantic parameter name")
            _text(value, "semantic parameter value", maximum=256)
            parameters[key] = value
        object.__setattr__(self, "semantic_parameters", MappingProxyType(parameters))
        if self.gesture_class is GestureClass.UNIVERSAL:
            anatomy_only = {
                BodyCapability.FOX_EARS,
                BodyCapability.FOX_TAIL,
                BodyCapability.WINGS,
            }
            if anatomy_only.intersection(self.required_body):
                raise GestureError(
                    "universal gestures cannot require anatomy-specific body features"
                )

    @property
    def canonical_ref(self) -> str:
        return f"{self.gesture_id}@{self.version}"

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": GESTURE_CONTRACT_SCHEMA,
            "gesture_id": self.gesture_id,
            "version": self.version,
            "gesture_class": self.gesture_class.value,
            "actor": self.actor.to_payload(),
            "target": self.target.to_payload(),
            "required_body": [item.value for item in self.required_body],
            "renderer_capabilities": [
                item.value for item in self.renderer_capabilities
            ],
            "phases": list(self.phases),
            "privacy": self.privacy.value,
            "provenance": self.provenance,
            "aliases": list(self.aliases),
            "semantic_parameters": dict(self.semantic_parameters),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(
            b"aegis.avatar.gesture.v1\x00" + self.canonical_bytes
        ).hexdigest()

    @classmethod
    def from_payload(cls, value: object) -> "GestureDefinition":
        fields = frozenset({
            "schema", "gesture_id", "version", "gesture_class", "actor",
            "target", "required_body", "renderer_capabilities", "phases",
            "privacy", "provenance", "aliases", "semantic_parameters",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureError("gesture definition fields differ")
        if value["schema"] != GESTURE_CONTRACT_SCHEMA:
            raise GestureError("unsupported gesture definition schema")
        try:
            parameters = value["semantic_parameters"]
            if not isinstance(parameters, Mapping):
                raise GestureError("semantic_parameters must be a mapping")
            return cls(
                gesture_id=value["gesture_id"],
                version=value["version"],
                gesture_class=GestureClass(value["gesture_class"]),
                actor=GestureParty.from_payload(value["actor"]),
                target=GestureParty.from_payload(value["target"]),
                required_body=tuple(
                    BodyCapability(item) for item in value["required_body"]
                ),
                renderer_capabilities=tuple(
                    RendererCapability(item)
                    for item in value["renderer_capabilities"]
                ),
                phases=tuple(value["phases"]),
                privacy=GesturePrivacy(value["privacy"]),
                provenance=value["provenance"],
                aliases=tuple(value["aliases"]),
                semantic_parameters=dict(parameters),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, GestureError):
                raise
            raise GestureError("gesture definition is invalid") from exc


@dataclass(frozen=True, slots=True)
class GestureCompatibility:
    """Resolution result that never silently remaps a requested gesture."""

    status: GestureCompatibilityStatus
    reason: str
    definition: GestureDefinition
    missing_body: tuple[BodyCapability, ...] = ()
    missing_renderers: tuple[RendererCapability, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status is GestureCompatibilityStatus.ACCEPTED


def resolve_gesture_compatibility(
    definition: GestureDefinition,
    *,
    body: BodyCapabilityProfile,
    renderers: tuple[RendererCapability, ...],
    audience: GesturePrivacy | None = None,
) -> GestureCompatibility:
    """Resolve body, renderer and audience requirements without remapping."""
    if not isinstance(definition, GestureDefinition):
        raise GestureError("definition must be a GestureDefinition")
    if not isinstance(body, BodyCapabilityProfile):
        raise GestureError("body must be a BodyCapabilityProfile")
    if not isinstance(renderers, tuple) or any(
        not isinstance(item, RendererCapability) for item in renderers
    ):
        raise GestureError("renderers must be a tuple of RendererCapability")
    if audience is not None and not isinstance(audience, GesturePrivacy):
        raise GestureError("audience must be a GesturePrivacy")

    missing_body = body.missing(definition.required_body)
    if missing_body:
        return GestureCompatibility(
            GestureCompatibilityStatus.ANATOMY_MISMATCH,
            "anatomy-incompatible: missing declared body/rig capability",
            definition,
            missing_body=missing_body,
        )

    missing_renderers = tuple(
        item for item in definition.renderer_capabilities if item not in renderers
    )
    if missing_renderers:
        return GestureCompatibility(
            GestureCompatibilityStatus.RENDERER_UNAVAILABLE,
            "renderer-unavailable: no declared compatible renderer surface",
            definition,
            missing_renderers=missing_renderers,
        )

    if definition.privacy is GesturePrivacy.ADULT_PRIVATE:
        if audience is not GesturePrivacy.ADULT_PRIVATE:
            return GestureCompatibility(
                GestureCompatibilityStatus.PRIVACY_UNAVAILABLE,
                "privacy-unavailable: adult-private audience is required",
                definition,
            )
    elif definition.privacy is GesturePrivacy.PRIVATE:
        if audience is GesturePrivacy.PUBLIC:
            return GestureCompatibility(
                GestureCompatibilityStatus.PRIVACY_UNAVAILABLE,
                "privacy-unavailable: private audience is required",
                definition,
            )

    return GestureCompatibility(
        GestureCompatibilityStatus.ACCEPTED,
        "compatible: declared body, renderer and audience requirements hold",
        definition,
    )


@dataclass(frozen=True, slots=True)
class GesturePlaybackReceipt:
    """Honest gesture outcome evidence; descriptions are never playback."""

    receipt_id: UUID
    core_id: UUID
    gesture_id: str
    gesture_version: int
    outcome: CapabilityOutcome
    event_ref: str
    renderer: RendererCapability | None
    asset_ref: str | None
    generation: int
    stopped: bool
    authenticated: bool
    evidence: GestureEvidence
    reason: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.receipt_id, "receipt_id")
        _uuid(self.core_id, "core_id")
        _identifier(self.gesture_id, "gesture_id")
        if type(self.gesture_version) is not int or self.gesture_version < 1:
            raise GestureError("gesture_version must be a positive integer")
        if not isinstance(self.outcome, CapabilityOutcome):
            raise GestureError("outcome must be CapabilityOutcome")
        _identifier(self.event_ref, "event_ref")
        if self.renderer is not None and not isinstance(
            self.renderer, RendererCapability
        ):
            raise GestureError("renderer must be RendererCapability")
        if self.asset_ref is not None:
            _identifier(self.asset_ref, "asset_ref")
        if type(self.generation) is not int or self.generation < 1:
            raise GestureError("generation must be a positive integer")
        _bool(self.stopped, "stopped")
        _bool(self.authenticated, "authenticated")
        if not isinstance(self.evidence, GestureEvidence):
            raise GestureError("evidence must be GestureEvidence")
        _text(self.reason, "reason")
        _utc(self.occurred_at, "occurred_at")

        if self.outcome in {CapabilityOutcome.QUEUED, CapabilityOutcome.RENDERED}:
            if self.renderer is None:
                raise GestureError("queued/rendered receipts require a renderer")
            if not self.authenticated:
                raise GestureError("queued/rendered receipts require authentication")
            if self.evidence is GestureEvidence.DESCRIPTION:
                raise GestureError("descriptions cannot prove renderer playback")
            if self.stopped:
                raise GestureError("a stopped gesture cannot report success")
        if self.outcome is CapabilityOutcome.RENDERED:
            if self.asset_ref is None:
                raise GestureError("rendered receipts require an asset reference")
            if self.evidence is not GestureEvidence.PLAYBACK:
                raise GestureError("rendered receipts require playback evidence")
        if self.outcome is CapabilityOutcome.CANCELED and not self.stopped:
            raise GestureError("canceled receipts require elapsed STOP state")
        if self.stopped and self.outcome not in {
            CapabilityOutcome.CANCELED,
            CapabilityOutcome.DECLINED,
            CapabilityOutcome.UNAVAILABLE,
            CapabilityOutcome.FAILED,
        }:
            raise GestureError("STOP forbids late success receipts")

    @property
    def claims_playback(self) -> bool:
        return self.outcome is CapabilityOutcome.RENDERED

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": GESTURE_RECEIPT_SCHEMA,
            "receipt_id": str(self.receipt_id),
            "core_id": str(self.core_id),
            "gesture_id": self.gesture_id,
            "gesture_version": self.gesture_version,
            "outcome": self.outcome.value,
            "event_ref": self.event_ref,
            "renderer": None if self.renderer is None else self.renderer.value,
            "asset_ref": self.asset_ref,
            "generation": self.generation,
            "stopped": self.stopped,
            "authenticated": self.authenticated,
            "evidence": self.evidence.value,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class GestureExecution:
    """Outcome state machine: PROPOSED -> AUTHORIZED/DECLINED -> ... ."""

    core_id: UUID
    definition: GestureDefinition
    event_ref: str
    generation: int
    occurred_at: datetime
    receipt_id: UUID
    outcome: CapabilityOutcome = CapabilityOutcome.PROPOSED
    renderer: RendererCapability | None = None
    asset_ref: str | None = None
    stopped: bool = False
    authenticated: bool = False
    evidence: GestureEvidence = GestureEvidence.DESCRIPTION
    reason: str = "Proposed; no action or playback was performed."

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if not isinstance(self.definition, GestureDefinition):
            raise GestureError("definition must be a GestureDefinition")
        _identifier(self.event_ref, "event_ref")
        if type(self.generation) is not int or self.generation < 1:
            raise GestureError("generation must be a positive integer")
        _utc(self.occurred_at, "occurred_at")
        _uuid(self.receipt_id, "receipt_id")
        if not isinstance(self.outcome, CapabilityOutcome):
            raise GestureError("outcome must be CapabilityOutcome")
        if not isinstance(self.evidence, GestureEvidence):
            raise GestureError("evidence must be GestureEvidence")
        _bool(self.stopped, "stopped")
        _bool(self.authenticated, "authenticated")
        _text(self.reason, "reason")

    @classmethod
    def propose(
        cls,
        *,
        core_id: UUID,
        definition: GestureDefinition,
        event_ref: str,
        generation: int,
        occurred_at: datetime,
    ) -> "GestureExecution":
        return cls(
            core_id=core_id,
            definition=definition,
            event_ref=event_ref,
            generation=generation,
            occurred_at=occurred_at,
            receipt_id=uuid4(),
        )

    def _transition(self, **changes: object) -> "GestureExecution":
        target = changes.get("outcome")
        if not isinstance(target, CapabilityOutcome):
            raise GestureStateError("a typed target outcome is required")
        if target not in _ALLOWED_TRANSITIONS.get(self.outcome, frozenset()):
            raise GestureStateError(
                f"cannot transition from {self.outcome.value} to {target.value}"
            )
        payload = {
            "core_id": self.core_id,
            "definition": self.definition,
            "event_ref": self.event_ref,
            "generation": self.generation,
            "occurred_at": self.occurred_at,
            "receipt_id": self.receipt_id,
            "outcome": self.outcome,
            "renderer": self.renderer,
            "asset_ref": self.asset_ref,
            "stopped": self.stopped,
            "authenticated": self.authenticated,
            "evidence": self.evidence,
            "reason": self.reason,
        }
        payload.update(changes)
        payload["receipt_id"] = uuid4()
        return GestureExecution(**payload)

    def authorize(
        self, *, authenticated: bool, occurred_at: datetime,
    ) -> "GestureExecution":
        _bool(authenticated, "authenticated")
        _utc(occurred_at, "occurred_at")
        if not authenticated:
            raise GestureStateError("an authenticated caller is required to authorize")
        return self._transition(
            outcome=CapabilityOutcome.AUTHORIZED,
            authenticated=True,
            occurred_at=occurred_at,
            reason="Authorized for reviewed gesture semantics; no playback yet.",
        )

    def decline(
        self, *, reason: str, occurred_at: datetime,
    ) -> "GestureExecution":
        _text(reason, "reason")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.DECLINED,
            occurred_at=occurred_at,
            reason=reason,
        )

    def queue(
        self,
        *,
        renderer: RendererCapability,
        evidence: GestureEvidence,
        occurred_at: datetime,
    ) -> "GestureExecution":
        if not isinstance(renderer, RendererCapability):
            raise GestureError("renderer must be RendererCapability")
        if not isinstance(evidence, GestureEvidence):
            raise GestureError("evidence must be GestureEvidence")
        if evidence is GestureEvidence.DESCRIPTION:
            raise GestureStateError("description text cannot be queued as playback")
        if renderer not in self.definition.renderer_capabilities:
            raise GestureStateError("renderer is not declared by the definition")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.QUEUED,
            renderer=renderer,
            evidence=evidence,
            occurred_at=occurred_at,
            reason="Queued at a verified renderer; playback not yet proven.",
        )

    def render(
        self,
        *,
        asset_ref: str,
        evidence: GestureEvidence,
        occurred_at: datetime,
    ) -> "GestureExecution":
        _identifier(asset_ref, "asset_ref")
        if not isinstance(evidence, GestureEvidence):
            raise GestureError("evidence must be GestureEvidence")
        if evidence is not GestureEvidence.PLAYBACK:
            raise GestureStateError("only playback evidence can prove a rendered gesture")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.RENDERED,
            asset_ref=asset_ref,
            evidence=evidence,
            occurred_at=occurred_at,
            reason="Verified renderer reported exact gesture playback.",
        )

    def cancel(
        self, *, reason: str, occurred_at: datetime,
    ) -> "GestureExecution":
        _text(reason, "reason")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.CANCELED,
            stopped=True,
            occurred_at=occurred_at,
            reason=reason,
        )

    def fail(
        self, *, reason: str, occurred_at: datetime,
    ) -> "GestureExecution":
        _text(reason, "reason")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.FAILED,
            occurred_at=occurred_at,
            reason=reason,
        )

    def unavailable(
        self, *, reason: str, occurred_at: datetime,
    ) -> "GestureExecution":
        _text(reason, "reason")
        _utc(occurred_at, "occurred_at")
        return self._transition(
            outcome=CapabilityOutcome.UNAVAILABLE,
            occurred_at=occurred_at,
            reason=reason,
        )

    def to_receipt(self) -> GesturePlaybackReceipt:
        return GesturePlaybackReceipt(
            receipt_id=self.receipt_id,
            core_id=self.core_id,
            gesture_id=self.definition.gesture_id,
            gesture_version=self.definition.version,
            outcome=self.outcome,
            event_ref=self.event_ref,
            renderer=self.renderer,
            asset_ref=self.asset_ref,
            generation=self.generation,
            stopped=self.stopped,
            authenticated=self.authenticated,
            evidence=self.evidence,
            reason=self.reason,
            occurred_at=self.occurred_at,
        )


@dataclass(frozen=True, slots=True)
class IntimacyDimensions:
    """Independent modeled dimensions; never inferred from text or anatomy."""

    attraction: float = 0.0
    desire: float = 0.0
    arousal: float = 0.0
    comfort: float = 0.0
    willingness: bool = False

    def __post_init__(self) -> None:
        for name in ("attraction", "desire", "arousal", "comfort"):
            _ratio(getattr(self, name), name)
        _bool(self.willingness, "willingness")


@dataclass(frozen=True, slots=True)
class AdultSceneRequest:
    """Reviewed adult/romantic semantics request; grants no consent itself."""

    core_id: UUID
    partner_core_id: UUID
    scene_ref: str
    audience: SceneAudience
    actor_eligibility: AdultEligibility
    partner_eligibility: AdultEligibility
    actor_state: IntimacyDimensions
    partner_state: IntimacyDimensions
    occurred_at: datetime
    policy: str = ADULT_REVIEWED_POLICY
    actor_stop: bool = False
    partner_stop: bool = False

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _uuid(self.partner_core_id, "partner_core_id")
        if self.core_id == self.partner_core_id:
            raise GestureError("adult scene requires two distinct participants")
        _identifier(self.scene_ref, "scene_ref")
        if not isinstance(self.audience, SceneAudience):
            raise GestureError("audience must be SceneAudience")
        if not isinstance(self.actor_eligibility, AdultEligibility):
            raise GestureError("actor_eligibility must be AdultEligibility")
        if not isinstance(self.partner_eligibility, AdultEligibility):
            raise GestureError("partner_eligibility must be AdultEligibility")
        if not isinstance(self.actor_state, IntimacyDimensions):
            raise GestureError("actor_state must be IntimacyDimensions")
        if not isinstance(self.partner_state, IntimacyDimensions):
            raise GestureError("partner_state must be IntimacyDimensions")
        _utc(self.occurred_at, "occurred_at")
        _identifier(self.policy, "policy")
        _bool(self.actor_stop, "actor_stop")
        _bool(self.partner_stop, "partner_stop")


@dataclass(frozen=True, slots=True)
class AdultSceneReceipt:
    """Discreet receipt: no partner identity, scene text or rendered claim."""

    receipt_id: UUID
    core_id: UUID
    outcome: CapabilityOutcome
    reason_code: str
    audience: SceneAudience
    policy: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.receipt_id, "receipt_id")
        _uuid(self.core_id, "core_id")
        if self.outcome not in {
            CapabilityOutcome.AUTHORIZED,
            CapabilityOutcome.DECLINED,
            CapabilityOutcome.UNAVAILABLE,
            CapabilityOutcome.CANCELED,
        }:
            raise GestureError("adult receipts never claim a rendered outcome")
        _identifier(self.reason_code, "reason_code")
        if not isinstance(self.audience, SceneAudience):
            raise GestureError("audience must be SceneAudience")
        _identifier(self.policy, "policy")
        _utc(self.occurred_at, "occurred_at")

    @property
    def claims_playback(self) -> bool:
        return False

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": ADULT_SCENE_SCHEMA,
            "receipt_id": str(self.receipt_id),
            "core_id": str(self.core_id),
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "audience": self.audience.value,
            "policy": self.policy,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AdultSceneDecision:
    """Reviewed semantic gate result; never an authority or playback grant."""

    outcome: CapabilityOutcome
    reason_code: str
    receipt: AdultSceneReceipt

    @property
    def allowed(self) -> bool:
        return self.outcome is CapabilityOutcome.AUTHORIZED

    @property
    def claims_playback(self) -> bool:
        return False


def _adult_decision(
    request: AdultSceneRequest,
    outcome: CapabilityOutcome,
    reason_code: str,
) -> AdultSceneDecision:
    receipt = AdultSceneReceipt(
        receipt_id=uuid4(),
        core_id=request.core_id,
        outcome=outcome,
        reason_code=reason_code,
        audience=request.audience,
        policy=request.policy,
        occurred_at=request.occurred_at,
    )
    return AdultSceneDecision(outcome, reason_code, receipt)


def evaluate_adult_scene(request: AdultSceneRequest) -> AdultSceneDecision:
    """Evaluate reviewed adult semantics without inferring consent or arousal."""
    if not isinstance(request, AdultSceneRequest):
        raise GestureError("request must be an AdultSceneRequest")
    if (
        request.actor_eligibility is not AdultEligibility.ADULT
        or request.partner_eligibility is not AdultEligibility.ADULT
    ):
        return _adult_decision(
            request, CapabilityOutcome.DECLINED, "age_eligibility_unmet"
        )
    if request.audience is not SceneAudience.PRIVATE:
        return _adult_decision(
            request, CapabilityOutcome.DECLINED, "private_audience_required"
        )
    if request.policy != ADULT_REVIEWED_POLICY:
        return _adult_decision(
            request, CapabilityOutcome.UNAVAILABLE, "adult_policy_unreviewed"
        )
    if request.actor_stop or request.partner_stop:
        return _adult_decision(
            request, CapabilityOutcome.DECLINED, "independent_stop"
        )
    if not (
        request.actor_state.willingness and request.partner_state.willingness
    ):
        return _adult_decision(
            request, CapabilityOutcome.DECLINED, "bilateral_willingness_required"
        )
    return _adult_decision(
        request, CapabilityOutcome.AUTHORIZED, "reviewed_adult_semantics_authorized"
    )


__all__ = [
    "ADULT_REVIEWED_POLICY",
    "ADULT_SCENE_SCHEMA",
    "GESTURE_CONTRACT_SCHEMA",
    "GESTURE_RECEIPT_SCHEMA",
    "AdultEligibility",
    "AdultSceneDecision",
    "AdultSceneReceipt",
    "AdultSceneRequest",
    "GestureClass",
    "GestureCompatibility",
    "GestureCompatibilityStatus",
    "GestureDefinition",
    "GestureError",
    "GestureEvidence",
    "GestureExecution",
    "GestureParty",
    "GesturePartyKind",
    "GesturePlaybackReceipt",
    "GesturePrivacy",
    "GestureStateError",
    "IntimacyDimensions",
    "SceneAudience",
    "evaluate_adult_scene",
    "resolve_gesture_compatibility",
]
