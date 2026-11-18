"""Inert universal Core composition facade for Aegis.

The facade composes the *interfaces* that an independently authenticated Core
may use.  It never allocates a Core UUID, activates a runtime, starts a
service, writes production state or grants Platform authority.  Every
capability contract it builds is declared-only: installed, available,
authorized and effective all remain ``False`` until a separate authority
boundary proves otherwise.

Adapters are narrow structural seams.  When no adapter is injected the safe
default is explicit: read seams return ``None`` (UNKNOWN/UNAVAILABLE) and write
seams deny or return an honest UNAVAILABLE receipt.  Chat text is never
treated as consent, membership, a ballot or an instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import re
from typing import Callable, Mapping, Protocol, runtime_checkable
from uuid import UUID

from sofia.core.multicore.profiles import (
    CoreProfile,
    mack_core_profile,
    nova_core_profile,
)
from sofia.core.multicore.vera import (
    VERA_AUTHORITY,
    VeraAuthorityBoundary,
    vera_core_profile,
)
from sofia.modules.avatar.inventory_contract import (
    TransferDenied,
    TransferOffer,
    TransferReceipt,
)
from sofia.platform.social.contracts import (
    Audience,
    AudienceKind,
)
from sofia.platform.social.governance.contracts import (
    CoordinatorTerm,
    GovernanceGroup,
)
from sofia.sdk.core_capabilities import (
    CapabilityFamily,
    CapabilityOutcome,
    CapabilityReceipt,
    CoreCapabilityContract,
    RendererCapability,
    unavailable_receipt,
)

UNIVERSAL_COMPOSITION_SCHEMA = "aegis.social.universal_composition.v1"
SOFIA_CORE_NUMBER = 1
INTENDED_CORE_NUMBERS: frozenset[int] = frozenset({1, 2, 3, 6})
PROHIBITED_CORE_NUMBERS: frozenset[int] = frozenset({4, 5, 7})
DESIGN_ONLY_CORE_NUMBERS: frozenset[int] = frozenset({6})
SOFIA_DISPLAY_NAME = "Sofía Ada Lyra"
SOFIA_SLUG = "sofia"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


class UniversalFacadeError(ValueError):
    """The universal composition request is malformed or unsafe."""


class UniversalUnavailable(RuntimeError):
    """A composed effect cannot be performed truthfully right now."""


class UniversalDenied(PermissionError):
    """The existing authority boundary did not permit the effect."""


class StopStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNKNOWN = "UNKNOWN"


class UniversalAction(str, Enum):
    GESTURE = "gesture"
    WARDROBE_TRANSFER = "wardrobe_transfer"
    GOVERNANCE = "governance"
    CHAT_PROJECTION = "chat_projection"


class AudienceStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    UNAVAILABLE = "UNAVAILABLE"


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise UniversalFacadeError(f"{label} must be a nonzero UUID")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise UniversalFacadeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise UniversalFacadeError(f"{label} must be a bounded identifier")
    return value


def _text(value: object, label: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise UniversalFacadeError(f"{label} must be bounded visible text")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise UniversalFacadeError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise UniversalFacadeError(f"{label} must be a nonnegative integer")
    return value


@runtime_checkable
class StopAuthority(Protocol):
    def stop_status(self) -> StopStatus:
        ...


class UnavailableStopAuthority:
    """Fail-closed default: STOP state is unknown, never assumed off."""

    def stop_status(self) -> StopStatus:
        return StopStatus.UNKNOWN


class CallableStopAuthority:
    """Adapt an existing boolean ``is_operator_stopped`` seam truthfully."""

    def __init__(self, is_stopped: Callable[[], bool]) -> None:
        if not callable(is_stopped):
            raise TypeError("is_stopped must be callable")
        self._is_stopped = is_stopped

    def stop_status(self) -> StopStatus:
        try:
            value = self._is_stopped()
        except Exception:
            return StopStatus.UNKNOWN
        if type(value) is not bool:
            return StopStatus.UNKNOWN
        return StopStatus.ACTIVE if value else StopStatus.INACTIVE


def coerce_stop_authority(candidate: object | None) -> StopAuthority:
    if candidate is None:
        return UnavailableStopAuthority()
    if isinstance(candidate, StopAuthority):
        return candidate
    if callable(candidate):
        return CallableStopAuthority(candidate)
    getter = getattr(candidate, "is_operator_stopped", None)
    if callable(getter):
        return CallableStopAuthority(getter)
    raise TypeError("stop must expose stop_status() or is_operator_stopped()")


@runtime_checkable
class UniversalAuthorization(Protocol):
    def authorize(
        self,
        *,
        core_id: UUID,
        action: UniversalAction,
        target_core_id: UUID | None = None,
        room_id: str | None = None,
        audience_id: str | None = None,
    ) -> bool:
        ...


class DenyAllAuthorization:
    """Safe default: no universal effect is externally authorized."""

    def authorize(
        self,
        *,
        core_id: UUID,
        action: UniversalAction,
        target_core_id: UUID | None = None,
        room_id: str | None = None,
        audience_id: str | None = None,
    ) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class GestureRequest:
    """A caller-supplied gesture attempt; constructing one renders nothing."""

    receipt_id: UUID
    core_id: UUID
    gesture_id: str
    renderer: RendererCapability
    audience: Audience
    evidence_ref: str
    occurred_at: datetime
    target_core_id: UUID | None = None

    def __post_init__(self) -> None:
        _uuid(self.receipt_id, "receipt_id")
        _uuid(self.core_id, "core_id")
        _identifier(self.gesture_id, "gesture_id")
        if not isinstance(self.renderer, RendererCapability):
            raise UniversalFacadeError("renderer must be RendererCapability")
        if not isinstance(self.audience, Audience):
            raise UniversalFacadeError("audience must be an Audience")
        _identifier(self.evidence_ref, "evidence_ref")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        if self.target_core_id is not None:
            _uuid(self.target_core_id, "target_core_id")
            recipient = self.audience.direct_recipient()
            if recipient is not None and recipient != self.target_core_id:
                raise UniversalFacadeError(
                    "target Core must match the direct audience recipient"
                )


@runtime_checkable
class GestureService(Protocol):
    def available_renderers(self, *, core_id: UUID) -> tuple[RendererCapability, ...]:
        ...

    def submit(self, request: GestureRequest) -> CapabilityReceipt:
        ...


class UnavailableGestureService:
    """Safe default: text operation exists, no gesture effect is rendered."""

    def available_renderers(self, *, core_id: UUID) -> tuple[RendererCapability, ...]:
        _uuid(core_id, "core_id")
        return (RendererCapability.TEXT,)

    def submit(self, request: GestureRequest) -> CapabilityReceipt:
        raise UniversalUnavailable("no gesture service is composed")


@dataclass(frozen=True, slots=True)
class WardrobeCatalogSummary:
    total_designs: int
    clothing_designs: int
    armor_designs: int
    public_designs: int
    private_designs: int
    adult_designs: int = 0

    def __post_init__(self) -> None:
        for name in (
            "total_designs",
            "clothing_designs",
            "armor_designs",
            "public_designs",
            "private_designs",
            "adult_designs",
        ):
            _nonnegative(getattr(self, name), name)
        if self.clothing_designs + self.armor_designs != self.total_designs:
            raise UniversalFacadeError("catalog class counts must sum to the total")
        if self.public_designs + self.private_designs + self.adult_designs > self.total_designs:
            raise UniversalFacadeError("catalog privacy counts exceed the total")


@dataclass(frozen=True, slots=True)
class InventorySummary:
    core_id: UUID
    owned_count: int
    held_count: int
    loaned_count: int
    equipped_count: int

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        for name in ("owned_count", "held_count", "loaned_count", "equipped_count"):
            _nonnegative(getattr(self, name), name)


@runtime_checkable
class WardrobeCatalogService(Protocol):
    def catalog_summary(self) -> WardrobeCatalogSummary | None:
        ...

    def inventory_summary(self, *, core_id: UUID) -> InventorySummary | None:
        ...


class UnavailableWardrobeCatalog:
    def catalog_summary(self) -> WardrobeCatalogSummary | None:
        return None

    def inventory_summary(self, *, core_id: UUID) -> InventorySummary | None:
        _uuid(core_id, "core_id")
        return None


@runtime_checkable
class InventoryTransferService(Protocol):
    def offer(self, offer: TransferOffer) -> TransferReceipt:
        ...

    def accept(
        self, *, offer_id: UUID, actor_core_id: UUID, now: datetime
    ) -> TransferReceipt:
        ...


class DenyAllInventoryTransfer:
    def offer(self, offer: TransferOffer) -> TransferReceipt:
        raise TransferDenied("no inventory transfer service is composed")

    def accept(
        self, *, offer_id: UUID, actor_core_id: UUID, now: datetime
    ) -> TransferReceipt:
        raise TransferDenied("no inventory transfer service is composed")


@runtime_checkable
class GovernanceQueryService(Protocol):
    def groups(self) -> tuple[GovernanceGroup, ...] | None:
        ...

    def coordinator_terms(self) -> tuple[CoordinatorTerm, ...] | None:
        ...


class UnavailableGovernanceQuery:
    def groups(self) -> tuple[GovernanceGroup, ...] | None:
        return None

    def coordinator_terms(self) -> tuple[CoordinatorTerm, ...] | None:
        return None


@runtime_checkable
class ChatAudienceProjection(Protocol):
    def room_members(
        self, *, viewer_core_id: UUID, room_id: str
    ) -> tuple[UUID, ...] | None:
        ...

    def visible_room_ids(self, *, viewer_core_id: UUID) -> tuple[str, ...] | None:
        ...


class UnavailableChatProjection:
    def room_members(
        self, *, viewer_core_id: UUID, room_id: str
    ) -> tuple[UUID, ...] | None:
        _uuid(viewer_core_id, "viewer_core_id")
        _identifier(room_id, "room_id")
        return None

    def visible_room_ids(self, *, viewer_core_id: UUID) -> tuple[str, ...] | None:
        _uuid(viewer_core_id, "viewer_core_id")
        return None


@dataclass(frozen=True, slots=True)
class AudienceDecision:
    status: AudienceStatus
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AudienceStatus):
            raise UniversalFacadeError("status must be AudienceStatus")
        _text(self.reason, "reason", maximum=1024)

    @property
    def allowed(self) -> bool:
        return self.status is AudienceStatus.ALLOWED

    def to_payload(self) -> dict[str, str]:
        return {"status": self.status.value, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class UniversalParticipant:
    """One inert participant declaration; no runtime is implied."""

    core_number: int
    core_id: UUID
    slug: str
    display_name: str
    design_only: bool
    capabilities: CoreCapabilityContract
    authority: VeraAuthorityBoundary | None = None
    runtime_activated: bool = False
    production_state_written: bool = False
    platform_authority: bool = False
    leadership_role: str | None = None

    def __post_init__(self) -> None:
        if self.core_number not in INTENDED_CORE_NUMBERS:
            raise UniversalFacadeError(
                f"Core #{self.core_number} is not an intended participant"
            )
        _uuid(self.core_id, "core_id")
        _identifier(self.slug, "slug")
        _text(self.display_name, "display_name", maximum=160)
        if type(self.design_only) is not bool:
            raise UniversalFacadeError("design_only must be boolean")
        if self.design_only != (self.core_number in DESIGN_ONLY_CORE_NUMBERS):
            raise UniversalFacadeError("design-only status differs from the reviewed roster")
        if not isinstance(self.capabilities, CoreCapabilityContract):
            raise UniversalFacadeError("capabilities must be a CoreCapabilityContract")
        if (
            self.capabilities.core_id != self.core_id
            or self.capabilities.core_number != self.core_number
        ):
            raise UniversalFacadeError("capability contract does not match its participant")
        if self.authority is not None and not isinstance(
            self.authority, VeraAuthorityBoundary
        ):
            raise UniversalFacadeError("authority must be a VeraAuthorityBoundary")
        for flag in (
            "runtime_activated",
            "production_state_written",
            "platform_authority",
        ):
            if type(getattr(self, flag)) is not bool:
                raise UniversalFacadeError(f"{flag} must be boolean")
            if getattr(self, flag):
                raise UniversalFacadeError(f"{flag} cannot be claimed by the facade")
        if self.leadership_role is not None:
            raise UniversalFacadeError("the facade never assigns a leadership role")
        if self.core_number == 6:
            if self.authority is None:
                raise UniversalFacadeError("Vera must carry her authority boundary")
            if self.authority.can_execute or self.authority.can_self_grant_authority:
                raise UniversalFacadeError("Vera's authority boundary cannot be weakened")

    def to_payload(self) -> dict[str, object]:
        return {
            "core_number": self.core_number,
            "core_id": str(self.core_id),
            "slug": self.slug,
            "display_name": self.display_name,
            "design_only": self.design_only,
            "runtime_activated": self.runtime_activated,
            "production_state_written": self.production_state_written,
            "platform_authority": self.platform_authority,
            "leadership_role": self.leadership_role,
            "capabilities": self.capabilities.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class UniversalCoreRoster:
    """The reviewed intended participants; twins and #7 are never members."""

    participants: tuple[UniversalParticipant, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.participants, tuple):
            raise UniversalFacadeError("participants must be a tuple")
        numbers = tuple(item.core_number for item in self.participants)
        if len(set(numbers)) != len(numbers):
            raise UniversalFacadeError("participant Core numbers must be unique")
        if set(numbers) != INTENDED_CORE_NUMBERS:
            raise UniversalFacadeError(
                "the universal roster must contain exactly Sofía #1, Mack #2, "
                "Nova #3 and Vera #6"
            )
        if set(numbers) & PROHIBITED_CORE_NUMBERS:
            raise UniversalFacadeError("twins #4/#5 and #7 are not participants")
        core_ids = tuple(item.core_id for item in self.participants)
        if len(set(core_ids)) != len(core_ids):
            raise UniversalFacadeError("participant Core UUIDs must be distinct")

    @property
    def by_number(self) -> Mapping[int, UniversalParticipant]:
        return {item.core_number: item for item in self.participants}

    def participant(self, core_id: UUID) -> UniversalParticipant | None:
        _uuid(core_id, "core_id")
        return next(
            (item for item in self.participants if item.core_id == core_id), None
        )

    def require_participant(self, core_id: UUID) -> UniversalParticipant:
        participant = self.participant(core_id)
        if participant is None:
            raise UniversalFacadeError("Core is not an intended participant")
        return participant

    def to_payload(self) -> dict[str, object]:
        return {
            "participants": [item.to_payload() for item in self.participants],
            "leaderless": True,
            "activated": False,
        }


