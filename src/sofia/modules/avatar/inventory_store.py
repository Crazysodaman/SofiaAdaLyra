"""Canonical SQLite persistence for per-Core wardrobe inventory and transfers.

This module owns four additive tables in the single canonical Platform state
file.  It never creates a sidecar database, never opens a second writer and
never mutates another owner's tables.  An item instance row is the one physical
virtual object; transfers update that row instead of cloning it.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import UUID

from sofia.platform.safe.audit import AuditChain
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .inventory_contract import (
    CustodyKind,
    InventoryError,
    ItemInstance,
    ItemRevision,
    OfferStatus,
    OutfitSelection,
    StaleItemRevision,
    TransferOffer,
    TransferOperation,
    TransferReceipt,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS wardrobe_item_instance (
    item_instance_id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL,
    design_version INTEGER NOT NULL CHECK(design_version >= 1),
    owner_core_id TEXT NOT NULL,
    holder_core_id TEXT NOT NULL,
    custody TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    transferable INTEGER NOT NULL CHECK(transferable IN (0, 1)),
    private_to_owner INTEGER NOT NULL CHECK(private_to_owner IN (0, 1)),
    loan_due_at TEXT,
    recall_requested INTEGER NOT NULL CHECK(recall_requested IN (0, 1)),
    equipped_by_core_id TEXT
);

CREATE INDEX IF NOT EXISTS wardrobe_item_instance_owner
    ON wardrobe_item_instance(owner_core_id);
CREATE INDEX IF NOT EXISTS wardrobe_item_instance_holder
    ON wardrobe_item_instance(holder_core_id);

CREATE TABLE IF NOT EXISTS wardrobe_transfer_offer (
    offer_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    sender_core_id TEXT NOT NULL,
    recipient_core_id TEXT NOT NULL,
    item_instance_ids_json TEXT NOT NULL,
    reciprocal_item_instance_ids_json TEXT NOT NULL,
    expected_items_json TEXT NOT NULL,
    design_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    note TEXT,
    previous_items_json TEXT,
    UNIQUE(sender_core_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS wardrobe_transfer_offer_recipient
    ON wardrobe_transfer_offer(recipient_core_id, status);
CREATE INDEX IF NOT EXISTS wardrobe_transfer_offer_expiry
    ON wardrobe_transfer_offer(status, expires_at);

CREATE TABLE IF NOT EXISTS wardrobe_transfer_receipt (
    receipt_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_core_id TEXT NOT NULL,
    item_instance_ids_json TEXT NOT NULL,
    resulting_items_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    reason TEXT,
    UNIQUE(offer_id, status)
);

CREATE INDEX IF NOT EXISTS wardrobe_transfer_receipt_offer
    ON wardrobe_transfer_receipt(offer_id);

CREATE TABLE IF NOT EXISTS wardrobe_outfit_selection (
    wearer_core_id TEXT PRIMARY KEY,
    item_instance_ids_json TEXT NOT NULL,
    item_revisions_json TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    privacy TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InventoryError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _uuid_list(value: str) -> tuple[UUID, ...]:
    return tuple(UUID(item) for item in json.loads(value))


def _revision_list(value: str) -> tuple[ItemRevision, ...]:
    return tuple(
        ItemRevision(UUID(item["item_instance_id"]), int(item["revision"]))
        for item in json.loads(value)
    )


def _revision_payload(items: Iterable[ItemRevision]) -> list[dict[str, object]]:
    return [
        {"item_instance_id": str(item.item_instance_id), "revision": item.revision}
        for item in items
    ]


class InventoryStore:
    """Own the additive wardrobe inventory schema in one canonical file."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        self._initialize()

    def _initialize(self) -> None:
        with self.transaction() as db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def reader(self):
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    # -- audit -------------------------------------------------------------

    def append_audit(
        self,
        db: sqlite3.Connection,
        *,
        actor_core_id: UUID,
        event_type: str,
        payload: dict[str, object],
        occurred_at: datetime,
    ) -> str:
        return self.audit.append_in_transaction(
            db,
            actor_id=str(actor_core_id),
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
        )

    # -- item instances ----------------------------------------------------

    @staticmethod
    def _item_values(item: ItemInstance) -> tuple[object, ...]:
        return (
            str(item.item_instance_id),
            item.design_id,
            item.design_version,
            str(item.owner_core_id),
            str(item.holder_core_id),
            item.custody.value,
            item.revision,
            _iso(item.created_at),
            _iso(item.updated_at),
            1 if item.transferable else 0,
            1 if item.private_to_owner else 0,
            None if item.loan_due_at is None else _iso(item.loan_due_at),
            1 if item.recall_requested else 0,
            None if item.equipped_by_core_id is None else str(item.equipped_by_core_id),
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> ItemInstance:
        return ItemInstance(
            item_instance_id=UUID(row["item_instance_id"]),
            design_id=row["design_id"],
            design_version=int(row["design_version"]),
            owner_core_id=UUID(row["owner_core_id"]),
            holder_core_id=UUID(row["holder_core_id"]),
            custody=CustodyKind(row["custody"]),
            revision=int(row["revision"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
            transferable=bool(row["transferable"]),
            private_to_owner=bool(row["private_to_owner"]),
            loan_due_at=None if row["loan_due_at"] is None else _dt(row["loan_due_at"]),
            recall_requested=bool(row["recall_requested"]),
            equipped_by_core_id=(
                None if row["equipped_by_core_id"] is None
                else UUID(row["equipped_by_core_id"])
            ),
        )

    def insert_item(self, db: sqlite3.Connection, item: ItemInstance) -> None:
        db.execute(
            """
            INSERT INTO wardrobe_item_instance (
                item_instance_id, design_id, design_version, owner_core_id,
                holder_core_id, custody, revision, created_at, updated_at,
                transferable, private_to_owner, loan_due_at, recall_requested,
                equipped_by_core_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._item_values(item),
        )

    def get_item(self, db: sqlite3.Connection, item_instance_id: UUID) -> ItemInstance | None:
        row = db.execute(
            "SELECT * FROM wardrobe_item_instance WHERE item_instance_id = ?",
            (str(item_instance_id),),
        ).fetchone()
        return None if row is None else self._item_from_row(row)

    def get_items(
        self, db: sqlite3.Connection, ids: Iterable[UUID]
    ) -> dict[UUID, ItemInstance]:
        values = tuple(dict.fromkeys(ids))
        if not values:
            return {}
        placeholders = ",".join("?" for _ in values)
        rows = db.execute(
            f"SELECT * FROM wardrobe_item_instance WHERE item_instance_id IN ({placeholders})",
            tuple(str(item) for item in values),
        ).fetchall()
        return {
            UUID(row["item_instance_id"]): self._item_from_row(row) for row in rows
        }

    def list_items(
        self, db: sqlite3.Connection, *, core_id: UUID | None = None
    ) -> tuple[ItemInstance, ...]:
        if core_id is None:
            rows = db.execute(
                "SELECT * FROM wardrobe_item_instance ORDER BY created_at, item_instance_id"
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM wardrobe_item_instance
                WHERE owner_core_id = ? OR holder_core_id = ?
                ORDER BY created_at, item_instance_id
                """,
                (str(core_id), str(core_id)),
            ).fetchall()
        return tuple(self._item_from_row(row) for row in rows)

    def update_item(
        self,
        db: sqlite3.Connection,
        item: ItemInstance,
        *,
        expected_revision: int,
    ) -> None:
        if item.revision != expected_revision + 1:
            raise InventoryError("updated item revision must advance by exactly one")
        cursor = db.execute(
            """
            UPDATE wardrobe_item_instance SET
                design_id = ?, design_version = ?, owner_core_id = ?,
                holder_core_id = ?, custody = ?, revision = ?, created_at = ?,
                updated_at = ?, transferable = ?, private_to_owner = ?,
                loan_due_at = ?, recall_requested = ?, equipped_by_core_id = ?
            WHERE item_instance_id = ? AND revision = ?
            """,
            (
                item.design_id,
                item.design_version,
                str(item.owner_core_id),
                str(item.holder_core_id),
                item.custody.value,
                item.revision,
                _iso(item.created_at),
                _iso(item.updated_at),
                1 if item.transferable else 0,
                1 if item.private_to_owner else 0,
                None if item.loan_due_at is None else _iso(item.loan_due_at),
                1 if item.recall_requested else 0,
                None if item.equipped_by_core_id is None else str(item.equipped_by_core_id),
                str(item.item_instance_id),
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleItemRevision(
                f"item {item.item_instance_id} no longer matches revision {expected_revision}"
            )

    def delete_item(self, db: sqlite3.Connection, item_instance_id: UUID) -> None:
        db.execute(
            "DELETE FROM wardrobe_item_instance WHERE item_instance_id = ?",
            (str(item_instance_id),),
        )

    # -- offers ------------------------------------------------------------

    @staticmethod
    def _offer_values(offer: TransferOffer) -> tuple[object, ...]:
        return (
            str(offer.offer_id),
            offer.operation.value,
            str(offer.sender_core_id),
            str(offer.recipient_core_id),
            _json([str(item) for item in offer.item_instance_ids]),
            _json([str(item) for item in offer.reciprocal_item_instance_ids]),
            _json(_revision_payload(offer.expected_items)),
            _json(list(offer.design_ids)),
            _iso(offer.created_at),
            _iso(offer.expires_at),
            offer.idempotency_key,
            offer.status.value,
            offer.revision,
            offer.note,
        )

    @staticmethod
    def _offer_from_row(row: sqlite3.Row) -> TransferOffer:
        return TransferOffer(
            offer_id=UUID(row["offer_id"]),
            operation=TransferOperation(row["operation"]),
            sender_core_id=UUID(row["sender_core_id"]),
            recipient_core_id=UUID(row["recipient_core_id"]),
            item_instance_ids=_uuid_list(row["item_instance_ids_json"]),
            reciprocal_item_instance_ids=_uuid_list(
                row["reciprocal_item_instance_ids_json"]
            ),
            expected_items=_revision_list(row["expected_items_json"]),
            design_ids=tuple(json.loads(row["design_ids_json"])),
            created_at=_dt(row["created_at"]),
            expires_at=_dt(row["expires_at"]),
            idempotency_key=row["idempotency_key"],
            status=OfferStatus(row["status"]),
            revision=int(row["revision"]),
            note=row["note"],
        )

    def insert_offer(self, db: sqlite3.Connection, offer: TransferOffer) -> None:
        db.execute(
            """
            INSERT INTO wardrobe_transfer_offer (
                offer_id, operation, sender_core_id, recipient_core_id,
                item_instance_ids_json, reciprocal_item_instance_ids_json,
                expected_items_json, design_ids_json, created_at, expires_at,
                idempotency_key, status, revision, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._offer_values(offer),
        )

    def get_offer(
        self, db: sqlite3.Connection, offer_id: UUID
    ) -> TransferOffer | None:
        row = db.execute(
            "SELECT * FROM wardrobe_transfer_offer WHERE offer_id = ?",
            (str(offer_id),),
        ).fetchone()
        return None if row is None else self._offer_from_row(row)

    def find_offer_by_idempotency(
        self, db: sqlite3.Connection, sender_core_id: UUID, idempotency_key: str
    ) -> TransferOffer | None:
        row = db.execute(
            """
            SELECT * FROM wardrobe_transfer_offer
            WHERE sender_core_id = ? AND idempotency_key = ?
            """,
            (str(sender_core_id), idempotency_key),
        ).fetchone()
        return None if row is None else self._offer_from_row(row)

    def update_offer(
        self,
        db: sqlite3.Connection,
        offer: TransferOffer,
        *,
        expected_revision: int,
        previous_items_json: str | None = None,
    ) -> None:
        if offer.revision != expected_revision + 1:
            raise InventoryError("updated offer revision must advance by exactly one")
        cursor = db.execute(
            """
            UPDATE wardrobe_transfer_offer SET
                operation = ?, sender_core_id = ?, recipient_core_id = ?,
                item_instance_ids_json = ?, reciprocal_item_instance_ids_json = ?,
                expected_items_json = ?, design_ids_json = ?, created_at = ?,
                expires_at = ?, idempotency_key = ?, status = ?, revision = ?,
                note = ?, previous_items_json = ?
            WHERE offer_id = ? AND revision = ?
            """,
            (
                offer.operation.value,
                str(offer.sender_core_id),
                str(offer.recipient_core_id),
                _json([str(item) for item in offer.item_instance_ids]),
                _json([str(item) for item in offer.reciprocal_item_instance_ids]),
                _json(_revision_payload(offer.expected_items)),
                _json(list(offer.design_ids)),
                _iso(offer.created_at),
                _iso(offer.expires_at),
                offer.idempotency_key,
                offer.status.value,
                offer.revision,
                offer.note,
                previous_items_json,
                str(offer.offer_id),
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleItemRevision(
                f"offer {offer.offer_id} no longer matches revision {expected_revision}"
            )

    def get_offer_guard(
        self, db: sqlite3.Connection, offer_id: UUID
    ) -> str | None:
        row = db.execute(
            "SELECT previous_items_json FROM wardrobe_transfer_offer WHERE offer_id = ?",
            (str(offer_id),),
        ).fetchone()
        return None if row is None else row["previous_items_json"]

    def clear_offer_guard(self, db: sqlite3.Connection, offer_id: UUID) -> None:
        db.execute(
            "UPDATE wardrobe_transfer_offer SET previous_items_json = NULL WHERE offer_id = ?",
            (str(offer_id),),
        )

    def list_offers(
        self, db: sqlite3.Connection, *, status: OfferStatus | None = None
    ) -> tuple[TransferOffer, ...]:
        if status is None:
            rows = db.execute(
                "SELECT * FROM wardrobe_transfer_offer ORDER BY created_at, offer_id"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM wardrobe_transfer_offer WHERE status = ? ORDER BY created_at, offer_id",
                (status.value,),
            ).fetchall()
        return tuple(self._offer_from_row(row) for row in rows)

    def list_render_pending_offers(
        self, db: sqlite3.Connection
    ) -> tuple[TransferOffer, ...]:
        rows = db.execute(
            """
            SELECT * FROM wardrobe_transfer_offer
            WHERE status = ? AND previous_items_json IS NOT NULL
            ORDER BY created_at, offer_id
            """,
            (OfferStatus.ACCEPTED.value,),
        ).fetchall()
        return tuple(self._offer_from_row(row) for row in rows)

    # -- receipts ----------------------------------------------------------

    @staticmethod
    def _receipt_values(receipt: TransferReceipt) -> tuple[object, ...]:
        return (
            str(receipt.receipt_id),
            str(receipt.offer_id),
            receipt.operation.value,
            receipt.status.value,
            str(receipt.actor_core_id),
            _json([str(item) for item in receipt.item_instance_ids]),
            _json(_revision_payload(receipt.resulting_items)),
            receipt.idempotency_key,
            _iso(receipt.occurred_at),
            receipt.evidence_ref,
            receipt.reason,
        )

    @staticmethod
    def _receipt_from_row(row: sqlite3.Row) -> TransferReceipt:
        return TransferReceipt(
            receipt_id=UUID(row["receipt_id"]),
            offer_id=UUID(row["offer_id"]),
            operation=TransferOperation(row["operation"]),
            status=OfferStatus(row["status"]),
            actor_core_id=UUID(row["actor_core_id"]),
            item_instance_ids=_uuid_list(row["item_instance_ids_json"]),
            resulting_items=_revision_list(row["resulting_items_json"]),
            idempotency_key=row["idempotency_key"],
            occurred_at=_dt(row["occurred_at"]),
            evidence_ref=row["evidence_ref"],
            reason=row["reason"],
        )

    def insert_receipt(
        self, db: sqlite3.Connection, receipt: TransferReceipt
    ) -> None:
        db.execute(
            """
            INSERT INTO wardrobe_transfer_receipt (
                receipt_id, offer_id, operation, status, actor_core_id,
                item_instance_ids_json, resulting_items_json, idempotency_key,
                occurred_at, evidence_ref, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._receipt_values(receipt),
        )

    def get_receipt(
        self, db: sqlite3.Connection, receipt_id: UUID
    ) -> TransferReceipt | None:
        row = db.execute(
            "SELECT * FROM wardrobe_transfer_receipt WHERE receipt_id = ?",
            (str(receipt_id),),
        ).fetchone()
        return None if row is None else self._receipt_from_row(row)

    def find_receipt(
        self,
        db: sqlite3.Connection,
        offer_id: UUID,
        status: OfferStatus,
    ) -> TransferReceipt | None:
        row = db.execute(
            """
            SELECT * FROM wardrobe_transfer_receipt
            WHERE offer_id = ? AND status = ?
            """,
            (str(offer_id), status.value),
        ).fetchone()
        return None if row is None else self._receipt_from_row(row)

    def list_receipts(
        self, db: sqlite3.Connection, *, offer_id: UUID | None = None
    ) -> tuple[TransferReceipt, ...]:
        if offer_id is None:
            rows = db.execute(
                "SELECT * FROM wardrobe_transfer_receipt ORDER BY occurred_at, receipt_id"
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM wardrobe_transfer_receipt
                WHERE offer_id = ? ORDER BY occurred_at, receipt_id
                """,
                (str(offer_id),),
            ).fetchall()
        return tuple(self._receipt_from_row(row) for row in rows)

    # -- outfits -----------------------------------------------------------

    def get_outfit(
        self, db: sqlite3.Connection, wearer_core_id: UUID
    ) -> tuple[OutfitSelection, tuple[ItemRevision, ...]] | None:
        row = db.execute(
            "SELECT * FROM wardrobe_outfit_selection WHERE wearer_core_id = ?",
            (str(wearer_core_id),),
        ).fetchone()
        if row is None:
            return None
        selection = OutfitSelection(
            wearer_core_id=UUID(row["wearer_core_id"]),
            item_instance_ids=_uuid_list(row["item_instance_ids_json"]),
            revision=int(row["revision"]),
            privacy=row["privacy"],
        )
        return selection, _revision_list(row["item_revisions_json"])

    def put_outfit(
        self,
        db: sqlite3.Connection,
        selection: OutfitSelection,
        item_revisions: Iterable[ItemRevision],
        *,
        expected_revision: int | None,
        updated_at: datetime,
    ) -> None:
        revisions = tuple(item_revisions)
        if selection.revision != (1 if expected_revision is None else expected_revision + 1):
            raise InventoryError("outfit revision must advance by exactly one")
        if expected_revision is None:
            cursor = db.execute(
                """
                INSERT INTO wardrobe_outfit_selection (
                    wearer_core_id, item_instance_ids_json, item_revisions_json,
                    revision, privacy, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(wearer_core_id) DO NOTHING
                """,
                (
                    str(selection.wearer_core_id),
                    _json([str(item) for item in selection.item_instance_ids]),
                    _json(_revision_payload(revisions)),
                    selection.revision,
                    selection.privacy,
                    _iso(updated_at),
                ),
            )
            if cursor.rowcount != 1:
                raise StaleItemRevision("outfit was created concurrently")
            return
        cursor = db.execute(
            """
            UPDATE wardrobe_outfit_selection SET
                item_instance_ids_json = ?, item_revisions_json = ?,
                revision = ?, privacy = ?, updated_at = ?
            WHERE wearer_core_id = ? AND revision = ?
            """,
            (
                _json([str(item) for item in selection.item_instance_ids]),
                _json(_revision_payload(revisions)),
                selection.revision,
                selection.privacy,
                _iso(updated_at),
                str(selection.wearer_core_id),
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleItemRevision(
                f"outfit for {selection.wearer_core_id} no longer matches "
                f"revision {expected_revision}"
            )


__all__ = ["InventoryStore"]
