"""AEGIS inventory transfer, custody, outfit and armor acceptance behavior."""
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

import pytest

from sofia.modules.avatar.inventory import (
    EquipDenied,
    InventoryEngine,
    InventoryRenderFailed,
    InventoryUnavailable,
)
from sofia.modules.avatar.inventory_contract import (
    CustodyKind,
    ItemRevision,
    NotItemHolder,
    OfferStatus,
    StaleItemRevision,
    TransferConflict,
    TransferDenied,
    TransferOperation,
)
from sofia.modules.avatar.inventory_store import InventoryStore
from sofia.modules.avatar.wardrobe import Layer
from sofia.modules.avatar.wardrobe_equipment import (
    VERA_ARMOR_BY_DESIGN_ID,
    ArmorDecisionStatus,
    GarmentClass,
    WardrobeDesign,
    WardrobePrivacy,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
CORE_A = UUID(int=0xA)
CORE_B = UUID(int=0xB)
CORE_C = UUID(int=0xC)

UNDERSUIT = "vera_undersuit_mark_iv"
BASE = "vera_base_mark_iv"
CHEST = "vera_mark_iv_chest"
SHOULDER_LEFT = "vera_mark_iv_shoulder_left"
SHOULDER_RIGHT = "vera_mark_iv_shoulder_right"


def design(
    design_id: str,
    *,
    name: str = "Test garment",
    privacy: WardrobePrivacy = WardrobePrivacy.PUBLIC,
) -> WardrobeDesign:
    return WardrobeDesign(
        design_id=design_id,
        version=1,
        name=name,
        garment_class=GarmentClass.CLOTHING,
        garment_type="garment",
        layer=Layer.OUTER,
        slots=("torso",),
        coverage=("torso",),
        fit_anchors=("torso.front",),
        privacy=privacy,
    )


DESIGNS = {
    **VERA_ARMOR_BY_DESIGN_ID,
    "test_jacket": design("test_jacket", name="Test jacket"),
    "test_coat": design("test_coat", name="Test coat"),
    "private_dress": design(
        "private_dress", name="Private dress", privacy=WardrobePrivacy.PRIVATE
    ),
}


@pytest.fixture
def state_path(tmp_path):
    return bootstrap_canonical_sqlite(tmp_path / "sofia.db")


@pytest.fixture
def engine(state_path):
    return InventoryEngine(InventoryStore(state_path), DESIGNS)


def _lend(engine, item_id, sender=CORE_A, recipient=CORE_B, key="lend"):
    return engine.create_offer(
        TransferOperation.LEND,
        sender,
        recipient,
        item_instance_ids=(item_id,),
        idempotency_key=key,
        at=NOW,
    )


# -- WD-03 ------------------------------------------------------------------


def test_loan_one_jacket_and_return_keeps_single_instance(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = _lend(engine, item.item_instance_id)

    accepted = engine.accept(
        offer.offer_id,
        CORE_B,
        at=NOW + timedelta(seconds=1),
        loan_due_at=NOW + timedelta(days=7),
    )
    assert accepted.status is OfferStatus.ACCEPTED
    loaned = engine.item(item.item_instance_id)
    assert loaned.item_instance_id == item.item_instance_id
    assert loaned.owner_core_id == CORE_A
    assert loaned.holder_core_id == CORE_B
    assert loaned.custody is CustodyKind.LOANED
    assert loaned.loan_due_at == NOW + timedelta(days=7)
    assert len(engine.inventory(CORE_A)) == 1
    assert engine.inventory(CORE_B) == (loaned,)

    recalled = engine.request_recall(
        item.item_instance_id, CORE_A, at=NOW + timedelta(seconds=2)
    )
    assert recalled.owner_core_id == CORE_A
    assert recalled.holder_core_id == CORE_B
    assert recalled.recall_requested is True

    returned_offer = engine.create_offer(
        TransferOperation.RETURN,
        CORE_B,
        CORE_A,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="return-loan",
        at=NOW + timedelta(seconds=3),
    )
    engine.accept(returned_offer.offer_id, CORE_A, at=NOW + timedelta(seconds=4))

    returned = engine.item(item.item_instance_id)
    assert returned.item_instance_id == item.item_instance_id
    assert returned.owner_core_id == CORE_A
    assert returned.holder_core_id == CORE_A
    assert returned.custody is CustodyKind.OWNED
    assert returned.loan_due_at is None
    assert returned.recall_requested is False
    assert len(engine.inventory(CORE_A)) == 1


# -- WD-04 ------------------------------------------------------------------


def test_reciprocal_two_item_trade_is_atomic_and_replay_safe(engine):
    jacket = engine.mint("test_jacket", CORE_A, at=NOW)
    coat = engine.mint("test_coat", CORE_B, at=NOW)
    offer = engine.create_offer(
        TransferOperation.TRADE,
        CORE_A,
        CORE_B,
        item_instance_ids=(jacket.item_instance_id,),
        reciprocal_item_instance_ids=(coat.item_instance_id,),
        idempotency_key="trade-1",
        at=NOW,
    )

    receipt = engine.accept(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=1))
    assert receipt.status is OfferStatus.ACCEPTED

    traded_jacket = engine.item(jacket.item_instance_id)
    traded_coat = engine.item(coat.item_instance_id)
    assert traded_jacket.owner_core_id == CORE_B
    assert traded_jacket.holder_core_id == CORE_B
    assert traded_coat.owner_core_id == CORE_A
    assert traded_coat.holder_core_id == CORE_A
    assert {traded_jacket.design_id, traded_coat.design_id} == {
        "test_jacket",
        "test_coat",
    }
    assert len(engine.inventory(CORE_A)) == 1
    assert len(engine.inventory(CORE_B)) == 1

    with pytest.raises(TransferConflict):
        engine.accept(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=2))
    assert engine.item(jacket.item_instance_id) == traded_jacket
    assert engine.item(coat.item_instance_id) == traded_coat
    assert len(engine.receipts(offer_id=offer.offer_id)) == 1