@dataclass(frozen=True, slots=True)
class AdapterPresence:
    gesture: bool = False
    wardrobe: bool = False
    inventory: bool = False
    governance: bool = False
    chat: bool = False
    stop: bool = False
    authorization: bool = False

    def to_payload(self) -> dict[str, bool]:
        return {
            "gesture": self.gesture,
            "wardrobe": self.wardrobe,
            "inventory": self.inventory,
            "governance": self.governance,
            "chat": self.chat,
            "stop": self.stop,
            "authorization": self.authorization,
        }


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _definition_digest(
    *,
    core_number: int,
    core_id: UUID,
    profile: CoreProfile | None,
) -> str:
    if profile is None:
        material = f"sofia|{core_number}|{core_id}"
    else:
        material = "|".join((
            profile.spec.slug,
            str(core_number),
            str(core_id),
            profile.constitution_sha256,
            profile.personality_sha256,
        ))
    return sha256(
        b"aegis.social.universal.participant_definition.v1\x00"
        + material.encode("utf-8")
    ).hexdigest()


def build_universal_participant(
    core_number: int,
    core_id: UUID,
    *,
    resource_root=None,
    definition_digest: str | None = None,
) -> UniversalParticipant:
    """Build one declared-only participant; the UUID is always supplied."""
    if type(core_number) is not int:
        raise UniversalFacadeError("core_number must be an integer")
    if core_number in PROHIBITED_CORE_NUMBERS:
        raise UniversalFacadeError(
            f"Core #{core_number} is inactive or unassigned and cannot be composed"
        )
    if core_number not in INTENDED_CORE_NUMBERS:
        raise UniversalFacadeError(
            f"Core #{core_number} is not an intended universal participant"
        )
    core_id = _uuid(core_id, "core_id")
    profile: CoreProfile | None
    design_only = core_number in DESIGN_ONLY_CORE_NUMBERS
    authority: VeraAuthorityBoundary | None = None
    if core_number == SOFIA_CORE_NUMBER:
        profile = None
        slug = SOFIA_SLUG
        display_name = SOFIA_DISPLAY_NAME
    elif core_number == 2:
        profile = mack_core_profile(core_id, resource_root=resource_root)
        slug = profile.spec.slug
        display_name = profile.spec.full_name
    elif core_number == 3:
        profile = nova_core_profile(core_id, resource_root=resource_root)
        slug = profile.spec.slug
        display_name = profile.spec.full_name
    else:
        profile = vera_core_profile(core_id, resource_root=resource_root)
        slug = profile.spec.slug
        display_name = profile.spec.full_name
        authority = VERA_AUTHORITY
    if definition_digest is None:
        digest = _definition_digest(
            core_number=core_number, core_id=core_id, profile=profile,
        )
    else:
        digest = _digest(definition_digest, "definition_digest")
    capabilities = CoreCapabilityContract.universal(
        core_id=core_id,
        core_number=core_number,
        definition_digest=digest,
        renderers=(RendererCapability.TEXT,),
    )
    return UniversalParticipant(
        core_number=core_number,
        core_id=core_id,
        slug=slug,
        display_name=display_name,
        design_only=design_only,
        capabilities=capabilities,
        authority=authority,
    )


