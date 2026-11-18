"""Narrow adapters from existing Platform seams to the universal facade.

These adapters are optional and read-only where possible.  They translate an
existing chat engine, wardrobe catalog, inventory source, governance query or
SAFE operator STOP into the structural protocols defined by
``sofia.platform.social.universal``.  They do not create a second writer, copy
protected state, infer consent from chat text or grant any authority.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable
from uuid import UUID

from sofia.modules.avatar.inventory_contract import (
    CustodyKind,
    ItemInstance,
    TransferDenied,
    TransferOffer,
    TransferReceipt,
)
from sofia.modules.avatar.wardrobe_equipment import (
    WardrobeDesign,
    WardrobePrivacy,
)
from sofia.platform.chat.contracts import ChatActor, MembershipStatus
from sofia.platform.social.governance.contracts import (
    CoordinatorTerm,
    GovernanceGroup,
)
from sofia.platform.social.universal import (
    InventorySummary,
    StopStatus,
    UniversalAction,
    WardrobeCatalogSummary,
)


class OperatorStopAuthority:
    """Expose the canonical SAFE operator STOP without copying its state."""

    def __init__(self, store) -> None:
        current = getattr(store, "current", None)
        if not callable(current):
            raise TypeError("store must expose current()")
        self._store = store

    def stop_status(self) -> StopStatus:
        try:
            state = self._store.current()
            active = getattr(state, "active", None)
        except Exception:
            return StopStatus.UNKNOWN
        if type(active) is not bool:
            return StopStatus.UNKNOWN
        return StopStatus.ACTIVE if active else StopStatus.INACTIVE


class ChatEngineAudienceProjection:
    """Read a viewer's own room membership through the chat engine.

    The projection authenticates the viewer as its enrolled Core actor.  It
    does not substitute the Platform owner, so private group membership is
    never widened by management access.
    """

    def __init__(self, engine) -> None:
        for name in ("core_identity", "memberships", "rooms"):
            if not callable(getattr(engine, name, None)):
                raise TypeError(f"engine must expose {name}()")
        self._engine = engine

    def _actor(self, core_id: UUID) -> ChatActor | None:
        identity = self._engine.core_identity(str(core_id))
        if identity is None:
            return None
        try:
            return ChatActor.core(identity)
        except (TypeError, ValueError):
            return None

    def room_members(
        self, *, viewer_core_id: UUID, room_id: str
    ) -> tuple[UUID, ...] | None:
        actor = self._actor(viewer_core_id)
        if actor is None:
            return None
        try:
            memberships = self._engine.memberships(actor, room_id)
        except (PermissionError, LookupError, KeyError, TypeError, ValueError):
            return None
        return tuple(
            UUID(member.core_id)
            for member in memberships
            if member.status is MembershipStatus.ACTIVE
        )

    def visible_room_ids(self, *, viewer_core_id: UUID) -> tuple[str, ...] | None:
        actor = self._actor(viewer_core_id)
        if actor is None:
            return None
        try:
            rooms = self._engine.rooms(actor)
        except (PermissionError, LookupError, KeyError, TypeError, ValueError):
            return None
        return tuple(room.room_id for room in rooms)


class CallableChatProjection:
    """Adapt host-provided read callables to the audience projection seam."""

    def __init__(
        self,
        room_members: Callable[[UUID, str], tuple[UUID, ...] | None],
        visible_room_ids: Callable[[UUID], tuple[str, ...] | None],
    ) -> None:
        if not callable(room_members) or not callable(visible_room_ids):
            raise TypeError("chat projection callbacks must be callable")
        self._room_members = room_members
        self._visible_room_ids = visible_room_ids

    def room_members(
        self, *, viewer_core_id: UUID, room_id: str
    ) -> tuple[UUID, ...] | None:
        return self._room_members(viewer_core_id, room_id)

    def visible_room_ids(self, *, viewer_core_id: UUID) -> tuple[str, ...] | None:
        return self._visible_room_ids(viewer_core_id)


class IterableWardrobeCatalog:
    """Summarize a catalog and inventory source without exposing item details."""

    def __init__(
        self,
        designs: Iterable[WardrobeDesign] | Callable[[], Iterable[WardrobeDesign]],
        inventory: (
            Callable[[UUID], Iterable[ItemInstance] | None] | None
        ) = None,
    ) -> None:
        if callable(designs):
            self._designs = designs
        else:
            snapshot = tuple(designs)
            self._designs = lambda: snapshot
        if inventory is not None and not callable(inventory):
            raise TypeError("inventory must be callable or None")
        self._inventory = inventory

    def catalog_summary(self) -> WardrobeCatalogSummary | None:
        designs = tuple(self._designs())
        for design in designs:
            if not isinstance(design, WardrobeDesign):
                raise TypeError("catalog must contain WardrobeDesign values")
        armor = sum(1 for design in designs if design.is_armor)
        return WardrobeCatalogSummary(
            total_designs=len(designs),
            clothing_designs=len(designs) - armor,
            armor_designs=armor,
            public_designs=sum(
                1 for design in designs
                if design.privacy is WardrobePrivacy.PUBLIC
            ),
            private_designs=sum(
                1 for design in designs
                if design.privacy is WardrobePrivacy.PRIVATE
            ),
            adult_designs=sum(
                1 for design in designs
                if design.privacy is WardrobePrivacy.ADULT
            ),
        )

    def inventory_summary(self, *, core_id: UUID) -> InventorySummary | None:
        if self._inventory is None:
            return None
        items = self._inventory(core_id)
        if items is None:
            return None
        materialized = tuple(items)
        for item in materialized:
            if not isinstance(item, ItemInstance):
                raise TypeError("inventory must contain ItemInstance values")
        return InventorySummary(
            core_id=core_id,
            owned_count=sum(
                1 for item in materialized if item.owner_core_id == core_id
            ),
            held_count=sum(
                1 for item in materialized if item.holder_core_id == core_id
            ),
            loaned_count=sum(
                1 for item in materialized
                if item.owner_core_id == core_id
                and item.custody is CustodyKind.LOANED
            ),
            equipped_count=sum(
                1 for item in materialized if item.equipped_by_core_id == core_id
            ),
        )


class CallableGovernanceQuery:
    """Adapt read-only governance callables; ballots are never projected."""

    def __init__(
        self,
        groups: Callable[[], tuple[GovernanceGroup, ...] | None],
        coordinator_terms: Callable[[], tuple[CoordinatorTerm, ...] | None],
    ) -> None:
        if not callable(groups) or not callable(coordinator_terms):
            raise TypeError("governance query callbacks must be callable")
        self._groups = groups
        self._coordinator_terms = coordinator_terms

    def groups(self) -> tuple[GovernanceGroup, ...] | None:
        return self._groups()

    def coordinator_terms(self) -> tuple[CoordinatorTerm, ...] | None:
        return self._coordinator_terms()


class CallbackAuthorization:
    """Adapt a host callback with the exact universal authorization signature."""

    def __init__(self, authorize: Callable[..., bool]) -> None:
        if not callable(authorize):
            raise TypeError("authorize must be callable")
        self._authorize = authorize

    def authorize(
        self,
        *,
        core_id: UUID,
        action: UniversalAction,
        target_core_id: UUID | None = None,
        room_id: str | None = None,
        audience_id: str | None = None,
    ) -> bool:
        result = self._authorize(
            core_id=core_id,
            action=action,
            target_core_id=target_core_id,
            room_id=room_id,
            audience_id=audience_id,
        )
        return result is True


class StaticAllowListAuthorization:
    """Explicitly scoped allow-list for tests or a deliberately narrow host."""

    def __init__(
        self,
        allowed: set[tuple[UUID, UniversalAction]] | None = None,
    ) -> None:
        self._allowed = set() if allowed is None else set(allowed)

    def authorize(
        self,
        *,
        core_id: UUID,
        action: UniversalAction,
        target_core_id: UUID | None = None,
        room_id: str | None = None,
        audience_id: str | None = None,
    ) -> bool:
        return (core_id, action) in self._allowed


class CallbackInventoryTransfer:
    """Adapt host transaction callables; missing callbacks deny the transfer."""

    def __init__(
        self,
        offer: Callable[[TransferOffer], TransferReceipt] | None = None,
        accept: (
            Callable[..., TransferReceipt] | None
        ) = None,
    ) -> None:
        if offer is not None and not callable(offer):
            raise TypeError("offer must be callable or None")
        if accept is not None and not callable(accept):
            raise TypeError("accept must be callable or None")
        self._offer = offer
        self._accept = accept

    def offer(self, offer: TransferOffer) -> TransferReceipt:
        if self._offer is None:
            raise TransferDenied("no inventory transfer offer callback is composed")
        return self._offer(offer)

    def accept(
        self, *, offer_id: UUID, actor_core_id: UUID, now: datetime
    ) -> TransferReceipt:
        if self._accept is None:
            raise TransferDenied("no inventory transfer accept callback is composed")
        return self._accept(
            offer_id=offer_id, actor_core_id=actor_core_id, now=now,
        )


__all__ = [
    "CallbackAuthorization",
    "CallbackInventoryTransfer",
    "CallableChatProjection",
    "CallableGovernanceQuery",
    "ChatEngineAudienceProjection",
    "IterableWardrobeCatalog",
    "OperatorStopAuthority",
    "StaticAllowListAuthorization",
]
