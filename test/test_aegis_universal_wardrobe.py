"""Source-level acceptance tests for WD-01..WD-07 universal wardrobe behavior.

These tests exercise metadata and contract boundaries only.  They do not claim
installed assets, a live renderer, cross-Core mesh fit or applied ownership
store mutations.  WD-04..WD-06 coordinate with the shared inventory contract by
import only; the transfer engine itself belongs to the inventory slice.
"""
from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from sofia.modules.avatar.fit import (
    WearerFitStatus,
    WearerProfile,
    evaluate_wearer_fit,
)
from sofia.modules.avatar.inventory_contract import (
    CustodyKind,
    ItemInstance,
    ItemRevision,
    OfferStatus,
    StaleItemRevision,
    TransferConflict,
    TransferOffer,
    TransferOperation,
    assert_current_revisions,
)
from sofia.modules.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.modules.avatar.wardrobe_equipment import (
    VERA_ARMOR_BY_DESIGN_ID,
    VERA_ARMOR_DESIGNS,
    WardrobePrivacy,
)
from sofia.modules.avatar.wardrobe_equipment_catalog import (
    CatalogAudience,
    EquipmentDesignRegistry,
    SAFE_COVERED_DEFAULT_NAME,
    equipped_item_from_design_id,
    garment_from_wardrobe_design,
    project_catalog,
    wardrobe_design_from_garment,
)

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
OWNER = UUID(int=101)
BORROWER = UUID(int=102)


def _design(design_id: str):
    return VERA_ARMOR_BY_DESIGN_ID[design_id]


def _private_design():
    return replace(
        _design("vera_base_mark_iv_cqb"),
        design_id="test.private.base",
        name="Test private catalog base",
        privacy=WardrobePrivacy.PRIVATE,
        content_rating="lewd",
    )


def _adult_design():
    return replace(
        _design("vera_base_mark_v"),
        design_id="test.adult.base",
        name="Test adult catalog base",
        privacy=WardrobePrivacy.ADULT,
        content_rating="explicit",
    )


def _item_instance(
    item_id: UUID,
    *,
    design_id: str,
    owner: UUID,
    holder: UUID | None = None,
    revision: int = 1,
    created_at: datetime = NOW,
) -> ItemInstance:
    resolved_holder = owner if holder is None else holder
    return ItemInstance(
        item_instance_id=item_id,
        design_id=design_id,
        design_version=1,
        owner_core_id=owner,
        holder_core_id=resolved_holder,
        custody=(
            CustodyKind.OWNED
            if resolved_holder == owner
            else CustodyKind.LOANED
        ),
        revision=revision,
        created_at=created_at,
        updated_at=created_at,
    )


def _trade_offer(
    *,
    item_a: ItemInstance,
    item_b: ItemInstance,
    created_at: datetime = NOW,
    expires_at: datetime = NOW + timedelta(hours=1),
) -> TransferOffer:
    return TransferOffer(
        offer_id=UUID(int=300),
        operation=TransferOperation.TRADE,
        sender_core_id=item_a.owner_core_id,
        recipient_core_id=item_b.owner_core_id,
        item_instance_ids=(item_a.item_instance_id,),
        reciprocal_item_instance_ids=(item_b.item_instance_id,),
        expected_items=(
            ItemRevision(item_a.item_instance_id, item_a.revision),
            ItemRevision(item_b.item_instance_id, item_b.revision),
        ),
        created_at=created_at,
        expires_at=expires_at,
        idempotency_key="test.trade.001",
        design_ids=(item_a.design_id, item_b.design_id),
    )