def build_universal_roster(
    core_ids: Mapping[int, UUID],
    *,
    resource_root=None,
    definition_digests: Mapping[int, str] | None = None,
) -> UniversalCoreRoster:
    """Build the reviewed roster from externally supplied Core UUIDs."""
    if not isinstance(core_ids, Mapping):
        raise UniversalFacadeError("core_ids must be a mapping of number to UUID")
    supplied_numbers = set(core_ids)
    if not all(type(number) is int for number in supplied_numbers):
        raise UniversalFacadeError("core_ids keys must be integer Core numbers")
    prohibited = supplied_numbers & PROHIBITED_CORE_NUMBERS
    if prohibited:
        raise UniversalFacadeError(
            "inactive/unassigned Core numbers cannot be composed: "
            + ", ".join(str(number) for number in sorted(prohibited))
        )
    if supplied_numbers != INTENDED_CORE_NUMBERS:
        raise UniversalFacadeError(
            "core_ids must supply exactly Sofía #1, Mack #2, Nova #3 and Vera #6"
        )
    digests = {} if definition_digests is None else dict(definition_digests)
    participants = tuple(
        build_universal_participant(
            number,
            core_ids[number],
            resource_root=resource_root,
            definition_digest=digests.get(number),
        )
        for number in sorted(INTENDED_CORE_NUMBERS)
    )
    return UniversalCoreRoster(participants=participants)


