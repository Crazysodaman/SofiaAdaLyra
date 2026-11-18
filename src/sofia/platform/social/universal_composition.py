"""Concrete adapters composing universal Core slices behind inert seams.

The integration facade in :mod:`sofia.platform.social.universal` accepts narrow
protocols.  This module binds the real 2026-11-18 slices to those protocols:

* gesture definitions and body predicates (SDK/Core gesture slice);
* shared wardrobe catalog, wearer fit and Vera armor designs;
* canonical per-Core inventory and transfer transactions;
* voluntary governance read queries;
* existing chat membership projections.

Nothing here activates a Core, allocates an identity, grants Platform authority,
starts a service, or fabricates a renderer/transfer receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping
from uuid import UUID, uuid4

from sofia.modules.avatar.inventory import InventoryEngine
from sofia.modules.avatar.inventory_contract import (
    CustodyKind,
    OfferStatus,
    TransferOffer,
    TransferReceipt,
)
from sofia.modules.avatar.wardrobe_equipment import (
    GarmentClass,
    WardrobeDesign,
    WardrobePrivacy,
)
from sofia.modules.avatar.wardrobe_equipment_catalog import EquipmentDesignRegistry
from sofia.platform.chat.contracts import ActorKind, ChatActor
from sofia.platform.social.governance.contracts import (
    CoordinatorTerm,
    GovernanceGroup,
)
from sofia.platform.social.governance.store import GovernanceStore
from sofia.platform.social.universal import (
    AdapterPresence,
    AudienceKind,
    DenyAllAuthorization,
    DenyAllInventoryTransfer,
    GestureRequest,
    InventorySummary,
    StopStatus,
    UnavailableChatProjection,
    UnavailableGovernanceQuery,
    UniversalComposition,
    UniversalCoreRoster,
    WardrobeCatalogSummary,
    build_universal_roster,
    coerce_stop_authority,
)
from sofia.sdk.core_capabilities import (
    BodyCapabilityProfile,
    CapabilityFamily,
    CapabilityOutcome,
    CapabilityReceipt,
    CoreCapabilityContract,
    RendererCapability,
    unavailable_receipt,
)
from sofia.sdk.gesture_contract import (
    GestureDefinition,
    GesturePrivacy,
    resolve_gesture_compatibility,
)

DEFAULT_CLOCK = lambda: datetime.now(timezone.utc)  # noqa: E731


def _gesture_privacy(request: GestureRequest, adult_audience_ids: frozenset[str]) -> GesturePrivacy:
    if request.audience.audience_id in adult_audience_ids:
        return GesturePrivacy.ADULT_PRIVATE
    if request.audience.kind is AudienceKind.GENERAL:
        return GesturePrivacy.PUBLIC
    return GesturePrivacy.PRIVATE


class CatalogGestureService:
    """Resolve reviewed gesture definitions against declared bodies/renderers.

    A callback is required before any ``RENDERED`` claim.  Without installed
    renderer evidence the adapter returns ``UNAVAILABLE`` instead of pretending
    a typed or described gesture was played back.
    """

    def __init__(
        self,
        *,
        definitions: Iterable[GestureDefinition],
        body_profiles: Mapping[UUID, BodyCapabilityProfile],
        capabilities: Mapping[UUID, CoreCapabilityContract],
        render: Callable[[GestureRequest, GestureDefinition], str | None] | None = None,
        adult_audience_ids: Iterable[str] = (),
    ) -> None:
        values = tuple(definitions)
        if any(not isinstance(item, GestureDefinition) for item in values):
            raise TypeError("definitions must contain GestureDefinition values")
        self._definitions = values
        by_key: dict[str, GestureDefinition] = {}
        for definition in values:
            for key in (definition.gesture_id, definition.canonical_ref, *definition.aliases):
                existing = by_key.get(key)
                if existing is not None and existing != definition:
                    raise ValueError(f"ambiguous gesture key: {key}")
                by_key[key] = definition
        self._by_key = by_key
        self._body_profiles = dict(body_profiles)
        self._capabilities = dict(capabilities)
        self._render = render
        self._adult_audience_ids = frozenset(adult_audience_ids)

    @property
    def definitions(self) -> tuple[GestureDefinition, ...]:
        return self._definitions

    def available_renderers(self, *, core_id: UUID) -> tuple[RendererCapability, ...]:
        contract = self._capabilities.get(core_id)
        return () if contract is None else contract.renderers

    def submit(self, request: GestureRequest) -> CapabilityReceipt:
        if not isinstance(request, GestureRequest):
            raise TypeError("request must be a GestureRequest")
        definition = self._by_key.get(request.gesture_id)
        if definition is None:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason=f"unknown gesture definition: {request.gesture_id}",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        body = self._body_profiles.get(request.core_id)
        if body is None:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="declared body/rig profile is unavailable",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        renderers = self.available_renderers(core_id=request.core_id)
        compatibility = resolve_gesture_compatibility(
            definition,
            body=body,
            renderers=renderers,
            audience=_gesture_privacy(request, self._adult_audience_ids),
        )
        if not compatibility.accepted:
            outcome = (
                CapabilityOutcome.DECLINED
                if compatibility.status.value == "privacy_unavailable"
                else CapabilityOutcome.UNAVAILABLE
            )
            return CapabilityReceipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                outcome=outcome,
                reason=compatibility.reason,
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if request.renderer not in definition.renderer_capabilities:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason=(
                    f"gesture {definition.canonical_ref} does not declare renderer "
                    f"{request.renderer.value!r}"
                ),
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        if self._render is None:
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="no authenticated renderer playback seam is composed",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        evidence = self._render(request, definition)
        if not isinstance(evidence, str) or not evidence.strip():
            return unavailable_receipt(
                receipt_id=request.receipt_id,
                core_id=request.core_id,
                family=CapabilityFamily.GESTURE,
                reason="renderer returned no playback evidence",
                evidence_ref=request.evidence_ref,
                occurred_at=request.occurred_at,
                renderer=request.renderer,
            )
        return CapabilityReceipt(
            receipt_id=request.receipt_id,
            core_id=request.core_id,
            family=CapabilityFamily.GESTURE,
            outcome=CapabilityOutcome.RENDERED,
            reason="authenticated renderer returned playback evidence",
            evidence_ref=request.evidence_ref,
            occurred_at=request.occurred_at,
            renderer=request.renderer,
            asset_ref=evidence,
        )


class CatalogWardrobeService:
    """Shared catalog counts plus per-Core inventory counts; no item leakage."""

    def __init__(
        self,
        designs: Iterable[WardrobeDesign],
        *,
        inventory: InventoryEngine | None = None,
    ) -> None:
        self._registry = EquipmentDesignRegistry(designs)
        self._inventory = inventory

    @property
    def designs(self) -> tuple[WardrobeDesign, ...]:
        return self._registry.designs

    def catalog_summary(self) -> WardrobeCatalogSummary:
        designs = self._registry.designs
        clothing = sum(1 for item in designs if item.garment_class is GarmentClass.CLOTHING)
        armor = len(designs) - clothing
        public = sum(1 for item in designs if item.privacy is WardrobePrivacy.PUBLIC)
        private = sum(1 for item in designs if item.privacy is WardrobePrivacy.PRIVATE)
        adult = sum(1 for item in designs if item.privacy is WardrobePrivacy.ADULT)
        return WardrobeCatalogSummary(
            total_designs=len(designs),
            clothing_designs=clothing,
            armor_designs=armor,
            public_designs=public,
            private_designs=private,
            adult_designs=adult,
        )

    def inventory_summary(self, *, core_id: UUID) -> InventorySummary | None:
        if self._inventory is None:
            return None
        items = self._inventory.inventory(core_id, include_private=True)
        return InventorySummary(
            core_id=core_id,
            owned_count=sum(1 for item in items if item.owner_core_id == core_id),
            held_count=sum(1 for item in items if item.holder_core_id == core_id),
            loaned_count=sum(
                1 for item in items
                if item.custody is CustodyKind.LOANED and item.holder_core_id == core_id
            ),
            equipped_count=sum(
                1 for item in items if item.equipped_by_core_id == core_id
            ),
        )


class EngineInventoryTransferService:
    """Adapt the canonical InventoryEngine to the facade's receipt protocol."""

    def __init__(self, engine: InventoryEngine) -> None:
        if not isinstance(engine, InventoryEngine):
            raise TypeError("engine must be InventoryEngine")
        self._engine = engine

    def offer(self, offer: TransferOffer) -> TransferReceipt:
        if not isinstance(offer, TransferOffer):
            raise TypeError("offer must be a TransferOffer")
        ttl = int((offer.expires_at - offer.created_at).total_seconds())
        created = self._engine.create_offer(
            offer.operation,
            offer.sender_core_id,
            offer.recipient_core_id,
            item_instance_ids=offer.item_instance_ids,
            reciprocal_item_instance_ids=offer.reciprocal_item_instance_ids,
            expected_items=offer.expected_items,
            design_ids=offer.design_ids,
            idempotency_key=offer.idempotency_key,
            ttl_seconds=ttl,
            note=offer.note,
            at=offer.created_at,
            offer_id=offer.offer_id,
        )
        return TransferReceipt(
            receipt_id=uuid4(),
            offer_id=created.offer_id,
            operation=created.operation,
            status=OfferStatus.PENDING,
            actor_core_id=created.sender_core_id,
            item_instance_ids=created.item_instance_ids + created.reciprocal_item_instance_ids,
            resulting_items=created.expected_items,
            idempotency_key=created.idempotency_key,
            occurred_at=created.created_at,
            evidence_ref=f"transfer-offer-{created.offer_id}",
            reason="offer created and remains inert until bilateral acceptance",
        )

    def accept(
        self, *, offer_id: UUID, actor_core_id: UUID, now: datetime
    ) -> TransferReceipt:
        return self._engine.accept(offer_id, actor_core_id, at=now)


