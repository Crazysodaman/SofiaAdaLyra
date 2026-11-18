"""Versioned item-instance, outfit and transfer contracts for the wardrobe.

A catalog design is shared and immutable.  An item instance is the single
owned/custodied physical-virtual object.  Lending never clones the instance;
gifts, trades and outfit swaps change ownership or custody through one atomic
bilateral transaction.  These types are inert: constructing one does not prove
sender title, recipient consent, renderer success or an applied mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Iterable
from uuid import UUID

INVENTORY_SCHEMA = "aegis.avatar.item_instance.v1"
TRANSFER_SCHEMA = "aegis.avatar.transfer.v1"
OUTFIT_SCHEMA = "aegis.avatar.outfit_selection.v1"

_MAX_ITEMS_PER_TRANSFER = 64
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class InventoryError(ValueError):
    """An inventory or transfer contract is malformed."""


class TransferDenied(PermissionError):
    """The supplied evidence does not permit the requested transfer."""


class TransferConflict(RuntimeError):
    """A revision, terminal state or duplicate offer conflicts."""


class OfferExpired(TransferConflict):
    """The transfer offer is past its bounded expiry."""


class OfferNotFound(KeyError):
    """No transfer offer exists for the supplied identity."""


class StaleItemRevision(TransferConflict):
    """The item changed after the offer's expected revision."""


class NotItemOwner(TransferDenied):
    """The actor does not hold genuine title for the requested operation."""