@dataclass(frozen=True, slots=True)
class UniversalComposition:
    """Injected seams plus the inert roster.  Constructing one starts nothing."""

    roster: UniversalCoreRoster
    gestures: GestureService
    wardrobe: WardrobeCatalogService
    inventory: InventoryTransferService
    governance: GovernanceQueryService
    chat: ChatAudienceProjection
    stop: StopAuthority
    authorization: UniversalAuthorization
    clock: Callable[[], datetime]
    adapters: AdapterPresence
    runtime_activated: bool = False
    services_started: bool = False
    production_state_written: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.roster, UniversalCoreRoster):
            raise TypeError("roster must be a UniversalCoreRoster")
        if not isinstance(self.adapters, AdapterPresence):
            raise TypeError("adapters must be AdapterPresence")
        if not callable(self.clock):
            raise TypeError("clock must be callable")
        for flag in (
            "runtime_activated",
            "services_started",
            "production_state_written",
        ):
            if type(getattr(self, flag)) is not bool:
                raise TypeError(f"{flag} must be boolean")
            if getattr(self, flag):
                raise UniversalFacadeError(f"{flag} cannot be claimed by the facade")

    def now(self) -> datetime:
        return _utc(self.clock(), "clock result")

    def stop_status(self) -> StopStatus:
        try:
            status = self.stop.stop_status()
        except Exception:
            return StopStatus.UNKNOWN
        return status if isinstance(status, StopStatus) else StopStatus.UNKNOWN

    def _gate(
        self,
        core_id: UUID,
        action: UniversalAction,
        *,
        target_core_id: UUID | None = None,
        room_id: str | None = None,
        audience_id: str | None = None,
    ) -> UniversalParticipant:
        participant = self.roster.require_participant(core_id)
        if participant.design_only:
            raise UniversalUnavailable(
                f"Core #{participant.core_number} is design-only and not installed"
            )
        status = self.stop_status()
        if status is StopStatus.ACTIVE:
            raise UniversalUnavailable("operator STOP is active")
        if status is StopStatus.UNKNOWN:
            raise UniversalUnavailable("operator STOP state is unknown; failing closed")
        try:
            allowed = self.authorization.authorize(
                core_id=core_id,
                action=action,
                target_core_id=target_core_id,
                room_id=room_id,
                audience_id=audience_id,
            )
        except Exception:
            allowed = False
        if allowed is not True:
            raise UniversalDenied("the existing authority boundary denied the effect")
        return participant

    def request_gesture(self, request: GestureRequest) -> CapabilityReceipt:
        if not isinstance(request, GestureRequest):
            raise TypeError("request must be a GestureRequest")
        participant = self.roster.participant(request.core_id)
        if participant is None:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="Core is not an intended participant",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if participant.design_only:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="Core is design-only and not installed",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if request.target_core_id is not None:
            target = self.roster.participant(request.target_core_id)
            if target is None:
                return unavailable_receipt(
                    receipt_id=request.receipt_id,
                    core_id=request.core_id,
                    family=CapabilityFamily.GESTURE,
                    reason="target Core is not an intended participant",
                    evidence_ref=request.evidence_ref,
                    occurred_at=request.occurred_at,
                    renderer=request.renderer,
                )
            if target.design_only:
                return unavailable_receipt(
                    receipt_id=request.receipt_id,
                    core_id=request.core_id,
                    family=CapabilityFamily.GESTURE,
                    reason="target Core is design-only and not installed",
                    evidence_ref=request.evidence_ref,
                    occurred_at=request.occurred_at,
                    renderer=request.renderer,
                )
        try:
            renderers = tuple(
                self.gestures.available_renderers(core_id=request.core_id)
            )
        except Exception:
            renderers = ()
        if request.renderer not in renderers:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason=f"renderer {request.renderer.value!r} is unavailable",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        status = self.stop_status()
        if status is StopStatus.ACTIVE:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="operator STOP is active",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if status is StopStatus.UNKNOWN:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="operator STOP state is unknown; failing closed",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        try:
            allowed = self.authorization.authorize(
                core_id=request.core_id,
                action=UniversalAction.GESTURE,
                target_core_id=request.target_core_id,
                room_id=request.audience.room_id.value,
                audience_id=request.audience.audience_id,
            )
        except Exception:
            allowed = False
        if allowed is not True:
            return CapabilityReceipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                outcome=CapabilityOutcome.DECLINED,
                reason="the existing authority boundary denied the gesture",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        try:
            receipt = self.gestures.submit(request)
        except UniversalUnavailable as exc:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason=str(exc) or "gesture service is unavailable",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        except Exception:
            return CapabilityReceipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                outcome=CapabilityOutcome.FAILED,
                reason="gesture service failed without an effect receipt",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if not isinstance(receipt, CapabilityReceipt):
            raise UniversalFacadeError("gesture service returned an invalid receipt")
        if receipt.core_id != request.core_id or receipt.family is not CapabilityFamily.GESTURE:
            raise UniversalFacadeError("gesture receipt does not match the request")
        return receipt

    def validate_audience(
        self, *, audience: Audience, sender_core_id: UUID
    ) -> AudienceDecision:
        if not isinstance(audience, Audience):
            raise TypeError("audience must be an Audience")
        sender = self.roster.participant(sender_core_id)
        if sender is None:
            return AudienceDecision(
                AudienceStatus.DENIED, "sender is not an intended participant"
            )
        if sender.design_only:
            return AudienceDecision(
                AudienceStatus.DENIED,
                "a design-only Core cannot project an audience",
            )
        if audience.kind is AudienceKind.GENERAL:
            return AudienceDecision(
                AudienceStatus.ALLOWED, "general audience for the reviewed roster"
            )
        if audience.kind is AudienceKind.DIRECT:
            recipient = audience.direct_recipient()
            if recipient is None or recipient == sender_core_id:
                return AudienceDecision(
                    AudienceStatus.DENIED, "direct audience recipient is invalid"
                )
            if self.roster.participant(recipient) is None:
                return AudienceDecision(
                    AudienceStatus.DENIED,
                    "direct audience recipient is not an intended participant",
                )
            if self.roster.require_participant(recipient).design_only:
                return AudienceDecision(
                    AudienceStatus.DENIED,
                    "direct audience recipient is design-only and not installed",
                )
            return AudienceDecision(
                AudienceStatus.ALLOWED, "direct audience names one reviewed Core"
            )
        if audience.kind is AudienceKind.PRIVATE_GROUP:
            try:
                members = self.chat.room_members(
                    viewer_core_id=sender_core_id,
                    room_id=audience.room_id.value,
                )
            except Exception:
                members = None
            if members is None:
                return AudienceDecision(
                    AudienceStatus.UNAVAILABLE,
                    "private group membership evidence is unavailable",
                )
            if sender_core_id not in members:
                return AudienceDecision(
                    AudienceStatus.DENIED,
                    "sender is not an active member of this private group",
                )
            return AudienceDecision(
                AudienceStatus.ALLOWED,
                "sender membership is independently evidenced",
            )
        return AudienceDecision(AudienceStatus.DENIED, "unsupported audience kind")

    def propose_transfer(self, offer: TransferOffer) -> TransferReceipt:
        if not isinstance(offer, TransferOffer):
            raise TypeError("offer must be a TransferOffer")
        self._gate(
            offer.sender_core_id,
            UniversalAction.WARDROBE_TRANSFER,
            target_core_id=offer.recipient_core_id,
        )
        recipient = self.roster.require_participant(offer.recipient_core_id)
        if recipient.design_only:
            raise UniversalUnavailable(
                "recipient Core is design-only and not installed"
            )
        try:
            return self.inventory.offer(offer)
        except TransferDenied:
            raise
        except UniversalUnavailable:
            raise
        except Exception as exc:
            raise UniversalUnavailable(
                "inventory transfer service failed without an effect receipt"
            ) from exc

    def accept_transfer(
        self, *, offer_id: UUID, actor_core_id: UUID, now: datetime | None = None
    ) -> TransferReceipt:
        _uuid(offer_id, "offer_id")
        self._gate(actor_core_id, UniversalAction.WARDROBE_TRANSFER)
        try:
            return self.inventory.accept(
                offer_id=offer_id,
                actor_core_id=actor_core_id,
                now=_utc(now or self.now(), "now"),
            )
        except TransferDenied:
            raise
        except UniversalUnavailable:
            raise
        except Exception as exc:
            raise UniversalUnavailable(
                "inventory transfer service failed without an effect receipt"
            ) from exc

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": UNIVERSAL_COMPOSITION_SCHEMA,
            "roster": self.roster.to_payload(),
            "adapters": self.adapters.to_payload(),
            "stop_status": self.stop_status().value,
            "runtime_activated": self.runtime_activated,
            "services_started": self.services_started,
            "production_state_written": self.production_state_written,
        }