# -- WD-05 ------------------------------------------------------------------


def test_concurrent_gift_offers_have_exactly_one_winner(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    first = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-first",
        at=NOW,
    )
    second = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_C,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-second",
        at=NOW,
    )

    engine.accept(first.offer_id, CORE_B, at=NOW + timedelta(seconds=1))
    with pytest.raises(StaleItemRevision):
        engine.accept(second.offer_id, CORE_C, at=NOW + timedelta(seconds=2))

    winner = engine.item(item.item_instance_id)
    assert winner.owner_core_id == CORE_B
    assert engine.get_offer(second.offer_id).status is OfferStatus.FAILED
    assert [receipt.status for receipt in engine.receipts(offer_id=second.offer_id)] == [
        OfferStatus.FAILED
    ]


# -- bilateral consent, exact recipient and worn-item safety ----------------


def test_gift_requires_exact_recipient_acceptance(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-consent",
        at=NOW,
    )
    assert engine.item(item.item_instance_id).owner_core_id == CORE_A
    with pytest.raises(TransferDenied):
        engine.accept(offer.offer_id, CORE_C, at=NOW + timedelta(seconds=1))
    assert engine.item(item.item_instance_id).owner_core_id == CORE_A
    engine.accept(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=2))
    assert engine.item(item.item_instance_id).owner_core_id == CORE_B


def test_worn_item_transfer_is_blocked_without_silent_unequip(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    engine.select_outfit(CORE_A, (item.item_instance_id,), at=NOW + timedelta(seconds=1))
    worn = engine.item(item.item_instance_id)
    assert worn.equipped_by_core_id == CORE_A

    with pytest.raises(TransferConflict):
        engine.create_offer(
            TransferOperation.GIFT,
            CORE_A,
            CORE_B,
            item_instance_ids=(item.item_instance_id,),
            idempotency_key="gift-worn",
            at=NOW + timedelta(seconds=2),
        )
    assert engine.item(item.item_instance_id) == worn
    assert engine.outfit(CORE_A)[0].item_instance_ids == (item.item_instance_id,)


# -- WD-06 ------------------------------------------------------------------


def test_renderer_failure_restores_ownership_and_records_failed(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-render-fail",
        at=NOW,
    )

    def failing_renderer(_offer, _items):
        raise RuntimeError("simulated renderer failure")

    with pytest.raises(InventoryRenderFailed):
        engine.accept(
            offer.offer_id,
            CORE_B,
            at=NOW + timedelta(seconds=1),
            render=failing_renderer,
        )

    restored = engine.item(item.item_instance_id)
    assert restored.owner_core_id == CORE_A
    assert restored.holder_core_id == CORE_A
    assert engine.get_offer(offer.offer_id).status is OfferStatus.FAILED
    assert [receipt.status for receipt in engine.receipts(offer_id=offer.offer_id)] == [
        OfferStatus.FAILED
    ]
    assert engine.store.audit.verify()[0] is True


def test_renderer_success_records_evidence_and_keeps_transfer(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-render-success",
        at=NOW,
    )

    receipt = engine.accept(
        offer.offer_id,
        CORE_B,
        at=NOW + timedelta(seconds=1),
        render=lambda _offer, _items: "renderer-receipt-42",
    )
    assert receipt.status is OfferStatus.ACCEPTED
    assert receipt.evidence_ref.startswith("aegis.inventory.render.")
    assert engine.item(item.item_instance_id).owner_core_id == CORE_B
    assert engine.reconcile(at=NOW + timedelta(seconds=2)) == {
        "expired": 0,
        "render_failed": 0,
    }


def test_stop_mid_render_is_reconciled_fail_closed_on_restart(state_path):
    store = InventoryStore(state_path)
    engine = InventoryEngine(store, DESIGNS)
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-stop",
        at=NOW,
    )

    class SimulationStop(BaseException):
        pass

    def stop(_offer, _items):
        raise SimulationStop()

    with pytest.raises(SimulationStop):
        engine.accept(
            offer.offer_id,
            CORE_B,
            at=NOW + timedelta(seconds=1),
            render=stop,
        )
    assert engine.item(item.item_instance_id).owner_core_id == CORE_B

    restarted = InventoryEngine(
        InventoryStore(state_path), DESIGNS, reconcile_on_start=False
    )
    result = restarted.reconcile(at=NOW + timedelta(seconds=2))
    assert result == {"expired": 0, "render_failed": 1}
    assert restarted.reconcile(at=NOW + timedelta(seconds=3)) == {
        "expired": 0,
        "render_failed": 0,
    }
    restored = restarted.item(item.item_instance_id)
    assert restored.owner_core_id == CORE_A
    assert restarted.get_offer(offer.offer_id).status is OfferStatus.FAILED
    assert [receipt.status for receipt in restarted.receipts(offer_id=offer.offer_id)] == [
        OfferStatus.FAILED
    ]