class NotItemHolder(TransferDenied):
    """The actor is not the current custodian of the item."""


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise InventoryError(f"{label} must be a nonzero UUID")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise InventoryError(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise InventoryError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _text(value: object, label: str, *, maximum: int = 1024) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise InventoryError(f"{label} must be bounded visible text")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InventoryError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise InventoryError(f"{label} must be boolean")
    return value


def _unique_uuid_tuple(value: object, label: str, *, nonempty: bool) -> tuple[UUID, ...]:
    if not isinstance(value, tuple):
        raise InventoryError(f"{label} must be a tuple")
    if nonempty and not value:
        raise InventoryError(f"{label} cannot be empty")
    for item in value:
        _uuid(item, label)
    if len(set(value)) != len(value):
        raise InventoryError(f"{label} must be unique")
    if len(value) > _MAX_ITEMS_PER_TRANSFER:
        raise InventoryError(f"{label} exceeds the bounded item count")
    return value


class CustodyKind(str, Enum):
    OWNED = "owned"
    LOANED = "loaned"
    GROUP_SHARED = "group_shared"


class TransferOperation(str, Enum):
    OFFER = "offer"
    ACCEPT = "accept"
    DECLINE = "decline"
    CANCEL = "cancel"
    LEND = "lend"
    RETURN = "return"
    GIFT = "gift"
    TRADE = "trade"
    SWAP_OUTFIT = "swap_outfit"
    COPY_DESIGN = "copy_design"
    CUSTOMIZE = "customize"


class OfferStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELED = "canceled"
    EXPIRED = "expired"
    FAILED = "failed"


TERMINAL_OFFER_STATUSES = frozenset({
    OfferStatus.ACCEPTED,
    OfferStatus.DECLINED,
    OfferStatus.CANCELED,
    OfferStatus.EXPIRED,
    OfferStatus.FAILED,
})
ITEM_TRANSFER_OPERATIONS = frozenset({
    TransferOperation.LEND,
    TransferOperation.RETURN,
    TransferOperation.GIFT,
    TransferOperation.TRADE,
    TransferOperation.SWAP_OUTFIT,
})
TITLE_TRANSFER_OPERATIONS = frozenset({
    TransferOperation.GIFT,
    TransferOperation.TRADE,
    TransferOperation.SWAP_OUTFIT,
})
RECIPROCAL_OPERATIONS = frozenset({
    TransferOperation.TRADE,
    TransferOperation.SWAP_OUTFIT,
})


@dataclass(frozen=True, slots=True)
class ItemInstance:
    """One immutable-identity item instance with mutable revision/custody state."""

    item_instance_id: UUID
    design_id: str
    design_version: int
    owner_core_id: UUID
    holder_core_id: UUID
    custody: CustodyKind
    revision: int
    created_at: datetime
    updated_at: datetime
    transferable: bool = True
    private_to_owner: bool = False
    loan_due_at: datetime | None = None
    recall_requested: bool = False
    equipped_by_core_id: UUID | None = None

    def __post_init__(self) -> None:
        _uuid(self.item_instance_id, "item_instance_id")
        _identifier(self.design_id, "design_id")
        if type(self.design_version) is not int or self.design_version < 1:
            raise InventoryError("design_version must be a positive integer")
        _uuid(self.owner_core_id, "owner_core_id")
        _uuid(self.holder_core_id, "holder_core_id")
        if not isinstance(self.custody, CustodyKind):
            raise InventoryError("custody must be CustodyKind")
        if type(self.revision) is not int or self.revision < 1:
            raise InventoryError("revision must be a positive integer")
        _utc(self.created_at, "created_at")
        _utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise InventoryError("updated_at cannot precede created_at")
        _bool(self.transferable, "transferable")
        _bool(self.private_to_owner, "private_to_owner")
        _bool(self.recall_requested, "recall_requested")
        if self.custody is CustodyKind.OWNED and self.holder_core_id != self.owner_core_id:
            raise InventoryError("an owned item is held by its owner")
        if self.custody is CustodyKind.LOANED and self.holder_core_id == self.owner_core_id:
            raise InventoryError("a loaned item is held by another Core")
        if self.loan_due_at is not None:
            _utc(self.loan_due_at, "loan_due_at")
            if self.custody is not CustodyKind.LOANED:
                raise InventoryError("only a loaned item can have a due time")
            if self.loan_due_at <= self.updated_at:
                raise InventoryError("loan due time must follow the current revision")
        if self.recall_requested and self.custody is not CustodyKind.LOANED:
            raise InventoryError("recall applies only to a loaned item")
        if self.equipped_by_core_id is not None:
            _uuid(self.equipped_by_core_id, "equipped_by_core_id")
            if self.equipped_by_core_id != self.holder_core_id:
                raise InventoryError("only the current holder may wear the item")

    @property
    def is_owned_by_holder(self) -> bool:
        return self.owner_core_id == self.holder_core_id

    def with_revision(self, **changes) -> "ItemInstance":
        """Return a new revision; callers must persist it transactionally."""
        from dataclasses import replace
        return replace(self, revision=self.revision + 1, **changes)


@dataclass(frozen=True, slots=True)
class ItemRevision:
    item_instance_id: UUID
    revision: int

    def __post_init__(self) -> None:
        _uuid(self.item_instance_id, "item_instance_id")
        if type(self.revision) is not int or self.revision < 1:
            raise InventoryError("revision must be a positive integer")


@dataclass(frozen=True, slots=True)
class TransferOffer:
    """A bounded, expiring, bilateral offer; inert until both sides accept."""

    offer_id: UUID
    operation: TransferOperation
    sender_core_id: UUID
    recipient_core_id: UUID
    item_instance_ids: tuple[UUID, ...]
    reciprocal_item_instance_ids: tuple[UUID, ...]
    expected_items: tuple[ItemRevision, ...]
    created_at: datetime
    expires_at: datetime
    idempotency_key: str
    status: OfferStatus = OfferStatus.PENDING
    revision: int = 1
    design_ids: tuple[str, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.offer_id, "offer_id")
        if not isinstance(self.operation, TransferOperation):
            raise InventoryError("operation must be TransferOperation")
        _uuid(self.sender_core_id, "sender_core_id")
        _uuid(self.recipient_core_id, "recipient_core_id")
        if self.sender_core_id == self.recipient_core_id:
            raise InventoryError("a Core cannot transfer to itself")
        _unique_uuid_tuple(self.item_instance_ids, "item_instance_ids", nonempty=False)
        _unique_uuid_tuple(
            self.reciprocal_item_instance_ids,
            "reciprocal_item_instance_ids",
            nonempty=False,
        )
        if not isinstance(self.expected_items, tuple):
            raise InventoryError("expected_items must be a tuple")
        for item in self.expected_items:
            if not isinstance(item, ItemRevision):
                raise InventoryError("expected_items must be ItemRevision values")
        expected_ids = tuple(item.item_instance_id for item in self.expected_items)
        if len(set(expected_ids)) != len(expected_ids):
            raise InventoryError("expected_items must be unique")
        changed_ids = set(self.item_instance_ids) | set(self.reciprocal_item_instance_ids)
        if not set(expected_ids).issubset(changed_ids):
            raise InventoryError("expected revisions must describe offered items only")
        _utc(self.created_at, "created_at")
        _utc(self.expires_at, "expires_at")
        if self.expires_at <= self.created_at:
            raise InventoryError("offer expiry must follow creation")
        _identifier(self.idempotency_key, "idempotency_key")
        if not isinstance(self.status, OfferStatus):
            raise InventoryError("status must be OfferStatus")
        if type(self.revision) is not int or self.revision < 1:
            raise InventoryError("revision must be a positive integer")
        if not isinstance(self.design_ids, tuple) or len(set(self.design_ids)) != len(self.design_ids):
            raise InventoryError("design_ids must be a unique tuple")
        for design_id in self.design_ids:
            _identifier(design_id, "design_id")
        if self.note is not None:
            _text(self.note, "note")
        if self.operation in ITEM_TRANSFER_OPERATIONS and not self.item_instance_ids:
            raise InventoryError("this operation requires at least one item instance")
        if self.operation in RECIPROCAL_OPERATIONS and not self.reciprocal_item_instance_ids:
            raise InventoryError("trade/swap operations require reciprocal item instances")
        if self.operation is TransferOperation.COPY_DESIGN and not self.design_ids:
            raise InventoryError("copy_design requires at least one catalog design")
        if self.operation is TransferOperation.OFFER and not (
            self.item_instance_ids or self.design_ids
        ):
            raise InventoryError("a generic offer must name an item or design")

    def is_expired(self, now: datetime) -> bool:
        return _utc(now, "now") >= self.expires_at

    def is_pending(self) -> bool:
        return self.status is OfferStatus.PENDING

    def require_pending(self, now: datetime) -> None:
        if self.status in TERMINAL_OFFER_STATUSES:
            raise TransferConflict(f"offer is already {self.status.value}")
        if self.is_expired(now):
            raise OfferExpired("transfer offer has expired")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": TRANSFER_SCHEMA,
            "offer_id": str(self.offer_id),
            "operation": self.operation.value,
            "sender_core_id": str(self.sender_core_id),
            "recipient_core_id": str(self.recipient_core_id),
            "item_instance_ids": [str(item) for item in self.item_instance_ids],
            "reciprocal_item_instance_ids": [
                str(item) for item in self.reciprocal_item_instance_ids
            ],
            "expected_items": [
                {
                    "item_instance_id": str(item.item_instance_id),
                    "revision": item.revision,
                }
                for item in self.expected_items
            ],
            "design_ids": list(self.design_ids),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "revision": self.revision,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class TransferReceipt:
    """Auditable outcome of one transfer attempt; never grants authority."""

    receipt_id: UUID
    offer_id: UUID
    operation: TransferOperation
    status: OfferStatus
    actor_core_id: UUID
    item_instance_ids: tuple[UUID, ...]
    resulting_items: tuple[ItemRevision, ...]
    idempotency_key: str
    occurred_at: datetime
    evidence_ref: str
    reason: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.receipt_id, "receipt_id")
        _uuid(self.offer_id, "offer_id")
        if not isinstance(self.operation, TransferOperation):
            raise InventoryError("operation must be TransferOperation")
        if not isinstance(self.status, OfferStatus):
            raise InventoryError("status must be OfferStatus")
        _uuid(self.actor_core_id, "actor_core_id")
        _unique_uuid_tuple(self.item_instance_ids, "item_instance_ids", nonempty=False)
        if not isinstance(self.resulting_items, tuple):
            raise InventoryError("resulting_items must be a tuple")
        for item in self.resulting_items:
            if not isinstance(item, ItemRevision):
                raise InventoryError("resulting_items must be ItemRevision values")
        _identifier(self.idempotency_key, "idempotency_key")
        _utc(self.occurred_at, "occurred_at")
        _identifier(self.evidence_ref, "evidence_ref")
        if self.reason is not None:
            _text(self.reason, "reason")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": f"{TRANSFER_SCHEMA}.receipt",
            "receipt_id": str(self.receipt_id),
            "offer_id": str(self.offer_id),
            "operation": self.operation.value,
            "status": self.status.value,
            "actor_core_id": str(self.actor_core_id),
            "item_instance_ids": [str(item) for item in self.item_instance_ids],
            "resulting_items": [
                {
                    "item_instance_id": str(item.item_instance_id),
                    "revision": item.revision,
                }
                for item in self.resulting_items
            ],
            "idempotency_key": self.idempotency_key,
            "occurred_at": self.occurred_at.isoformat(),
            "evidence_ref": self.evidence_ref,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class OutfitSelection:
    """An ordered equipped projection for one wearer; ownership is unchanged."""

    wearer_core_id: UUID
    item_instance_ids: tuple[UUID, ...]
    revision: int = 1
    privacy: str = "public"

    def __post_init__(self) -> None:
        _uuid(self.wearer_core_id, "wearer_core_id")
        _unique_uuid_tuple(self.item_instance_ids, "item_instance_ids", nonempty=False)
        if type(self.revision) is not int or self.revision < 1:
            raise InventoryError("revision must be a positive integer")
        if self.privacy not in {"public", "private", "adult"}:
            raise InventoryError("privacy is unknown")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": OUTFIT_SCHEMA,
            "wearer_core_id": str(self.wearer_core_id),
            "item_instance_ids": [str(item) for item in self.item_instance_ids],
            "revision": self.revision,
            "privacy": self.privacy,
        }