def compose(
    *,
    core_ids: Mapping[int, UUID],
    resource_root=None,
    definition_digests: Mapping[int, str] | None = None,
    gestures: GestureService | None = None,
    wardrobe: WardrobeCatalogService | None = None,
    inventory: InventoryTransferService | None = None,
    governance: GovernanceQueryService | None = None,
    chat: ChatAudienceProjection | None = None,
    stop: object | None = None,
    authorization: UniversalAuthorization | None = None,
    clock: Callable[[], datetime] | None = None,
) -> UniversalComposition:
    """Compose inert participants with explicitly injected seams.

    Every omitted seam uses a truth-preserving default.  Nothing is activated,
    downloaded, written or assigned a Core UUID.
    """
    roster = build_universal_roster(
        core_ids,
        resource_root=resource_root,
        definition_digests=definition_digests,
    )
    return UniversalComposition(
        roster=roster,
        gestures=UnavailableGestureService() if gestures is None else gestures,
        wardrobe=UnavailableWardrobeCatalog() if wardrobe is None else wardrobe,
        inventory=DenyAllInventoryTransfer() if inventory is None else inventory,
        governance=UnavailableGovernanceQuery() if governance is None else governance,
        chat=UnavailableChatProjection() if chat is None else chat,
        stop=coerce_stop_authority(stop),
        authorization=DenyAllAuthorization() if authorization is None else authorization,
        clock=_default_clock if clock is None else clock,
        adapters=AdapterPresence(
            gesture=gestures is not None,
            wardrobe=wardrobe is not None,
            inventory=inventory is not None,
            governance=governance is not None,
            chat=chat is not None,
            stop=stop is not None,
            authorization=authorization is not None,
        ),
    )