def test_expired_offer_cannot_complete(engine):
    item = engine.mint("test_jacket", CORE_A, at=NOW)
    offer = engine.create_offer(
        TransferOperation.GIFT,
        CORE_A,
        CORE_B,
        item_instance_ids=(item.item_instance_id,),
        idempotency_key="gift-expired",
        ttl_seconds=1,
        at=NOW,
    )
    with pytest.raises(Exception):
        engine.accept(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=2))
    assert engine.item(item.item_instance_id).owner_core_id == CORE_A
    assert engine.get_offer(offer.offer_id).status is OfferStatus.EXPIRED


# -- WD-07 ------------------------------------------------------------------


def test_restricted_garment_never_leaks_into_public_view(engine):
    public = engine.mint("test_jacket", CORE_A, at=NOW)
    private = engine.mint("private_dress", CORE_A, at=NOW)

    projection = engine.public_view(CORE_A)
    payload = json.dumps(projection.to_payload())

    assert "private_dress" not in payload
    assert private.design_id not in payload
    assert public.design_id in payload
    assert projection.redacted_count == 1
    assert engine.inventory(CORE_A, include_private=False) == (public,)


# -- outfit selection -------------------------------------------------------


def test_outfit_selection_is_ordered_revisioned_and_ownership_neutral(engine):
    jacket = engine.mint("test_jacket", CORE_A, at=NOW)
    coat = engine.mint("test_coat", CORE_A, at=NOW)
    selection = engine.select_outfit(
        CORE_A,
        (coat.item_instance_id, jacket.item_instance_id),
        expected_items=(
            ItemRevision(jacket.item_instance_id, jacket.revision),
            ItemRevision(coat.item_instance_id, coat.revision),
        ),
        at=NOW + timedelta(seconds=1),
    )
    assert selection.item_instance_ids == (
        coat.item_instance_id,
        jacket.item_instance_id,
    )
    assert selection.revision == 1
    assert engine.item(jacket.item_instance_id).owner_core_id == CORE_A
    assert engine.item(coat.item_instance_id).owner_core_id == CORE_A
    with pytest.raises(StaleItemRevision):
        engine.select_outfit(
            CORE_A,
            (jacket.item_instance_id,),
            expected_outfit_revision=selection.revision + 1,
            at=NOW + timedelta(seconds=2),
        )


# -- AR-01 / AR-08 ----------------------------------------------------------


def test_armor_part_without_undersuit_is_denied(engine):
    part = engine.mint(SHOULDER_LEFT, CORE_A, at=NOW)
    decision = engine.equip_item(
        CORE_A,
        part.item_instance_id,
        body_profile="human",
        require_fit=True,
        at=NOW + timedelta(seconds=1),
    )
    assert decision.status is ArmorDecisionStatus.DENIED
    assert engine.outfit(CORE_A) is None
    assert engine.item(part.item_instance_id) == part


def test_base_without_undersuit_is_denied(engine):
    base = engine.mint(BASE, CORE_A, at=NOW)
    decision = engine.equip_item(
        CORE_A,
        base.item_instance_id,
        body_profile="human",
        require_fit=True,
        at=NOW + timedelta(seconds=1),
    )
    assert decision.status is ArmorDecisionStatus.DENIED
    assert engine.outfit(CORE_A) is None


