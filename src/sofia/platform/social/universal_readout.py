"""Read-only universal Core snapshot for management and CLI surfaces.

The snapshot never mutates state, never invokes a transfer or gesture, never
reads ballots or private memory and never promotes a social role to Platform
authority.  Missing evidence is rendered as ``UNAVAILABLE`` or ``UNKNOWN``
instead of a fabricated zero or success.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping

from sofia.platform.social.universal import (
    AdapterPresence,
    StopStatus,
    UniversalComposition,
    UniversalParticipant,
)
from sofia.sdk.core_capabilities import (
    CapabilityFamily,
    CapabilityState,
    RendererCapability,
)

READOUT_SCHEMA = "aegis.social.universal_readout.v1"


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CapabilityReadout:
    family: str
    declared: bool
    installed: bool
    available: bool
    authorized: bool
    effective: bool
    state: str

    def __post_init__(self) -> None:
        if not isinstance(self.family, str) or not self.family:
            raise ValueError("family must be nonempty text")
        for name in ("declared", "installed", "available", "authorized", "effective"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if not isinstance(self.state, str) or not self.state:
            raise ValueError("state must be nonempty text")

    def to_payload(self) -> dict[str, object]:
        return {
            "family": self.family,
            "declared": self.declared,
            "installed": self.installed,
            "available": self.available,
            "authorized": self.authorized,
            "effective": self.effective,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class RendererReadout:
    renderer: str
    availability: Availability
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.renderer, str) or not self.renderer:
            raise ValueError("renderer must be nonempty text")
        if not isinstance(self.availability, Availability):
            raise ValueError("availability must be Availability")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not self.reason.strip()
        ):
            raise ValueError("reason must be nonempty text or None")

    def to_payload(self) -> dict[str, object]:
        return {
            "renderer": self.renderer,
            "availability": self.availability.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CoreReadout:
    core_number: int
    core_id: str
    display_name: str
    design_only: bool
    activated: bool
    runtime_state: str
    platform_authority: bool
    leadership_role: str | None
    capabilities: tuple[CapabilityReadout, ...]
    renderers: tuple[RendererReadout, ...]

    def __post_init__(self) -> None:
        if type(self.core_number) is not int or self.core_number < 1:
            raise ValueError("core_number must be positive")
        if not isinstance(self.core_id, str) or not self.core_id:
            raise ValueError("core_id must be nonempty text")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be nonempty text")
        for name in ("design_only", "activated", "platform_authority"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if self.activated or self.platform_authority or self.leadership_role is not None:
            raise ValueError("the readout cannot claim activation or authority")
        if not isinstance(self.capabilities, tuple) or not isinstance(
            self.renderers, tuple
        ):
            raise ValueError("capabilities and renderers must be tuples")

    def to_payload(self) -> dict[str, object]:
        return {
            "core_number": self.core_number,
            "core_id": self.core_id,
            "display_name": self.display_name,
            "design_only": self.design_only,
            "activated": self.activated,
            "runtime_state": self.runtime_state,
            "platform_authority": self.platform_authority,
            "leadership_role": self.leadership_role,
            "capabilities": [item.to_payload() for item in self.capabilities],
            "renderers": [item.to_payload() for item in self.renderers],
        }


@dataclass(frozen=True, slots=True)
class InventoryReadout:
    core_id: str
    availability: Availability
    owned_count: int | None = None
    held_count: int | None = None
    loaned_count: int | None = None
    equipped_count: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, str) or not self.core_id:
            raise ValueError("core_id must be nonempty text")
        if not isinstance(self.availability, Availability):
            raise ValueError("availability must be Availability")
        for name in ("owned_count", "held_count", "loaned_count", "equipped_count"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or None")

    def to_payload(self) -> dict[str, object]:
        return {
            "core_id": self.core_id,
            "availability": self.availability.value,
            "owned_count": self.owned_count,
            "held_count": self.held_count,
            "loaned_count": self.loaned_count,
            "equipped_count": self.equipped_count,
        }


@dataclass(frozen=True, slots=True)
class WardrobeReadout:
    availability: Availability
    total_designs: int | None = None
    clothing_designs: int | None = None
    armor_designs: int | None = None
    public_designs: int | None = None
    private_designs: int | None = None
    adult_designs: int | None = None
    inventories: tuple[InventoryReadout, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.availability, Availability):
            raise ValueError("availability must be Availability")
        for name in (
            "total_designs",
            "clothing_designs",
            "armor_designs",
            "public_designs",
            "private_designs",
            "adult_designs",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or None")
        if not isinstance(self.inventories, tuple):
            raise ValueError("inventories must be a tuple")

    def to_payload(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "total_designs": self.total_designs,
            "clothing_designs": self.clothing_designs,
            "armor_designs": self.armor_designs,
            "public_designs": self.public_designs,
            "private_designs": self.private_designs,
            "adult_designs": self.adult_designs,
            "inventories": [item.to_payload() for item in self.inventories],
        }


@dataclass(frozen=True, slots=True)
class GovernanceGroupReadout:
    group_id: str
    lifecycle: str
    member_count: int
    active_member_count: int
    leaderless: bool
    coordinator_term_active: bool | None

    def __post_init__(self) -> None:
        for name in ("group_id", "lifecycle"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be nonempty text")
        for name in ("member_count", "active_member_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if type(self.leaderless) is not bool:
            raise ValueError("leaderless must be boolean")
        if self.coordinator_term_active is not None and type(
            self.coordinator_term_active
        ) is not bool:
            raise ValueError("coordinator_term_active must be boolean or None")

    def to_payload(self) -> dict[str, object]:
        return {
            "group_id": self.group_id,
            "lifecycle": self.lifecycle,
            "member_count": self.member_count,
            "active_member_count": self.active_member_count,
            "leaderless": self.leaderless,
            "coordinator_term_active": self.coordinator_term_active,
        }


@dataclass(frozen=True, slots=True)
class GovernanceReadout:
    availability: Availability
    terms_availability: Availability
    group_count: int | None = None
    active_group_count: int | None = None
    coordinator_term_count: int | None = None
    active_coordinator_term_count: int | None = None
    groups: tuple[GovernanceGroupReadout, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("availability", self.availability),
            ("terms_availability", self.terms_availability),
        ):
            if not isinstance(value, Availability):
                raise ValueError(f"{label} must be Availability")
        for name in (
            "group_count",
            "active_group_count",
            "coordinator_term_count",
            "active_coordinator_term_count",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or None")
        if not isinstance(self.groups, tuple):
            raise ValueError("groups must be a tuple")

    def to_payload(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "terms_availability": self.terms_availability.value,
            "group_count": self.group_count,
            "active_group_count": self.active_group_count,
            "coordinator_term_count": self.coordinator_term_count,
            "active_coordinator_term_count": self.active_coordinator_term_count,
            "groups": [item.to_payload() for item in self.groups],
        }


@dataclass(frozen=True, slots=True)
class UniversalReadout:
    generated_at: str
    stop_status: StopStatus
    adapters: AdapterPresence
    cores: tuple[CoreReadout, ...]
    wardrobe: WardrobeReadout
    governance: GovernanceReadout
    authority: str = "READ_ONLY_NO_AUTHORITY"
    installed: bool = False
    live_verified: bool = False
    mutations_performed: bool = False
    secrets_included: bool = False
    private_member_ids_included: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, str) or not self.generated_at:
            raise ValueError("generated_at must be nonempty text")
        if not isinstance(self.stop_status, StopStatus):
            raise ValueError("stop_status must be StopStatus")
        if not isinstance(self.adapters, AdapterPresence):
            raise ValueError("adapters must be AdapterPresence")
        if not isinstance(self.cores, tuple) or not isinstance(
            self.wardrobe, WardrobeReadout
        ) or not isinstance(self.governance, GovernanceReadout):
            raise ValueError("readout sections have invalid types")
        if self.authority != "READ_ONLY_NO_AUTHORITY":
            raise ValueError("the readout authority label cannot be expanded")
        for name in (
            "installed",
            "live_verified",
            "mutations_performed",
            "secrets_included",
            "private_member_ids_included",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if self.mutations_performed or self.secrets_included:
            raise ValueError("readout cannot claim mutations or secrets")
        if self.private_member_ids_included:
            raise ValueError("readout cannot include private member identifiers")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": READOUT_SCHEMA,
            "generated_at": self.generated_at,
            "stop_status": self.stop_status.value,
            "adapters": self.adapters.to_payload(),
            "cores": [item.to_payload() for item in self.cores],
            "wardrobe": self.wardrobe.to_payload(),
            "governance": self.governance.to_payload(),
            "authority": self.authority,
            "installed": self.installed,
            "live_verified": self.live_verified,
            "mutations_performed": self.mutations_performed,
            "secrets_included": self.secrets_included,
            "private_member_ids_included": self.private_member_ids_included,
        }


def _capability_state_name(state: CapabilityState) -> str:
    if state.effective:
        return "EFFECTIVE"
    if state.authorized:
        return "AUTHORIZED"
    if state.available:
        return "AVAILABLE"
    if state.installed:
        return "INSTALLED"
    return "DECLARED_ONLY"


def _capabilities(participant: UniversalParticipant) -> tuple[CapabilityReadout, ...]:
    return tuple(
        CapabilityReadout(
            family=family.value,
            declared=participant.capabilities.state(family).declared,
            installed=participant.capabilities.state(family).installed,
            available=participant.capabilities.state(family).available,
            authorized=participant.capabilities.state(family).authorized,
            effective=participant.capabilities.state(family).effective,
            state=_capability_state_name(participant.capabilities.state(family)),
        )
        for family in CapabilityFamily
    )


def _renderers(
    participant: UniversalParticipant,
    composition: UniversalComposition,
) -> tuple[RendererReadout, ...]:
    if not composition.adapters.gesture:
        available: tuple[RendererCapability, ...] | None = ()
        failure: str | None = "gesture renderer adapter is not composed"
        unknown = False
    else:
        failure = None
        unknown = False
        try:
            available = tuple(
                composition.gestures.available_renderers(
                    core_id=participant.core_id,
                )
            )
        except Exception:
            available = None
            unknown = True
    lines: list[RendererReadout] = []
    for renderer in RendererCapability:
        if renderer is RendererCapability.TEXT:
            lines.append(
                RendererReadout(renderer.value, Availability.AVAILABLE)
            )
        elif unknown:
            lines.append(
                RendererReadout(
                    renderer.value,
                    Availability.UNKNOWN,
                    "renderer availability could not be read",
                )
            )
        elif available is not None and renderer in available:
            lines.append(
                RendererReadout(renderer.value, Availability.AVAILABLE)
            )
        else:
            lines.append(
                RendererReadout(
                    renderer.value,
                    Availability.UNAVAILABLE,
                    failure or f"renderer {renderer.value!r} is not installed",
                )
            )
    return tuple(lines)


def _core_readout(
    participant: UniversalParticipant,
    composition: UniversalComposition,
) -> CoreReadout:
    return CoreReadout(
        core_number=participant.core_number,
        core_id=str(participant.core_id),
        display_name=participant.display_name,
        design_only=participant.design_only,
        activated=False,
        runtime_state="INERT",
        platform_authority=False,
        leadership_role=None,
        capabilities=_capabilities(participant),
        renderers=_renderers(participant, composition),
    )


def _unavailable_inventories(
    composition: UniversalComposition, availability: Availability
) -> tuple[InventoryReadout, ...]:
    return tuple(
        InventoryReadout(str(participant.core_id), availability)
        for participant in composition.roster.participants
    )


def _wardrobe_readout(
    composition: UniversalComposition,
) -> WardrobeReadout:
    if not composition.adapters.wardrobe:
        return WardrobeReadout(
            Availability.UNAVAILABLE,
            inventories=_unavailable_inventories(
                composition, Availability.UNAVAILABLE
            ),
        )
    try:
        summary = composition.wardrobe.catalog_summary()
    except Exception:
        return WardrobeReadout(
            Availability.UNKNOWN,
            inventories=_unavailable_inventories(composition, Availability.UNKNOWN),
        )
    if summary is None:
        return WardrobeReadout(
            Availability.UNAVAILABLE,
            inventories=_unavailable_inventories(
                composition, Availability.UNAVAILABLE
            ),
        )
    inventories: list[InventoryReadout] = []
    for participant in composition.roster.participants:
        try:
            inventory = composition.wardrobe.inventory_summary(
                core_id=participant.core_id,
            )
        except Exception:
            inventories.append(
                InventoryReadout(str(participant.core_id), Availability.UNKNOWN)
            )
            continue
        if inventory is None:
            inventories.append(
                InventoryReadout(
                    str(participant.core_id), Availability.UNAVAILABLE,
                )
            )
            continue
        inventories.append(
            InventoryReadout(
                core_id=str(inventory.core_id),
                availability=Availability.AVAILABLE,
                owned_count=inventory.owned_count,
                held_count=inventory.held_count,
                loaned_count=inventory.loaned_count,
                equipped_count=inventory.equipped_count,
            )
        )
    return WardrobeReadout(
        availability=Availability.AVAILABLE,
        total_designs=summary.total_designs,
        clothing_designs=summary.clothing_designs,
        armor_designs=summary.armor_designs,
        public_designs=summary.public_designs,
        private_designs=summary.private_designs,
        adult_designs=summary.adult_designs,
        inventories=tuple(inventories),
    )


def _governance_readout(
    composition: UniversalComposition, now: datetime
) -> GovernanceReadout:
    if not composition.adapters.governance:
        return GovernanceReadout(
            Availability.UNAVAILABLE, Availability.UNAVAILABLE,
        )
    try:
        groups = composition.governance.groups()
    except Exception:
        return GovernanceReadout(Availability.UNKNOWN, Availability.UNKNOWN)
    if groups is None:
        return GovernanceReadout(
            Availability.UNAVAILABLE, Availability.UNAVAILABLE,
        )
    try:
        terms = composition.governance.coordinator_terms()
    except Exception:
        terms = None
        terms_availability = Availability.UNKNOWN
    else:
        terms_availability = (
            Availability.UNAVAILABLE if terms is None else Availability.AVAILABLE
        )
    terms_by_group: Mapping[object, object] = {}
    if terms is not None:
        terms_by_group = {term.group_id: term for term in terms}
    summaries: list[GovernanceGroupReadout] = []
    for group in groups:
        term = terms_by_group.get(group.group_id)
        term_active = None
        if term is not None:
            term_active = bool(term.is_active(now))
        summaries.append(
            GovernanceGroupReadout(
                group_id=str(group.group_id),
                lifecycle=group.lifecycle.value,
                member_count=len(group.members),
                active_member_count=len(group.active_member_ids()),
                leaderless=group.is_leaderless(),
                coordinator_term_active=term_active,
            )
        )
    active_groups = sum(
        1 for group in groups if group.lifecycle.value == "active"
    )
    term_count = None if terms is None else len(terms)
    active_terms = (
        None
        if terms is None
        else sum(1 for term in terms if term.is_active(now))
    )
    return GovernanceReadout(
        availability=Availability.AVAILABLE,
        terms_availability=terms_availability,
        group_count=len(groups),
        active_group_count=active_groups,
        coordinator_term_count=term_count,
        active_coordinator_term_count=active_terms,
        groups=tuple(summaries),
    )


def build_universal_readout(
    composition: UniversalComposition, *, now: datetime | None = None
) -> UniversalReadout:
    """Project the composition without mutating any adapter or state."""
    if not isinstance(composition, UniversalComposition):
        raise TypeError("composition must be a UniversalComposition")
    timestamp = composition.now() if now is None else now
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return UniversalReadout(
        generated_at=timestamp.isoformat(),
        stop_status=composition.stop_status(),
        adapters=composition.adapters,
        cores=tuple(
            _core_readout(participant, composition)
            for participant in composition.roster.participants
        ),
        wardrobe=_wardrobe_readout(composition),
        governance=_governance_readout(composition, timestamp),
    )


__all__ = [
    "Availability",
    "CapabilityReadout",
    "CoreReadout",
    "GovernanceGroupReadout",
    "GovernanceReadout",
    "InventoryReadout",
    "READOUT_SCHEMA",
    "RendererReadout",
    "UniversalReadout",
    "WardrobeReadout",
    "build_universal_readout",
]
