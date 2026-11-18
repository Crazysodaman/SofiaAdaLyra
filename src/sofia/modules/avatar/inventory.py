"""Per-Core wardrobe inventory, bilateral transfer and outfit engine.

The engine treats a catalog design as shared metadata and an item instance as
the one owned virtual object.  Lending never clones an instance.  Every
consequential mutation runs through one canonical SQLite immediate transaction
owned by :class:`InventoryStore`; this module never opens a second writer.

No function here claims an installed renderer, physical fit or live transfer.
A renderer callback is an explicit compensation seam: ownership is committed
first, the renderer must return evidence, and an unknown or failed renderer
restores the previous ownership/custody state and records a FAILED receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Callable, Iterable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .inventory_contract import (
    CustodyKind,
    InventoryError,
    ItemInstance,
    ItemRevision,
    NotItemHolder,
    NotItemOwner,
    OfferExpired,
    OfferNotFound,
    OfferStatus,
    OutfitSelection,
    StaleItemRevision,
    TERMINAL_OFFER_STATUSES,
    TransferConflict,
    TransferDenied,
    TransferOffer,
    TransferOperation,
    TransferReceipt,
    assert_current_revisions,
    assert_holder,
    assert_not_wearing,
    assert_title,
    item_revisions,
)
from .inventory_store import InventoryStore
from .wardrobe_equipment import (
    ArmorDecision,
    ArmorDecisionStatus,
    EquippedItem,
    WardrobeDesign,
    WardrobePrivacy,
    atomic_disassembly_plan,
    validate_armor_equip,
    validate_armor_unequip,
)

_RENDER_GUARD_SCHEMA = "aegis.avatar.inventory.render_guard.v1"
_DEFAULT_LOAN = timedelta(days=30)
_MAX_OFFER_LIFETIME = timedelta(days=7)
_OFFER_OPERATIONS = frozenset({
    TransferOperation.OFFER,
    TransferOperation.LEND,
    TransferOperation.RETURN,
    TransferOperation.GIFT,
    TransferOperation.TRADE,
    TransferOperation.SWAP_OUTFIT,
    TransferOperation.COPY_DESIGN,
    TransferOperation.CUSTOMIZE,
})
_RECIPROCAL_OPERATIONS = frozenset({
    TransferOperation.TRADE,
    TransferOperation.SWAP_OUTFIT,
})
_DESIGN_OPERATIONS = frozenset({
    TransferOperation.COPY_DESIGN,
    TransferOperation.CUSTOMIZE,
})


class EquipDenied(TransferDenied):
    """The design/body/equipment evidence does not permit the outfit change."""


class InventoryUnavailable(RuntimeError):
    """The requested effect cannot be claimed from available evidence."""


class InventoryRenderFailed(RuntimeError):
    """A downstream renderer failed or returned no evidence."""


@dataclass(frozen=True, slots=True)
class PublicInventoryItem:
    item_instance_id: UUID
    design_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class PublicInventory:
    core_id: UUID
    items: tuple[PublicInventoryItem, ...]
    redacted_count: int

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "aegis.avatar.inventory.public_view.v1",
            "core_id": str(self.core_id),
            "items": [
                {
                    "item_instance_id": str(item.item_instance_id),
                    "design_id": item.design_id,
                    "display_name": item.display_name,
                }
                for item in self.items
            ],
            "redacted_count": self.redacted_count,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InventoryError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _item_snapshot(item: ItemInstance) -> dict[str, object]:
    return {
        "item_instance_id": str(item.item_instance_id),
        "design_id": item.design_id,
        "design_version": item.design_version,
        "owner_core_id": str(item.owner_core_id),
        "holder_core_id": str(item.holder_core_id),
        "custody": item.custody.value,
        "revision": item.revision,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "transferable": item.transferable,
        "private_to_owner": item.private_to_owner,
        "loan_due_at": None if item.loan_due_at is None else item.loan_due_at.isoformat(),
        "recall_requested": item.recall_requested,
        "equipped_by_core_id": (
            None if item.equipped_by_core_id is None else str(item.equipped_by_core_id)
        ),
    }


def _item_from_snapshot(payload: Mapping[str, object]) -> ItemInstance:
    return ItemInstance(
        item_instance_id=UUID(str(payload["item_instance_id"])),
        design_id=str(payload["design_id"]),
        design_version=int(payload["design_version"]),
        owner_core_id=UUID(str(payload["owner_core_id"])),
        holder_core_id=UUID(str(payload["holder_core_id"])),
        custody=CustodyKind(str(payload["custody"])),
        revision=int(payload["revision"]),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        transferable=bool(payload["transferable"]),
        private_to_owner=bool(payload["private_to_owner"]),
        loan_due_at=(
            None if payload["loan_due_at"] is None
            else datetime.fromisoformat(str(payload["loan_due_at"]))
        ),
        recall_requested=bool(payload["recall_requested"]),
        equipped_by_core_id=(
            None if payload["equipped_by_core_id"] is None
            else UUID(str(payload["equipped_by_core_id"]))
        ),
    )


class InventoryEngine:
    """Ownership, custody, transfer, outfit and armor-dependency service."""

    def __init__(
        self,
        store: InventoryStore,
        designs: Mapping[str, WardrobeDesign] | None = None,
        *,
        reconcile_on_start: bool = True,
    ) -> None:
        if not isinstance(store, InventoryStore):
            raise TypeError("store must be InventoryStore")
        self._store = store
        self._designs: Mapping[str, WardrobeDesign] = (
            {} if designs is None else dict(designs)
        )
        if reconcile_on_start:
            self.reconcile()

    @property
    def store(self) -> InventoryStore:
        return self._store

    # -- catalog / instance registration -----------------------------------

    def design(self, design_id: str, version: int | None = None) -> WardrobeDesign:
        try:
            design = self._designs[design_id]
        except KeyError as exc:
            raise InventoryUnavailable(
                f"catalog design {design_id!r} is not available in this runtime"
            ) from exc
        if version is not None and design.version != version:
            raise InventoryUnavailable(
                f"catalog design {design_id!r} version {design.version} does not "
                f"match requested version {version}"
            )
        return design

    def mint(
        self,
        design_id: str,
        owner_core_id: UUID,
        *,
        holder_core_id: UUID | None = None,
        custody: CustodyKind | None = None,
        transferable: bool = True,
        private_to_owner: bool | None = None,
        loan_due_at: datetime | None = None,
        item_instance_id: UUID | None = None,
        at: datetime | None = None,
    ) -> ItemInstance:
        design = self.design(design_id)
        now = _utc(at) if at is not None else _now()
        holder = owner_core_id if holder_core_id is None else holder_core_id
        if custody is None:
            custody = CustodyKind.OWNED if holder == owner_core_id else CustodyKind.LOANED
        if private_to_owner is None:
            private_to_owner = design.privacy is not WardrobePrivacy.PUBLIC
        item = ItemInstance(
            item_instance_id=uuid4() if item_instance_id is None else item_instance_id,
            design_id=design.design_id,
            design_version=design.version,
            owner_core_id=owner_core_id,
            holder_core_id=holder,
            custody=custody,
            revision=1,
            created_at=now,
            updated_at=now,
            transferable=transferable,
            private_to_owner=private_to_owner,
            loan_due_at=loan_due_at,
            recall_requested=False,
            equipped_by_core_id=None,
        )
        with self._store.transaction() as db:
            self._store.insert_item(db, item)
            self._store.append_audit(
                db,
                actor_core_id=owner_core_id,
                event_type="aegis.wardrobe.inventory.mint",
                payload={"item_instance_id": str(item.item_instance_id), "design_id": design.design_id},
                occurred_at=now,
            )
        return item

    def register(self, item: ItemInstance) -> ItemInstance:
        if not isinstance(item, ItemInstance):
            raise TypeError("item must be ItemInstance")
        self.design(item.design_id, item.design_version)
        with self._store.transaction() as db:
            if self._store.get_item(db, item.item_instance_id) is not None:
                raise TransferConflict(
                    f"item instance {item.item_instance_id} already exists"
                )
            self._store.insert_item(db, item)
            self._store.append_audit(
                db,
                actor_core_id=item.owner_core_id,
                event_type="aegis.wardrobe.inventory.register",
                payload={"item_instance_id": str(item.item_instance_id)},
                occurred_at=item.updated_at,
            )
        return item

    def item(self, item_instance_id: UUID) -> ItemInstance:
        with self._store.reader() as db:
            item = self._store.get_item(db, item_instance_id)
        if item is None:
            raise KeyError(f"item instance {item_instance_id} was not found")
        return item

    def inventory(
        self, core_id: UUID, *, include_private: bool = True
    ) -> tuple[ItemInstance, ...]:
        with self._store.reader() as db:
            items = self._store.list_items(db, core_id=core_id)
        if include_private:
            return items
        return tuple(
            item for item in items if not self._is_restricted(item)
        )

    def public_view(self, core_id: UUID) -> PublicInventory:
        """Return only metadata safe for a general/guest audience.

        Restricted designs are omitted entirely rather than replaced with a
        guess.  Their count is reported so absence is observable, not hidden.
        """
        with self._store.reader() as db:
            items = self._store.list_items(db, core_id=core_id)
        visible: list[PublicInventoryItem] = []
        redacted = 0
        for item in items:
            if self._is_restricted(item):
                redacted += 1
                continue
            design = self._designs.get(item.design_id)
            if design is None:
                redacted += 1
                continue
            visible.append(
                PublicInventoryItem(
                    item_instance_id=item.item_instance_id,
                    design_id=design.design_id,
                    display_name=design.name,
                )
            )
        return PublicInventory(core_id=core_id, items=tuple(visible), redacted_count=redacted)

    def _is_restricted(self, item: ItemInstance) -> bool:
        if item.private_to_owner:
            return True
        design = self._designs.get(item.design_id)
        if design is None:
            return True
        return design.privacy is not WardrobePrivacy.PUBLIC

    # -- offers ------------------------------------------------------------

    def create_offer(
        self,
        operation: TransferOperation,
        sender_core_id: UUID,
        recipient_core_id: UUID,
        *,
        item_instance_ids: Iterable[UUID] = (),
        reciprocal_item_instance_ids: Iterable[UUID] = (),
        expected_items: Iterable[ItemRevision] = (),
        design_ids: Iterable[str] = (),
        idempotency_key: str,
        ttl_seconds: int = 3600,
        note: str | None = None,
        at: datetime | None = None,
    ) -> TransferOffer:
        if operation not in _OFFER_OPERATIONS:
            raise InventoryError(f"{operation.value} is not an offer operation")
        now = _utc(at) if at is not None else _now()
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise InventoryError("ttl_seconds must be a positive integer")
        ttl = timedelta(seconds=ttl_seconds)
        if ttl > _MAX_OFFER_LIFETIME:
            raise InventoryError("offer lifetime exceeds the bounded maximum")
        item_ids = tuple(dict.fromkeys(item_instance_ids))
        reciprocal_ids = tuple(dict.fromkeys(reciprocal_item_instance_ids))
        design_ids_tuple = tuple(dict.fromkeys(design_ids))
        if operation in _RECIPROCAL_OPERATIONS and not reciprocal_ids:
            raise InventoryError("trade/swap requires reciprocal item instances")
        if operation in _DESIGN_OPERATIONS and not design_ids_tuple:
            raise InventoryError(f"{operation.value} requires catalog design ids")
        if operation in (
            TransferOperation.LEND,
            TransferOperation.RETURN,
            TransferOperation.GIFT,
            TransferOperation.TRADE,
            TransferOperation.SWAP_OUTFIT,
        ) and not item_ids:
            raise InventoryError(f"{operation.value} requires item instances")

        with self._store.transaction() as db:
            existing = self._store.find_offer_by_idempotency(
                db, sender_core_id, idempotency_key
            )
            if existing is not None:
                if (
                    existing.operation is not operation
                    or existing.recipient_core_id != recipient_core_id
                    or existing.item_instance_ids != item_ids
                    or existing.reciprocal_item_instance_ids != reciprocal_ids
                    or existing.design_ids != design_ids_tuple
                ):
                    raise TransferConflict(
                        "idempotency key was already used for a different offer"
                    )
                return existing

            changed_ids = item_ids + reciprocal_ids
            items = self._store.get_items(db, changed_ids)
            missing = [item_id for item_id in changed_ids if item_id not in items]
            if missing:
                raise KeyError(f"item instances were not found: {missing}")
            ordered_items = tuple(items[item_id] for item_id in changed_ids)
            expected = self._merge_expected(ordered_items, expected_items)
            assert_current_revisions(ordered_items, expected)
            self._validate_item_subjects(
                operation,
                sender_core_id,
                recipient_core_id,
                item_ids,
                reciprocal_ids,
                items,
            )
            for design_id in design_ids_tuple:
                self.design(design_id)

            offer = TransferOffer(
                offer_id=uuid4(),
                operation=operation,
                sender_core_id=sender_core_id,
                recipient_core_id=recipient_core_id,
                item_instance_ids=item_ids,
                reciprocal_item_instance_ids=reciprocal_ids,
                expected_items=expected,
                created_at=now,
                expires_at=now + ttl,
                idempotency_key=idempotency_key,
                status=OfferStatus.PENDING,
                revision=1,
                design_ids=design_ids_tuple,
                note=note,
            )
            self._store.insert_offer(db, offer)
            self._store.append_audit(
                db,
                actor_core_id=sender_core_id,
                event_type="aegis.wardrobe.transfer.offer",
                payload=offer.to_payload(),
                occurred_at=now,
            )
            return offer

    def offer(self, operation: TransferOperation, sender_core_id: UUID, recipient_core_id: UUID, **kwargs) -> TransferOffer:
        return self.create_offer(
            operation, sender_core_id, recipient_core_id, **kwargs
        )

    def get_offer(self, offer_id: UUID) -> TransferOffer:
        with self._store.reader() as db:
            offer = self._store.get_offer(db, offer_id)
        if offer is None:
            raise OfferNotFound(str(offer_id))
        return offer

    def offers(self, *, status: OfferStatus | None = None) -> tuple[TransferOffer, ...]:
        with self._store.reader() as db:
            return self._store.list_offers(db, status=status)

    def _merge_expected(
        self, items: Iterable[ItemInstance], expected: Iterable[ItemRevision]
    ) -> tuple[ItemRevision, ...]:
        expected_values = tuple(expected)
        for expected_item in expected_values:
            if not isinstance(expected_item, ItemRevision):
                raise InventoryError("expected_items must be ItemRevision values")
        supplied = {item.item_instance_id: item for item in expected_values}
        result: list[ItemRevision] = []
        for item in items:
            revision = supplied.get(item.item_instance_id)
            if revision is not None and revision.revision != item.revision:
                raise StaleItemRevision(
                    f"item {item.item_instance_id} no longer matches revision "
                    f"{revision.revision}"
                )
            result.append(ItemRevision(item.item_instance_id, item.revision))
        changed = {item.item_instance_id for item in items}
        for item_id in supplied:
            if item_id not in changed:
                raise InventoryError("expected revision describes an unoffered item")
        return tuple(result)

    def _validate_item_subjects(
        self,
        operation: TransferOperation,
        sender_core_id: UUID,
        recipient_core_id: UUID,
        item_ids: tuple[UUID, ...],
        reciprocal_ids: tuple[UUID, ...],
        items: Mapping[UUID, ItemInstance],
    ) -> None:
        for item_id in item_ids:
            item = items[item_id]
            assert_holder(item, sender_core_id, operation=operation)
            assert_title(item, sender_core_id, operation=operation)
            assert_not_wearing(item, operation=operation)
        for item_id in reciprocal_ids:
            item = items[item_id]
            assert_holder(item, recipient_core_id, operation=operation)
            assert_title(item, recipient_core_id, operation=operation)
            assert_not_wearing(item, operation=operation)

    def decline(
        self,
        offer_id: UUID,
        actor_core_id: UUID,
        *,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> TransferReceipt:
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            offer = self._require_offer(db, offer_id)
            if actor_core_id != offer.recipient_core_id:
                raise TransferDenied("only the exact recipient may decline an offer")
            self._require_live_offer(offer, now)
            receipt = self._transition_terminal(
                db, offer, OfferStatus.DECLINED, actor_core_id, now, reason
            )
        return receipt

    def cancel(
        self,
        offer_id: UUID,
        actor_core_id: UUID,
        *,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> TransferReceipt:
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            offer = self._require_offer(db, offer_id)
            if actor_core_id != offer.sender_core_id:
                raise TransferDenied("only the sender may cancel an offer")
            self._require_live_offer(offer, now)
            receipt = self._transition_terminal(
                db, offer, OfferStatus.CANCELED, actor_core_id, now, reason
            )
        return receipt

    def _require_offer(self, db: sqlite3.Connection, offer_id: UUID) -> TransferOffer:
        offer = self._store.get_offer(db, offer_id)
        if offer is None:
            raise OfferNotFound(str(offer_id))
        return offer

    def _require_live_offer(self, offer: TransferOffer, now: datetime) -> None:
        if offer.status in TERMINAL_OFFER_STATUSES:
            raise TransferConflict(f"offer is already {offer.status.value}")
        offer.require_pending(now)

    def _transition_terminal(
        self,
        db: sqlite3.Connection,
        offer: TransferOffer,
        status: OfferStatus,
        actor_core_id: UUID,
        now: datetime,
        reason: str | None,
    ) -> TransferReceipt:
        updated = replace(offer, status=status, revision=offer.revision + 1)
        self._store.update_offer(
            db, updated, expected_revision=offer.revision, previous_items_json=None
        )
        receipt = self._make_receipt(
            updated,
            status,
            actor_core_id,
            now,
            reason=reason,
            resulting_items=(),
        )
        receipt = self._insert_receipt_once(db, receipt)
        self._store.append_audit(
            db,
            actor_core_id=actor_core_id,
            event_type=f"aegis.wardrobe.transfer.{status.value}",
            payload={
                "offer_id": str(offer.offer_id),
                "status": status.value,
                "actor_core_id": str(actor_core_id),
            },
            occurred_at=now,
        )
        return receipt

    # -- acceptance --------------------------------------------------------

    def accept(
        self,
        offer_id: UUID,
        actor_core_id: UUID,
        *,
        expected_items: Iterable[ItemRevision] = (),
        loan_due_at: datetime | None = None,
        at: datetime | None = None,
        render: Callable[[TransferOffer, tuple[ItemRevision, ...]], str] | None = None,
    ) -> TransferReceipt:
        now = _utc(at) if at is not None else _now()
        pending_error: BaseException | None = None
        receipt: TransferReceipt | None = None
        use_render = render is not None

        with self._store.transaction() as db:
            offer = self._require_offer(db, offer_id)
            if actor_core_id != offer.recipient_core_id:
                raise TransferDenied("only the exact recipient may accept an offer")
            if offer.status in TERMINAL_OFFER_STATUSES:
                raise TransferConflict(f"offer is already {offer.status.value}")
            if offer.is_expired(now):
                self._expire_offer(db, offer, now)
                pending_error = OfferExpired("transfer offer has expired")
            else:
                if expected_items:
                    supplied = tuple(expected_items)
                    assert_current_revisions(
                        self._offer_items(db, offer), supplied
                    )
                db.execute("SAVEPOINT aegis_accept")
                try:
                    receipt = self._apply_accept(
                        db,
                        offer,
                        now,
                        loan_due_at=loan_due_at,
                        defer_receipt=use_render,
                    )
                    db.execute("RELEASE aegis_accept")
                except (TransferConflict, TransferDenied, InventoryError) as exc:
                    db.execute("ROLLBACK TO aegis_accept")
                    db.execute("RELEASE aegis_accept")
                    self._fail_offer(db, offer, actor_core_id, now, str(exc))
                    pending_error = exc

        if pending_error is not None:
            raise pending_error
        assert receipt is not None or use_render

        if not use_render:
            assert receipt is not None
            return receipt

        assert render is not None
        accepted = self.get_offer(offer_id)
        try:
            evidence = render(accepted, self._receipt_revisions(db=None, offer=accepted))
        except Exception as exc:
            self._compensate_render_failure(
                offer_id, "downstream renderer failed", _now()
            )
            raise InventoryRenderFailed(
                "renderer failed; ownership/custody was restored and recorded FAILED"
            ) from exc
        if not isinstance(evidence, str) or not evidence.strip():
            self._compensate_render_failure(
                offer_id, "downstream renderer returned no evidence", _now()
            )
            raise InventoryRenderFailed(
                "renderer returned no evidence; ownership/custody was restored"
            )
        return self._record_render_success(offer_id, evidence, _now())

    def _receipt_revisions(
        self, *, db: sqlite3.Connection | None, offer: TransferOffer
    ) -> tuple[ItemRevision, ...]:
        if db is not None:
            items = self._store.get_items(
                db, offer.item_instance_ids + offer.reciprocal_item_instance_ids
            )
            return item_revisions(items[item_id] for item_id in items)
        with self._store.reader() as reader:
            items = self._store.get_items(
                reader, offer.item_instance_ids + offer.reciprocal_item_instance_ids
            )
            return item_revisions(items[item_id] for item_id in items)

    def _offer_items(
        self, db: sqlite3.Connection, offer: TransferOffer
    ) -> tuple[ItemInstance, ...]:
        ids = offer.item_instance_ids + offer.reciprocal_item_instance_ids
        items = self._store.get_items(db, ids)
        missing = [item_id for item_id in ids if item_id not in items]
        if missing:
            raise KeyError(f"item instances were not found: {missing}")
        return tuple(items[item_id] for item_id in ids)

    def _apply_accept(
        self,
        db: sqlite3.Connection,
        offer: TransferOffer,
        now: datetime,
        *,
        loan_due_at: datetime | None,
        defer_receipt: bool,
    ) -> TransferReceipt | None:
        items = self._offer_items(db, offer)
        assert_current_revisions(items, offer.expected_items)
        item_map = {item.item_instance_id: item for item in items}
        self._validate_item_subjects(
            offer.operation,
            offer.sender_core_id,
            offer.recipient_core_id,
            offer.item_instance_ids,
            offer.reciprocal_item_instance_ids,
            item_map,
        )

        updates: list[tuple[ItemInstance, int]] = []
        created: list[ItemInstance] = []
        returned: list[tuple[UUID, UUID]] = []

        if offer.operation is TransferOperation.LEND:
            due = (
                _utc(loan_due_at) if loan_due_at is not None else now + _DEFAULT_LOAN
            )
            if due <= now:
                raise InventoryError("loan due time must follow the transfer")
            for item_id in offer.item_instance_ids:
                item = item_map[item_id]
                updates.append((
                    replace(
                        item,
                        holder_core_id=offer.recipient_core_id,
                        custody=CustodyKind.LOANED,
                        loan_due_at=due,
                        recall_requested=False,
                        equipped_by_core_id=None,
                        updated_at=now,
                        revision=item.revision + 1,
                    ),
                    item.revision,
                ))
        elif offer.operation is TransferOperation.RETURN:
            for item_id in offer.item_instance_ids:
                item = item_map[item_id]
                if item.equipped_by_core_id is not None:
                    returned.append((item_id, item.equipped_by_core_id))
                updates.append((
                    replace(
                        item,
                        holder_core_id=item.owner_core_id,
                        custody=CustodyKind.OWNED,
                        loan_due_at=None,
                        recall_requested=False,
                        equipped_by_core_id=None,
                        updated_at=now,
                        revision=item.revision + 1,
                    ),
                    item.revision,
                ))
        elif offer.operation is TransferOperation.GIFT:
            for item_id in offer.item_instance_ids:
                item = item_map[item_id]
                updates.append((
                    replace(
                        item,
                        owner_core_id=offer.recipient_core_id,
                        holder_core_id=offer.recipient_core_id,
                        custody=CustodyKind.OWNED,
                        loan_due_at=None,
                        recall_requested=False,
                        equipped_by_core_id=None,
                        updated_at=now,
                        revision=item.revision + 1,
                    ),
                    item.revision,
                ))
        elif offer.operation in _RECIPROCAL_OPERATIONS:
            for item_id in offer.item_instance_ids:
                item = item_map[item_id]
                updates.append((
                    replace(
                        item,
                        owner_core_id=offer.recipient_core_id,
                        holder_core_id=offer.recipient_core_id,
                        custody=CustodyKind.OWNED,
                        loan_due_at=None,
                        recall_requested=False,
                        equipped_by_core_id=None,
                        updated_at=now,
                        revision=item.revision + 1,
                    ),
                    item.revision,
                ))
            for item_id in offer.reciprocal_item_instance_ids:
                item = item_map[item_id]
                updates.append((
                    replace(
                        item,
                        owner_core_id=offer.sender_core_id,
                        holder_core_id=offer.sender_core_id,
                        custody=CustodyKind.OWNED,
                        loan_due_at=None,
                        recall_requested=False,
                        equipped_by_core_id=None,
                        updated_at=now,
                        revision=item.revision + 1,
                    ),
                    item.revision,
                ))
        elif offer.operation in _DESIGN_OPERATIONS:
            for design_id in offer.design_ids:
                design = self.design(design_id)
                created.append(
                    ItemInstance(
                        item_instance_id=uuid4(),
                        design_id=design.design_id,
                        design_version=design.version,
                        owner_core_id=offer.recipient_core_id,
                        holder_core_id=offer.recipient_core_id,
                        custody=CustodyKind.OWNED,
                        revision=1,
                        created_at=now,
                        updated_at=now,
                        transferable=True,
                        private_to_owner=design.privacy is not WardrobePrivacy.PUBLIC,
                        equipped_by_core_id=None,
                    )
                )
        elif offer.operation is TransferOperation.OFFER:
            pass
        else:
            raise InventoryError(f"{offer.operation.value} cannot be accepted")

        changed_ids = offer.item_instance_ids + offer.reciprocal_item_instance_ids
        snapshots = [item_map[item_id] for item_id in changed_ids if item_id in item_map]
        for item, expected_revision in updates:
            self._store.update_item(db, item, expected_revision=expected_revision)
        for item in created:
            self._store.insert_item(db, item)
        for item_id, wearer in returned:
            self._remove_from_outfit(db, item_id, now, wearer_core_id=wearer)

        guard: str | None = None
        if defer_receipt:
            guard = json.dumps(
                {
                    "schema": _RENDER_GUARD_SCHEMA,
                    "items": [_item_snapshot(item) for item in snapshots],
                    "created_item_ids": [str(item.item_instance_id) for item in created],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        updated_offer = replace(
            offer, status=OfferStatus.ACCEPTED, revision=offer.revision + 1
        )
        self._store.update_offer(
            db,
            updated_offer,
            expected_revision=offer.revision,
            previous_items_json=guard,
        )

        if defer_receipt:
            self._store.append_audit(
                db,
                actor_core_id=offer.recipient_core_id,
                event_type="aegis.wardrobe.transfer.accept_pending_render",
                payload={
                    "offer_id": str(offer.offer_id),
                    "item_instance_ids": [str(item) for item in offer.item_instance_ids],
                },
                occurred_at=now,
            )
            return None

        resulting = tuple(
            ItemRevision(item.item_instance_id, item.revision)
            for item, _ in updates
        ) + tuple(item_revisions(created))
        receipt = self._make_receipt(
            updated_offer,
            OfferStatus.ACCEPTED,
            offer.recipient_core_id,
            now,
            resulting_items=resulting,
        )
        receipt = self._insert_receipt_once(db, receipt)
        self._store.append_audit(
            db,
            actor_core_id=offer.recipient_core_id,
            event_type="aegis.wardrobe.transfer.accepted",
            payload={
                "offer_id": str(offer.offer_id),
                "operation": offer.operation.value,
                "item_instance_ids": [str(item) for item in offer.item_instance_ids],
                "resulting_items": [
                    {"item_instance_id": str(rev.item_instance_id), "revision": rev.revision}
                    for rev in resulting
                ],
            },
            occurred_at=now,
        )
        return receipt

    def _record_render_success(
        self, offer_id: UUID, evidence: str, now: datetime
    ) -> TransferReceipt:
        digest = sha256(evidence.encode("utf-8")).hexdigest()
        evidence_ref = f"aegis.inventory.render.{digest}"
        with self._store.transaction() as db:
            offer = self._require_offer(db, offer_id)
            if offer.status is not OfferStatus.ACCEPTED:
                raise TransferConflict(
                    f"offer is {offer.status.value}, not awaiting render evidence"
                )
            guard = self._store.get_offer_guard(db, offer_id)
            if guard is None:
                raise TransferConflict("offer has no pending render guard")
            resulting = tuple(
                ItemRevision(item.item_instance_id, item.revision)
                for item in self._offer_items(db, offer)
            )
            receipt = self._make_receipt(
                offer,
                OfferStatus.ACCEPTED,
                offer.recipient_core_id,
                now,
                resulting_items=resulting,
                evidence_ref=evidence_ref,
            )
            receipt = self._insert_receipt_once(db, receipt)
            self._store.clear_offer_guard(db, offer_id)
            self._store.append_audit(
                db,
                actor_core_id=offer.recipient_core_id,
                event_type="aegis.wardrobe.transfer.render_verified",
                payload={
                    "offer_id": str(offer_id),
                    "evidence_ref": evidence_ref,
                },
                occurred_at=now,
            )
            return receipt

    def _compensate_render_failure(
        self, offer_id: UUID, reason: str, now: datetime
    ) -> TransferReceipt:
        with self._store.transaction() as db:
            offer = self._require_offer(db, offer_id)
            return self._restore_guard_and_fail(db, offer, reason, now)

    # -- failure, expiry and restart reconciliation ------------------------

    def _fail_offer(
        self,
        db: sqlite3.Connection,
        offer: TransferOffer,
        actor_core_id: UUID,
        now: datetime,
        reason: str,
    ) -> TransferReceipt:
        updated = replace(offer, status=OfferStatus.FAILED, revision=offer.revision + 1)
        self._store.update_offer(
            db, updated, expected_revision=offer.revision, previous_items_json=None
        )
        receipt = self._make_receipt(
            updated,
            OfferStatus.FAILED,
            actor_core_id,
            now,
            reason=reason,
            resulting_items=(),
        )
        receipt = self._insert_receipt_once(db, receipt)
        self._store.append_audit(
            db,
            actor_core_id=actor_core_id,
            event_type="aegis.wardrobe.transfer.failed",
            payload={"offer_id": str(offer.offer_id), "reason": reason},
            occurred_at=now,
        )
        return receipt

    def _expire_offer(
        self, db: sqlite3.Connection, offer: TransferOffer, now: datetime
    ) -> TransferReceipt:
        if offer.status in TERMINAL_OFFER_STATUSES:
            existing = self._store.find_receipt(db, offer.offer_id, offer.status)
            if existing is not None:
                return existing
            raise TransferConflict(f"offer is already {offer.status.value}")
        updated = replace(offer, status=OfferStatus.EXPIRED, revision=offer.revision + 1)
        self._store.update_offer(
            db, updated, expected_revision=offer.revision, previous_items_json=None
        )
        receipt = self._make_receipt(
            updated,
            OfferStatus.EXPIRED,
            offer.sender_core_id,
            now,
            reason="offer expired before bilateral acceptance",
            resulting_items=(),
        )
        receipt = self._insert_receipt_once(db, receipt)
        self._store.append_audit(
            db,
            actor_core_id=offer.sender_core_id,
            event_type="aegis.wardrobe.transfer.expired",
            payload={"offer_id": str(offer.offer_id)},
            occurred_at=now,
        )
        return receipt

    def _restore_guard_and_fail(
        self,
        db: sqlite3.Connection,
        offer: TransferOffer,
        reason: str,
        now: datetime,
    ) -> TransferReceipt:
        guard_raw = self._store.get_offer_guard(db, offer.offer_id)
        if guard_raw is not None:
            guard = json.loads(guard_raw)
            if guard.get("schema") != _RENDER_GUARD_SCHEMA:
                raise InventoryError("render guard schema is unknown")
            for snapshot in guard.get("items", ()):
                original = _item_from_snapshot(snapshot)
                current = self._store.get_item(db, original.item_instance_id)
                if current is None:
                    continue
                restored = replace(
                    current,
                    owner_core_id=original.owner_core_id,
                    holder_core_id=original.holder_core_id,
                    custody=original.custody,
                    loan_due_at=original.loan_due_at,
                    recall_requested=original.recall_requested,
                    equipped_by_core_id=original.equipped_by_core_id,
                    updated_at=now,
                    revision=current.revision + 1,
                )
                self._store.update_item(
                    db, restored, expected_revision=current.revision
                )
            for item_id in guard.get("created_item_ids", ()):
                self._store.delete_item(db, UUID(str(item_id)))
        updated = replace(offer, status=OfferStatus.FAILED, revision=offer.revision + 1)
        self._store.update_offer(
            db, updated, expected_revision=offer.revision, previous_items_json=None
        )
        receipt = self._make_receipt(
            updated,
            OfferStatus.FAILED,
            offer.recipient_core_id,
            now,
            reason=reason,
            resulting_items=(),
        )
        receipt = self._insert_receipt_once(db, receipt)
        self._store.append_audit(
            db,
            actor_core_id=offer.recipient_core_id,
            event_type="aegis.wardrobe.transfer.render_failed",
            payload={"offer_id": str(offer.offer_id), "reason": reason},
            occurred_at=now,
        )
        return receipt

    def reconcile(self, *, at: datetime | None = None) -> dict[str, int]:
        """Expire overdue offers and fail unknown renders exactly once."""
        now = _utc(at) if at is not None else _now()
        expired = 0
        failed_renders = 0
        with self._store.transaction() as db:
            for offer in self._store.list_offers(db, status=OfferStatus.PENDING):
                if offer.is_expired(now):
                    self._expire_offer(db, offer, now)
                    expired += 1
            for offer in self._store.list_render_pending_offers(db):
                self._restore_guard_and_fail(
                    db,
                    offer,
                    "render outcome unknown at restart; fail-closed rollback",
                    now,
                )
                failed_renders += 1
        return {"expired": expired, "render_failed": failed_renders}

    # -- receipts ----------------------------------------------------------

    def _make_receipt(
        self,
        offer: TransferOffer,
        status: OfferStatus,
        actor_core_id: UUID,
        now: datetime,
        *,
        resulting_items: Iterable[ItemRevision] = (),
        reason: str | None = None,
        evidence_ref: str | None = None,
    ) -> TransferReceipt:
        receipt_id = uuid5(
            NAMESPACE_URL, f"aegis.inventory.receipt:{offer.offer_id}:{status.value}"
        )
        if evidence_ref is None:
            evidence_ref = f"aegis.inventory.{status.value}.{offer.offer_id}"
        return TransferReceipt(
            receipt_id=receipt_id,
            offer_id=offer.offer_id,
            operation=offer.operation,
            status=status,
            actor_core_id=actor_core_id,
            item_instance_ids=offer.item_instance_ids,
            resulting_items=tuple(resulting_items),
            idempotency_key=offer.idempotency_key,
            occurred_at=now,
            evidence_ref=evidence_ref,
            reason=reason,
        )

    def _insert_receipt_once(
        self, db: sqlite3.Connection, receipt: TransferReceipt
    ) -> TransferReceipt:
        existing = self._store.find_receipt(db, receipt.offer_id, receipt.status)
        if existing is not None:
            return existing
        try:
            self._store.insert_receipt(db, receipt)
        except sqlite3.IntegrityError:
            existing = self._store.find_receipt(db, receipt.offer_id, receipt.status)
            if existing is None:
                raise
            return existing
        return receipt

    def receipts(self, *, offer_id: UUID | None = None) -> tuple[TransferReceipt, ...]:
        with self._store.reader() as db:
            return self._store.list_receipts(db, offer_id=offer_id)

    # -- loans and recall --------------------------------------------------

    def request_recall(
        self,
        item_instance_id: UUID,
        owner_core_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ItemInstance:
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            item = self._store.get_item(db, item_instance_id)
            if item is None:
                raise KeyError(f"item instance {item_instance_id} was not found")
            if item.owner_core_id != owner_core_id:
                raise NotItemOwner("only the recorded owner may request recall")
            if item.custody is not CustodyKind.LOANED:
                raise TransferConflict("recall applies only to a loaned item")
            updated = replace(
                item,
                recall_requested=True,
                updated_at=now,
                revision=item.revision + 1,
            )
            self._store.update_item(db, updated, expected_revision=item.revision)
            self._store.append_audit(
                db,
                actor_core_id=owner_core_id,
                event_type="aegis.wardrobe.inventory.recall_requested",
                payload={"item_instance_id": str(item_instance_id)},
                occurred_at=now,
            )
            return updated

    # -- outfits -----------------------------------------------------------

    def outfit(
        self, wearer_core_id: UUID
    ) -> tuple[OutfitSelection, tuple[ItemRevision, ...]] | None:
        with self._store.reader() as db:
            return self._store.get_outfit(db, wearer_core_id)

    def select_outfit(
        self,
        wearer_core_id: UUID,
        item_instance_ids: Iterable[UUID],
        *,
        expected_items: Iterable[ItemRevision] = (),
        expected_outfit_revision: int | None = None,
        privacy: str | None = None,
        body_profile: str | None = None,
        body_has_tail: bool = False,
        body_has_ears: bool = False,
        require_fit: bool = False,
        require_assets: bool = False,
        asset_verified: bool = False,
        at: datetime | None = None,
    ) -> OutfitSelection:
        now = _utc(at) if at is not None else _now()
        ids = tuple(dict.fromkeys(item_instance_ids))
        with self._store.transaction() as db:
            record = self._store.get_outfit(db, wearer_core_id)
            previous = None if record is None else record[0]
            if (
                expected_outfit_revision is not None
                and (previous is None or previous.revision != expected_outfit_revision)
            ):
                raise StaleItemRevision("outfit revision does not match")
            items_by_id = self._store.get_items(db, ids)
            missing = [item_id for item_id in ids if item_id not in items_by_id]
            if missing:
                raise KeyError(f"item instances were not found: {missing}")
            items = tuple(items_by_id[item_id] for item_id in ids)
            for item in items:
                if item.holder_core_id != wearer_core_id:
                    raise NotItemHolder(
                        f"wearer does not hold {item.item_instance_id}"
                    )
                if (
                    item.equipped_by_core_id is not None
                    and item.equipped_by_core_id != wearer_core_id
                ):
                    raise TransferConflict(
                        f"item {item.item_instance_id} is worn by another Core"
                    )
            if expected_items:
                assert_current_revisions(items, tuple(expected_items))
            selection = OutfitSelection(
                wearer_core_id=wearer_core_id,
                item_instance_ids=ids,
                revision=1 if previous is None else previous.revision + 1,
                privacy=privacy or self._outfit_privacy(items),
            )
            self._validate_outfit_chain(
                items,
                body_profile=body_profile,
                body_has_tail=body_has_tail,
                body_has_ears=body_has_ears,
                require_fit=require_fit,
                require_assets=require_assets,
                asset_verified=asset_verified,
            )
            self._persist_outfit(
                db,
                wearer_core_id,
                previous,
                items,
                selection,
                now,
            )
            self._store.append_audit(
                db,
                actor_core_id=wearer_core_id,
                event_type="aegis.wardrobe.outfit.selected",
                payload=selection.to_payload(),
                occurred_at=now,
            )
        return selection

    def equip_item(
        self,
        wearer_core_id: UUID,
        item_instance_id: UUID,
        *,
        body_profile: str | None = None,
        body_has_tail: bool = False,
        body_has_ears: bool = False,
        require_fit: bool = False,
        require_assets: bool = False,
        asset_verified: bool = False,
        at: datetime | None = None,
    ) -> ArmorDecision:
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            item = self._store.get_item(db, item_instance_id)
            if item is None:
                raise KeyError(f"item instance {item_instance_id} was not found")
            if item.holder_core_id != wearer_core_id:
                raise NotItemHolder(
                    f"wearer does not hold {item_instance_id}"
                )
            if (
                item.equipped_by_core_id is not None
                and item.equipped_by_core_id != wearer_core_id
            ):
                raise TransferConflict(f"item {item_instance_id} is worn by another Core")
            design = self.design(item.design_id, item.design_version)
            record = self._store.get_outfit(db, wearer_core_id)
            previous = None if record is None else record[0]
            current_ids = () if previous is None else previous.item_instance_ids
            if item_instance_id in current_ids:
                return ArmorDecision(
                    ArmorDecisionStatus.DENIED,
                    f"{design.design_id!r} is already equipped by this wearer",
                    (item_instance_id,),
                )
            current_items = self._items_for_ids(db, current_ids)
            equipped = tuple(
                EquippedItem.from_design(
                    other.item_instance_id,
                    self.design(other.design_id, other.design_version),
                    asset_verified=asset_verified,
                )
                for other in current_items
            )
            if design.is_armor:
                candidate = EquippedItem.from_design(
                    item_instance_id, design, asset_verified=asset_verified
                )
                decision = validate_armor_equip(
                    equipped,
                    candidate,
                    body_profile=body_profile,
                    body_has_tail=body_has_tail,
                    body_has_ears=body_has_ears,
                    require_fit=require_fit,
                    require_assets=require_assets,
                )
                if not decision.allowed:
                    return decision
            else:
                if require_fit and body_profile is None:
                    return ArmorDecision(
                        ArmorDecisionStatus.UNAVAILABLE,
                        "wearer body profile is unknown; fit cannot be claimed",
                    )
                if require_assets and (
                    design.asset_ref is None or not asset_verified
                ):
                    return ArmorDecision(
                        ArmorDecisionStatus.UNAVAILABLE,
                        "reviewed renderer asset is not installed/verified; metadata-only status",
                    )
                decision = ArmorDecision(
                    ArmorDecisionStatus.ALLOWED,
                    "ordinary wardrobe item selected; no armor dependency applies",
                )
            new_ids = current_ids + (item_instance_id,)
            items = tuple(current_items) + (item,)
            selection = OutfitSelection(
                wearer_core_id=wearer_core_id,
                item_instance_ids=new_ids,
                revision=1 if previous is None else previous.revision + 1,
                privacy=self._outfit_privacy(items),
            )
            self._persist_outfit(
                db,
                wearer_core_id,
                previous,
                items,
                selection,
                now,
            )
            self._store.append_audit(
                db,
                actor_core_id=wearer_core_id,
                event_type="aegis.wardrobe.outfit.equip",
                payload={
                    "wearer_core_id": str(wearer_core_id),
                    "item_instance_id": str(item_instance_id),
                    "design_id": design.design_id,
                },
                occurred_at=now,
            )
            return decision

    def unequip_item(
        self,
        wearer_core_id: UUID,
        item_instance_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ArmorDecision:
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            record = self._store.get_outfit(db, wearer_core_id)
            if record is None or item_instance_id not in record[0].item_instance_ids:
                return ArmorDecision(
                    ArmorDecisionStatus.DENIED,
                    "item instance is not equipped by this wearer",
                )
            previous = record[0]
            current_items = self._items_for_ids(db, previous.item_instance_ids)
            equipped = tuple(
                EquippedItem.from_design(
                    item.item_instance_id,
                    self.design(item.design_id, item.design_version),
                )
                for item in current_items
            )
            decision = validate_armor_unequip(equipped, item_instance_id)
            if not decision.allowed:
                return decision
            remaining = tuple(
                item for item in current_items
                if item.item_instance_id != item_instance_id
            )
            self._remove_items_from_outfit(
                db, wearer_core_id, previous, current_items, (item_instance_id,), now
            )
            selection = OutfitSelection(
                wearer_core_id=wearer_core_id,
                item_instance_ids=tuple(item.item_instance_id for item in remaining),
                revision=previous.revision + 1,
                privacy=previous.privacy,
            )
            self._persist_outfit(
                db,
                wearer_core_id,
                previous,
                remaining,
                selection,
                now,
                items_already_updated=True,
            )
            self._store.append_audit(
                db,
                actor_core_id=wearer_core_id,
                event_type="aegis.wardrobe.outfit.unequip",
                payload={
                    "wearer_core_id": str(wearer_core_id),
                    "item_instance_id": str(item_instance_id),
                },
                occurred_at=now,
            )
            return decision

    def atomic_disassemble(
        self,
        wearer_core_id: UUID,
        item_instance_id: UUID,
        *,
        at: datetime | None = None,
    ) -> tuple[UUID, ...]:
        """Execute the reviewed full-strip order in one canonical commit."""
        now = _utc(at) if at is not None else _now()
        with self._store.transaction() as db:
            record = self._store.get_outfit(db, wearer_core_id)
            if record is None or item_instance_id not in record[0].item_instance_ids:
                raise TransferConflict("item instance is not equipped")
            previous = record[0]
            current_items = self._items_for_ids(db, previous.item_instance_ids)
            equipped = tuple(
                EquippedItem.from_design(
                    item.item_instance_id,
                    self.design(item.design_id, item.design_version),
                )
                for item in current_items
            )
            plan = atomic_disassembly_plan(equipped, item_instance_id)
            self._remove_items_from_outfit(
                db, wearer_core_id, previous, current_items, plan, now
            )
            remaining = tuple(
                item for item in current_items if item.item_instance_id not in plan
            )
            selection = OutfitSelection(
                wearer_core_id=wearer_core_id,
                item_instance_ids=tuple(item.item_instance_id for item in remaining),
                revision=previous.revision + 1,
                privacy=previous.privacy,
            )
            self._persist_outfit(
                db,
                wearer_core_id,
                previous,
                remaining,
                selection,
                now,
                items_already_updated=True,
            )
            self._store.append_audit(
                db,
                actor_core_id=wearer_core_id,
                event_type="aegis.wardrobe.outfit.atomic_disassembly",
                payload={
                    "wearer_core_id": str(wearer_core_id),
                    "removed": [str(item) for item in plan],
                },
                occurred_at=now,
            )
            return plan

    def _items_for_ids(
        self, db: sqlite3.Connection, ids: Iterable[UUID]
    ) -> tuple[ItemInstance, ...]:
        values = tuple(ids)
        items = self._store.get_items(db, values)
        missing = [item_id for item_id in values if item_id not in items]
        if missing:
            raise KeyError(f"item instances were not found: {missing}")
        return tuple(items[item_id] for item_id in values)

    def _outfit_privacy(self, items: Iterable[ItemInstance]) -> str:
        privacy = "public"
        for item in items:
            design = self._designs.get(item.design_id)
            if design is None:
                return "private"
            if item.private_to_owner or design.privacy is WardrobePrivacy.ADULT:
                return "adult"
            if design.privacy is WardrobePrivacy.PRIVATE:
                privacy = "private"
        return privacy

    def _validate_outfit_chain(
        self,
        items: Iterable[ItemInstance],
        *,
        body_profile: str | None,
        body_has_tail: bool,
        body_has_ears: bool,
        require_fit: bool,
        require_assets: bool,
        asset_verified: bool,
    ) -> tuple[ArmorDecision, ...]:
        equipped: list[EquippedItem] = []
        decisions: list[ArmorDecision] = []
        for item in items:
            design = self.design(item.design_id, item.design_version)
            if require_fit and body_profile is None:
                raise InventoryUnavailable(
                    "wearer body profile is unknown; fit cannot be claimed"
                )
            if require_assets and (
                design.asset_ref is None or not asset_verified
            ):
                raise InventoryUnavailable(
                    "reviewed renderer asset is not installed/verified; "
                    "metadata-only status"
                )
            candidate = EquippedItem.from_design(
                item.item_instance_id, design, asset_verified=asset_verified
            )
            if design.is_armor:
                decision = validate_armor_equip(
                    equipped,
                    candidate,
                    body_profile=body_profile,
                    body_has_tail=body_has_tail,
                    body_has_ears=body_has_ears,
                    require_fit=require_fit,
                    require_assets=require_assets,
                )
                if not decision.allowed:
                    if decision.status is ArmorDecisionStatus.UNAVAILABLE:
                        raise InventoryUnavailable(decision.reason)
                    raise EquipDenied(decision.reason)
                decisions.append(decision)
            equipped.append(candidate)
        return tuple(decisions)

    def _persist_outfit(
        self,
        db: sqlite3.Connection,
        wearer_core_id: UUID,
        previous: OutfitSelection | None,
        items: tuple[ItemInstance, ...],
        selection: OutfitSelection,
        now: datetime,
        *,
        items_already_updated: bool = False,
    ) -> None:
        previous_ids = () if previous is None else previous.item_instance_ids
        new_ids = selection.item_instance_ids
        if not items_already_updated:
            self._apply_equipment_delta(
                db, wearer_core_id, previous_ids, items, now
            )
        revisions = self._current_revisions(db, new_ids)
        self._store.put_outfit(
            db,
            selection,
            revisions,
            expected_revision=None if previous is None else previous.revision,
            updated_at=now,
        )

    def _apply_equipment_delta(
        self,
        db: sqlite3.Connection,
        wearer_core_id: UUID,
        previous_ids: tuple[UUID, ...],
        items: tuple[ItemInstance, ...],
        now: datetime,
    ) -> None:
        new_by_id = {item.item_instance_id: item for item in items}
        previous = set(previous_ids)
        current = set(new_by_id)
        for item_id in previous - current:
            row = self._store.get_item(db, item_id)
            if row is None or row.equipped_by_core_id != wearer_core_id:
                continue
            updated = replace(
                row,
                equipped_by_core_id=None,
                updated_at=now,
                revision=row.revision + 1,
            )
            self._store.update_item(db, updated, expected_revision=row.revision)
        for item_id in current - previous:
            row = new_by_id[item_id]
            updated = replace(
                row,
                equipped_by_core_id=wearer_core_id,
                updated_at=now,
                revision=row.revision + 1,
            )
            self._store.update_item(db, updated, expected_revision=row.revision)

    def _current_revisions(
        self, db: sqlite3.Connection, ids: Iterable[UUID]
    ) -> tuple[ItemRevision, ...]:
        values = tuple(ids)
        rows = self._store.get_items(db, values)
        missing = [item_id for item_id in values if item_id not in rows]
        if missing:
            raise KeyError(f"item instances were not found: {missing}")
        return tuple(ItemRevision(item_id, rows[item_id].revision) for item_id in values)

    def _remove_items_from_outfit(
        self,
        db: sqlite3.Connection,
        wearer_core_id: UUID,
        previous: OutfitSelection,
        current_items: tuple[ItemInstance, ...],
        remove_ids: Iterable[UUID],
        now: datetime,
    ) -> None:
        targets = set(remove_ids)
        for item in current_items:
            if item.item_instance_id in targets:
                updated = replace(
                    item,
                    equipped_by_core_id=None,
                    updated_at=now,
                    revision=item.revision + 1,
                )
                self._store.update_item(
                    db, updated, expected_revision=item.revision
                )

    def _remove_from_outfit(
        self,
        db: sqlite3.Connection,
        item_instance_id: UUID,
        now: datetime,
        *,
        wearer_core_id: UUID | None = None,
    ) -> None:
        if wearer_core_id is None:
            item = self._store.get_item(db, item_instance_id)
            if item is None or item.equipped_by_core_id is None:
                return
            wearer = item.equipped_by_core_id
        else:
            wearer = wearer_core_id
        record = self._store.get_outfit(db, wearer)
        if record is None:
            return
        previous = record[0]
        if item_instance_id not in previous.item_instance_ids:
            return
        current_items = self._items_for_ids(db, previous.item_instance_ids)
        self._remove_items_from_outfit(
            db, wearer, previous, current_items, (item_instance_id,), now
        )
        remaining = tuple(
            row for row in current_items if row.item_instance_id != item_instance_id
        )
        revised = self._current_revisions(
            db, (row.item_instance_id for row in remaining)
        )
        selection = OutfitSelection(
            wearer_core_id=wearer,
            item_instance_ids=tuple(row.item_instance_id for row in remaining),
            revision=previous.revision + 1,
            privacy=previous.privacy,
        )
        # The transferred item was already revised by the transfer itself.
        keep = {
            row.item_instance_id: ItemRevision(row.item_instance_id, row.revision)
            for row in remaining
        }
        revisions = tuple(
            keep.get(revision.item_instance_id, revision) for revision in revised
        )
        self._store.put_outfit(
            db,
            selection,
            revisions,
            expected_revision=previous.revision,
            updated_at=now,
        )


__all__ = [
    "EquipDenied",
    "InventoryEngine",
    "InventoryRenderFailed",
    "InventoryUnavailable",
    "PublicInventory",
    "PublicInventoryItem",
]