class StoreGovernanceQuery:
    """Read-only governance projection over the canonical governance store."""

    def __init__(self, store: GovernanceStore) -> None:
        if not isinstance(store, GovernanceStore):
            raise TypeError("store must be GovernanceStore")
        self._store = store

    def groups(self) -> tuple[GovernanceGroup, ...] | None:
        return self._store.list_groups()

    def coordinator_terms(self) -> tuple[CoordinatorTerm, ...] | None:
        return self._store.active_terms()


class ChatEngineAudienceProjection:
    """Project room membership through an authenticated Core chat actor."""

    def __init__(self, engine: object) -> None:
        if not callable(getattr(engine, "core_identity", None)):
            raise TypeError("chat engine must expose core_identity")
        if not callable(getattr(engine, "memberships", None)):
            raise TypeError("chat engine must expose memberships")
        self._engine = engine

    def _actor(self, viewer_core_id: UUID):
        identity = self._engine.core_identity(str(viewer_core_id))
        if identity is None:
            return None
        return ChatActor.core(identity)

    def room_members(
        self, *, viewer_core_id: UUID, room_id: str
    ) -> tuple[UUID, ...] | None:
        actor = self._actor(viewer_core_id)
        if actor is None:
            return None
        try:
            memberships = self._engine.memberships(actor, room_id)
        except Exception:
            return None
        return tuple(
            UUID(membership.core_id)
            for membership in memberships
            if membership.is_active and membership.member_kind is ActorKind.CORE
        )

    def visible_room_ids(self, *, viewer_core_id: UUID) -> tuple[str, ...] | None:
        actor = self._actor(viewer_core_id)
        if actor is None:
            return None
        try:
            rooms = self._engine.rooms(actor)
        except Exception:
            return None
        return tuple(room.room_id for room in rooms)


