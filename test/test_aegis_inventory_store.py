"""Canonical persistence and restart evidence for wardrobe inventory."""
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import UUID

import pytest

from sofia.modules.avatar.inventory import InventoryEngine
from sofia.modules.avatar.inventory_contract import (
    CustodyKind,
    OfferStatus,
    TransferConflict,
    TransferOperation,
)
from sofia.modules.avatar.inventory_store import InventoryStore
from sofia.modules.avatar.wardrobe import Layer
from sofia.modules.avatar.wardrobe_equipment import (
    VERA_ARMOR_BY_DESIGN_ID,
    GarmentClass,
    WardrobeDesign,
    WardrobePrivacy,
)
from sofia.platform.state.canonical_sqlite import (
    CanonicalStateUnavailable,
    bootstrap_canonical_sqlite,
)


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
CORE_A = UUID(int=0xA)
CORE_B = UUID(int=0xB)


def jacket(design_id: str = "test_jacket") -> WardrobeDesign:
    return WardrobeDesign(
        design_id=design_id,
        version=1,
        name="Test jacket",
        garment_class=GarmentClass.CLOTHING,
        garment_type="jacket",
        layer=Layer.OUTER,
        slots=("torso",),
        coverage=("torso",),
        fit_anchors=("torso.front",),
    )


DESIGNS = {**VERA_ARMOR_BY_DESIGN_ID, "test_jacket": jacket(), "test_coat": jacket("test_coat")}


@pytest.fixture
def state_path(tmp_path):
    return bootstrap_canonical_sqlite(tmp_path / "sofia.db")


@pytest.fixture
def engine(state_path):
    return InventoryEngine(InventoryStore(state_path), DESIGNS)


def test_store_uses_one_canonical_file_and_additive_tables(tmp_path, state_path):
    InventoryStore(state_path)
    assert state_path.exists()
    assert not (tmp_path / "wardrobe.db").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["sofia.db"]
    with sqlite3.connect(state_path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "wardrobe_item_instance",
        "wardrobe_transfer_offer",
        "wardrobe_transfer_receipt",
        "wardrobe_outfit_selection",
    }.issubset(tables)


def test_store_requires_existing_authorized_canonical_state(tmp_path):
    with pytest.raises(CanonicalStateUnavailable):
        InventoryStore(tmp_path / "missing.db")


def test_mint_persists_one_instance_across_store_restart(state_path):
    engine = InventoryEngine(InventoryStore(state_path), DESIGNS)
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    reopened = InventoryEngine(InventoryStore(state_path), DESIGNS)
    loaded = reopened.item(item.item_instance_id)
    assert loaded == item
    assert loaded.revision == 1
    assert loaded.owner_core_id == CORE_A
    assert loaded.holder_core_id == CORE_A
    assert loaded.custody is CustodyKind.OWNED
    assert len(reopened.inventory(CORE_A)) == 1


def test_offer_idempotency_returns_the_same_single_row(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    first = engine.create_offer(
        TransferOperation.LEND,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="lend-once",
        at=NOW,
    )
    second = engine.create_offer(
        TransferOperation.LEND,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="lend-once",
        at=NOW,
    )
    assert first.offer_id == second.offer_id
    assert len(engine.offers()) == 1


def test_restart_reconciliation_expires_an_overdue_offer_exactly_once(state_path):
    engine = InventoryEngine(InventoryStore(state_path), DESIGNS)
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.LEND,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="lend-expiring",
        ttl_seconds=5,
        at=NOW,
    )

    restarted = InventoryEngine(
        InventoryStore(state_path), DESIGNS, reconcile_on_start=False
    )
    first = restarted.reconcile(at=NOW + timedelta(seconds=6))
    second = restarted.reconcile(at=NOW + timedelta(seconds=7))

    assert first == {"expired": 1, "render_failed": 0}
    assert second == {"expired": 0, "render_failed": 0}
    assert restarted.get_offer(offer.offer_id).status is OfferStatus.EXPIRED
    receipts = restarted.receipts(offer_id=offer.offer_id)
    assert [receipt.status for receipt in receipts] == [OfferStatus.EXPIRED]
    assert restarted.item(item.item_instance_id).owner_core_id == CORE_A


def test_receipts_and_audit_chain_are_append_only(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-decline",
        at=NOW,
    )
    receipt = engine.decline(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=1))
    with pytest.raises(TransferConflict):
        engine.decline(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=2))
    assert [entry.receipt_id for entry in engine.receipts(offer_id=offer.offer_id)] == [
        receipt.receipt_id
    ]
    valid, reason = engine.store.audit.verify()
    assert valid, reason
    assert engine.item(item.item_instance_id).owner_core_id == CORE_A