def item_revisions(items: Iterable[ItemInstance]) -> tuple[ItemRevision, ...]:
    return tuple(
        ItemRevision(item.item_instance_id, item.revision) for item in items
    )


def assert_holder(
    item: ItemInstance, actor_core_id: UUID, *, operation: TransferOperation
) -> None:
    """Check that the actor currently holds the item (custody gate only)."""
    if not isinstance(item, ItemInstance):
        raise TypeError("item must be ItemInstance")
    _uuid(actor_core_id, "actor_core_id")
    if item.holder_core_id != actor_core_id:
        raise NotItemHolder(
            f"actor does not currently hold {item.item_instance_id} for {operation.value}"
        )
    if not item.transferable and operation is not TransferOperation.RETURN:
        raise TransferDenied("item is marked non-transferable")


def assert_title(
    item: ItemInstance, actor_core_id: UUID, *, operation: TransferOperation
) -> None:
    """Check genuine title for gift/trade/swap; custody is checked separately."""
    _uuid(actor_core_id, "actor_core_id")
    if operation in TITLE_TRANSFER_OPERATIONS and item.owner_core_id != actor_core_id:
        raise NotItemOwner(
            f"actor does not own {item.item_instance_id} and cannot {operation.value} it"
        )


def assert_current_revisions(
    items: Iterable[ItemInstance], expected: Iterable[ItemRevision]
) -> None:
    """Fail closed on any stale or duplicate expected revision."""
    current = {item.item_instance_id: item.revision for item in items}
    seen: set[UUID] = set()
    for expected_item in expected:
        if expected_item.item_instance_id in seen:
            raise TransferConflict("duplicate expected item revision")
        seen.add(expected_item.item_instance_id)
        if current.get(expected_item.item_instance_id) != expected_item.revision:
            raise StaleItemRevision(
                f"item {expected_item.item_instance_id} no longer matches revision "
                f"{expected_item.revision}"
            )