def test_partial_left_and_right_armor_allowed_with_valid_chain(engine):
    undersuit = engine.mint(UNDERSUIT, CORE_A, at=NOW)
    base = engine.mint(BASE, CORE_A, at=NOW)
    chest = engine.mint(CHEST, CORE_A, at=NOW)
    left = engine.mint(SHOULDER_LEFT, CORE_A, at=NOW)
    right = engine.mint(SHOULDER_RIGHT, CORE_A, at=NOW)

    decisions = [
        engine.equip_item(
            CORE_A,
            item.item_instance_id,
            body_profile="human",
            require_fit=True,
            at=NOW + timedelta(seconds=index + 1),
        )
        for index, item in enumerate((undersuit, base, chest, left, right))
    ]
    assert all(decision.allowed for decision in decisions)
    outfit = engine.outfit(CORE_A)[0]
    assert outfit.item_instance_ids == (
        undersuit.item_instance_id,
        base.item_instance_id,
        chest.item_instance_id,
        left.item_instance_id,
        right.item_instance_id,
    )
    assert all(
        engine.item(item.item_instance_id).owner_core_id == CORE_A
        for item in (undersuit, base, chest, left, right)
    )


def test_armor_fit_unknown_is_unavailable_not_fabricated(engine):
    undersuit = engine.mint(UNDERSUIT, CORE_C, at=NOW)
    decision = engine.equip_item(
        CORE_C,
        undersuit.item_instance_id,
        body_profile=None,
        require_fit=True,
        at=NOW + timedelta(seconds=1),
    )
    assert decision.status is ArmorDecisionStatus.UNAVAILABLE
    assert engine.outfit(CORE_C) is None


# -- AR-06 ------------------------------------------------------------------


def test_removing_undersuit_with_plates_requires_atomic_disassembly(engine):
    undersuit = engine.mint(UNDERSUIT, CORE_A, at=NOW)
    base = engine.mint(BASE, CORE_A, at=NOW)
    chest = engine.mint(CHEST, CORE_A, at=NOW)
    for index, item in enumerate((undersuit, base, chest)):
        engine.equip_item(
            CORE_A,
            item.item_instance_id,
            body_profile="human",
            require_fit=True,
            at=NOW + timedelta(seconds=index + 1),
        )
    before = engine.outfit(CORE_A)[0]

    decision = engine.unequip_item(
        CORE_A, undersuit.item_instance_id, at=NOW + timedelta(seconds=10)
    )
    assert decision.status is ArmorDecisionStatus.ATOMIC_DISASSEMBLY_REQUIRED
    assert base.item_instance_id in decision.dependent_item_ids
    assert chest.item_instance_id in decision.dependent_item_ids
    assert engine.outfit(CORE_A)[0] == before

    plan = engine.atomic_disassemble(
        CORE_A, undersuit.item_instance_id, at=NOW + timedelta(seconds=11)
    )
    assert set(plan) == {
        undersuit.item_instance_id,
        base.item_instance_id,
        chest.item_instance_id,
    }
    assert engine.outfit(CORE_A)[0].item_instance_ids == ()
    for item in (undersuit, base, chest):
        assert engine.item(item.item_instance_id).equipped_by_core_id is None


def test_transferring_worn_undersuit_with_plates_is_blocked(engine):
    undersuit = engine.mint(UNDERSUIT, CORE_A, at=NOW)
    base = engine.mint(BASE, CORE_A, at=NOW)
    for index, item in enumerate((undersuit, base)):
        engine.equip_item(
            CORE_A,
            item.item_instance_id,
            body_profile="human",
            require_fit=True,
            at=NOW + timedelta(seconds=index + 1),
        )
    with pytest.raises(TransferConflict):
        engine.create_offer(
            TransferOperation.GIFT,
            CORE_A,
            CORE_B,
            item_instance_ids=(undersuit.item_instance_id,),
            idempotency_key="gift-worn-undersuit",
            at=NOW + timedelta(seconds=3),
        )
    assert engine.item(undersuit.item_instance_id).owner_core_id == CORE_A
    assert engine.item(undersuit.item_instance_id).equipped_by_core_id == CORE_A


# -- design operations ------------------------------------------------------


def test_copy_design_requires_acceptance_and_mints_recipient_instance(engine):
    offer = engine.create_offer(
        TransferOperation.COPY_DESIGN,
        CORE_A,
        CORE_B,
        design_ids=("test_jacket",),
        idempotency_key="copy-jacket",
        at=NOW,
    )
    assert engine.inventory(CORE_B) == ()
    receipt = engine.accept(offer.offer_id, CORE_B, at=NOW + timedelta(seconds=1))
    assert receipt.status is OfferStatus.ACCEPTED
    copied = engine.inventory(CORE_B)
    assert len(copied) == 1
    assert copied[0].design_id == "test_jacket"
    assert copied[0].owner_core_id == CORE_B