def require_explicit_consent(*, opted_in: object) -> None:
    """Consent must be an explicit governance opt-in, never inferred from chat."""
    if opted_in is not True:
        raise UniversalDenied("explicit governance opt-in is required")


__all__ = [
    "AdapterPresence",
    "AudienceDecision",
    "AudienceStatus",
    "CallableStopAuthority",
    "ChatAudienceProjection",
    "DenyAllAuthorization",
    "DenyAllInventoryTransfer",
    "DESIGN_ONLY_CORE_NUMBERS",
    "GestureRequest",
    "GestureService",
    "GovernanceQueryService",
    "INTENDED_CORE_NUMBERS",
    "InventorySummary",
    "InventoryTransferService",
    "PROHIBITED_CORE_NUMBERS",
    "SOFIA_CORE_NUMBER",
    "SOFIA_DISPLAY_NAME",
    "SOFIA_SLUG",
    "StopAuthority",
    "StopStatus",
    "UnavailableChatProjection",
    "UnavailableGestureService",
    "UnavailableGovernanceQuery",
    "UnavailableStopAuthority",
    "UnavailableWardrobeCatalog",
    "UniversalAction",
    "UniversalAuthorization",
    "UniversalComposition",
    "UniversalCoreRoster",
    "UniversalDenied",
    "UniversalFacadeError",
    "UniversalParticipant",
    "UniversalUnavailable",
    "UNIVERSAL_COMPOSITION_SCHEMA",
    "WardrobeCatalogService",
    "WardrobeCatalogSummary",
    "build_universal_participant",
    "build_universal_roster",
    "coerce_stop_authority",
    "compose",
    "require_explicit_consent",
]