def compose_universal_core_services(
    *,
    core_ids: Mapping[int, UUID],
    gesture_definitions: Iterable[GestureDefinition],
    body_profiles: Mapping[UUID, BodyCapabilityProfile],
    designs: Iterable[WardrobeDesign],
    inventory: InventoryEngine | None = None,
    governance_store: GovernanceStore | None = None,
    chat_engine: object | None = None,
    render_gesture: Callable[[GestureRequest, GestureDefinition], str | None] | None = None,
    adult_audience_ids: Iterable[str] = (),
    stop: object | None = None,
    authorization: object | None = None,
    clock: Callable[[], datetime] | None = None,
    resource_root=None,
    definition_digests: Mapping[int, str] | None = None,
) -> UniversalComposition:
    """Bind real slices to the inert universal facade.

    Every omitted seam stays unavailable/deny-all.  Supplying an inventory or
    governance store does not start, migrate or activate anything.
    """
    roster = build_universal_roster(
        core_ids,
        resource_root=resource_root,
        definition_digests=definition_digests,
    )
    capabilities = {item.core_id: item.capabilities for item in roster.participants}
    gestures = CatalogGestureService(
        definitions=gesture_definitions,
        body_profiles=body_profiles,
        capabilities=capabilities,
        render=render_gesture,
        adult_audience_ids=adult_audience_ids,
    )
    wardrobe = CatalogWardrobeService(designs, inventory=inventory)
    inventory_service = (
        DenyAllInventoryTransfer()
        if inventory is None
        else EngineInventoryTransferService(inventory)
    )
    governance = (
        UnavailableGovernanceQuery()
        if governance_store is None
        else StoreGovernanceQuery(governance_store)
    )
    chat = (
        UnavailableChatProjection()
        if chat_engine is None
        else ChatEngineAudienceProjection(chat_engine)
    )
    return UniversalComposition(
        roster=roster,
        gestures=gestures,
        wardrobe=wardrobe,
        inventory=inventory_service,
        governance=governance,
        chat=chat,
        stop=coerce_stop_authority(stop),
        authorization=authorization or DenyAllAuthorization(),
        clock=clock or DEFAULT_CLOCK,
        adapters=AdapterPresence(
            gesture=True,
            wardrobe=True,
            inventory=inventory is not None,
            governance=governance_store is not None,
            chat=chat_engine is not None,
            stop=stop is not None,
            authorization=authorization is not None,
        ),
    )


__all__ = [
    "CatalogGestureService",
    "CatalogWardrobeService",
    "ChatEngineAudienceProjection",
    "EngineInventoryTransferService",
    "StoreGovernanceQuery",
    "compose_universal_core_services",
]