def test_wd01_all_designs_are_discoverable_and_private_contents_are_scoped():
    private = _private_design()
    adult = _adult_design()
    designs = (*VERA_ARMOR_DESIGNS, private, adult)

    for audience in (
        CatalogAudience.PUBLIC,
        CatalogAudience.GUEST,
        CatalogAudience.PRIVATE,
        CatalogAudience.ADULT,
    ):
        view = project_catalog(designs, audience)
        assert set(view.design_ids) == {design.design_id for design in designs}

    public = project_catalog(designs, CatalogAudience.PUBLIC)
    assert public.entry(private.design_id).metadata_visible is False
    assert public.entry(private.design_id).safe_covered_default is True
    assert public.entry(adult.design_id).metadata_visible is False
    visible_public = public.entry("vera_base_mark_iv_cqb")
    assert visible_public.metadata_visible is True
    assert visible_public.armor is not None
    assert visible_public.name == _design("vera_base_mark_iv_cqb").name

    private_view = project_catalog(designs, CatalogAudience.PRIVATE)
    assert private_view.entry(private.design_id).metadata_visible is True
    assert private_view.entry(adult.design_id).metadata_visible is False

    adult_view = project_catalog(designs, CatalogAudience.ADULT)
    assert adult_view.entry(private.design_id).metadata_visible is True
    assert adult_view.entry(adult.design_id).metadata_visible is True

    parameters = inspect.signature(project_catalog).parameters
    assert not {"gender", "origin", "core", "core_id"} & set(parameters)


def test_wd02_cross_core_fit_is_honest_and_leaves_canonical_body_unchanged():
    base = _design("vera_base_mark_iv_cqb")
    assert base.armor is not None
    supported = replace(
        base,
        asset_ref="test.asset.cqb.base",
        armor=replace(base.armor, compatible_body_profiles=("vera",)),
    )
    vera = WearerProfile(
        body_profile="vera",
        measurements={"height_inches": 79.0},
        anchors=supported.fit_anchors,
        rig_id="vera.rig.v1",
    )
    fitted = evaluate_wearer_fit(
        supported, vera, evidence_ref="test.renderer.receipt", asset_verified=True,
    )
    assert fitted.status is WearerFitStatus.FITTED
    assert fitted.mutates_canonical_body is False
    assert fitted.metadata_only is False

    mack = WearerProfile(
        body_profile="mack",
        measurements={"height_inches": 72.0},
        anchors=supported.fit_anchors,
        rig_id="mack.rig.v1",
    )
    measurements_before = tuple(mack.measurements.items())
    unsupported = evaluate_wearer_fit(
        supported, mack, evidence_ref="test.renderer.receipt", asset_verified=True,
    )
    assert unsupported.status is WearerFitStatus.UNSUPPORTED
    assert "body profile" in unsupported.reason
    assert unsupported.mutates_canonical_body is False
    assert tuple(mack.measurements.items()) == measurements_before

    missing_anchors = WearerProfile(
        body_profile="vera",
        measurements={"height_inches": 79.0},
        anchors=("torso.front",),
        rig_id="vera.rig.v1",
    )
    missing = evaluate_wearer_fit(
        supported,
        missing_anchors,
        evidence_ref="test.renderer.receipt",
        asset_verified=True,
    )
    assert missing.status is WearerFitStatus.UNSUPPORTED
    assert missing.missing_anchors
    assert "anchors" in missing.reason

    unknown = WearerProfile(body_profile=None, anchors=supported.fit_anchors)
    assert evaluate_wearer_fit(supported, unknown).status is WearerFitStatus.UNAVAILABLE

    no_asset = replace(supported, asset_ref=None)
    assert evaluate_wearer_fit(
        no_asset, vera, evidence_ref="test.renderer.receipt", asset_verified=True,
    ).status is WearerFitStatus.UNAVAILABLE

    no_evidence = evaluate_wearer_fit(supported, vera, asset_verified=True)
    assert no_evidence.status is WearerFitStatus.UNAVAILABLE


def test_wd03_loan_and_return_keep_one_instance_and_the_original_owner():
    item = _item_instance(
        UUID(int=201), design_id="vera_base_mark_iv_cqb", owner=OWNER,
    )
    registry = EquipmentDesignRegistry(VERA_ARMOR_DESIGNS)
    projected_before = equipped_item_from_design_id(
        item.item_instance_id, item.design_id, registry,
        design_version=item.design_version,
    )

    loaned = item.with_revision(
        holder_core_id=BORROWER,
        custody=CustodyKind.LOANED,
        updated_at=NOW + timedelta(hours=1),
    )
    assert loaned.item_instance_id == item.item_instance_id
    assert loaned.owner_core_id == OWNER
    assert loaned.holder_core_id == BORROWER
    assert loaned.revision == item.revision + 1

    projected_loan = equipped_item_from_design_id(
        loaned.item_instance_id, loaned.design_id, registry,
        design_version=loaned.design_version,
    )
    assert projected_loan.item_instance_id == projected_before.item_instance_id
    assert projected_loan.design_id == projected_before.design_id

    returned = loaned.with_revision(
        holder_core_id=OWNER,
        custody=CustodyKind.OWNED,
        updated_at=NOW + timedelta(hours=2),
    )
    assert returned.item_instance_id == item.item_instance_id
    assert returned.owner_core_id == OWNER
    assert returned.holder_core_id == OWNER