def assert_not_wearing(item: ItemInstance, *, operation: TransferOperation) -> None:
    """Transfers of a worn item require a voluntary safe handoff/unequip step."""
    if item.equipped_by_core_id is not None and operation is not TransferOperation.RETURN:
        raise TransferConflict(
            f"item {item.item_instance_id} is currently worn; safe unequip/handoff required"
        )


def validate_offer_shape(offer: TransferOffer, *, now: datetime) -> None:
    """Validate an offer at the receiving boundary without applying it."""
    if not isinstance(offer, TransferOffer):
        raise TypeError("offer must be TransferOffer")
    offer.require_pending(now)
    if not offer.item_instance_ids and not offer.design_ids:
        raise InventoryError("offer contains no transferable subject")


__all__ = [
    "CustodyKind",
    "INVENTORY_SCHEMA",
    "ITEM_TRANSFER_OPERATIONS",
    "InventoryError",
    "ItemInstance",
    "ItemRevision",
    "MAX_ITEMS_PER_TRANSFER",
    "NotItemHolder",
    "NotItemOwner",
    "OUTFIT_SCHEMA",
    "OfferExpired",
    "OfferNotFound",
    "OfferStatus",
    "OutfitSelection",
    "RECIPROCAL_OPERATIONS",
    "StaleItemRevision",
    "TERMINAL_OFFER_STATUSES",
    "TITLE_TRANSFER_OPERATIONS",
    "TRANSFER_SCHEMA",
    "TransferConflict",
    "TransferDenied",
    "TransferOffer",
    "TransferOperation",
    "TransferReceipt",
    "assert_current_revisions",
    "assert_holder",
    "assert_not_wearing",
    "assert_title",
    "item_revisions",
    "validate_offer_shape",
]