def test_wd04_reciprocal_trade_contract_is_bilateral_and_uses_unique_instances():
    item_a = _item_instance(
        UUID(int=202), design_id="vera_cqb_chest", owner=OWNER,
    )
    item_b = _item_instance(
        UUID(int=203), design_id="vera_odst_chest", owner=BORROWER,
    )
    offer = _trade_offer(item_a=item_a, item_b=item_b)

    assert offer.operation is TransferOperation.TRADE
    assert offer.is_pending()
    assert set(offer.item_instance_ids).isdisjoint(offer.reciprocal_item_instance_ids)
    assert {revision.item_instance_id for revision in offer.expected_items} == {
        item_a.item_instance_id, item_b.item_instance_id,
    }
    assert_current_revisions((item_a, item_b), offer.expected_items)
    assert offer.to_payload()["operation"] == "trade"
    assert offer.to_payload()["status"] == "pending"


def test_wd05_concurrent_revision_conflict_is_exact_and_duplicate_free():
    item = _item_instance(
        UUID(int=204), design_id="vera_cqb_chest", owner=OWNER,
    )
    changed = item.with_revision(updated_at=NOW + timedelta(minutes=1))
    with pytest.raises(StaleItemRevision):
        assert_current_revisions(
            (changed,),
            (ItemRevision(item.item_instance_id, item.revision),),
        )
    assert changed.revision == item.revision + 1


def test_wd06_terminal_or_expired_offer_cannot_claim_false_acceptance():
    item_a = _item_instance(
        UUID(int=205), design_id="vera_cqb_chest", owner=OWNER,
    )
    item_b = _item_instance(
        UUID(int=206), design_id="vera_odst_chest", owner=BORROWER,
    )
    offer = _trade_offer(item_a=item_a, item_b=item_b)

    accepted = replace(offer, status=OfferStatus.ACCEPTED)
    with pytest.raises(TransferConflict):
        accepted.require_pending(NOW)

    expired = replace(
        offer,
        created_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(TransferConflict):
        expired.require_pending(NOW)


def test_wd07_public_and_guest_views_never_leak_restricted_metadata():
    private = _private_design()
    adult = _adult_design()
    designs = (*VERA_ARMOR_DESIGNS, private, adult)

    for audience in (CatalogAudience.PUBLIC, CatalogAudience.GUEST):
        view = project_catalog(designs, audience)
        for design in (private, adult):
            entry = view.entry(design.design_id)
            assert entry.safe_covered_default is True
            assert entry.metadata_visible is False
            assert entry.name == SAFE_COVERED_DEFAULT_NAME
            assert entry.asset_ref is None
            assert entry.armor is None
            assert entry.content_rating is None
            payload = entry.to_payload()
            assert design.name not in str(payload)
            assert design.asset_ref is None


def test_shared_registry_and_garment_bridge_do_not_duplicate_state():
    registry = EquipmentDesignRegistry(VERA_ARMOR_DESIGNS)
    assert set(registry.visible_to(CatalogAudience.PUBLIC).design_ids) == {
        design.design_id for design in VERA_ARMOR_DESIGNS
    }
    design = registry.get("vera_cqb_chest")
    garment = garment_from_wardrobe_design(design)
    assert garment.item_id == design.design_id
    assert garment.layer is design.layer
    assert garment.slots == design.slots
    assert garment.tail_clearance == design.tail_clearance

    starter = build_starter_wardrobe()
    blueprint = next(bp for bp in starter.blueprints if not bp.garment.private_only)
    adapted = wardrobe_design_from_garment(
        blueprint.garment, fit_anchors=blueprint.fit_anchors,
    )
    assert adapted.design_id == blueprint.garment.item_id
    assert adapted.layer is blueprint.garment.layer
    assert adapted.slots == blueprint.garment.slots
    assert adapted.coverage == blueprint.garment.coverage
    assert adapted.physical_protection is False
