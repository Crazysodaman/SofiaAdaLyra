"""Source-level acceptance tests for AR-01..AR-08 modular armor dependencies.

These tests validate metadata-only equip rules.  A positive decision does not
claim a rendered mesh, installed asset, physical protection or a canonical body
change.
"""
from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from sofia.modules.avatar.armor_catalog import (
    EQUIPMENT_TYPES,
    equipment_type,
    equipment_type_for_class,
)
from sofia.modules.avatar.fit import (
    WearerFitStatus,
    WearerProfile,
    evaluate_wearer_fit,
)
from sofia.modules.avatar.wardrobe_equipment import (
    ARMOR_CLASSES,
    VERA_ARMOR_BY_DESIGN_ID,
    VERA_ARMOR_DESIGNS,
    ArmorDecisionStatus,
    ArmorFamily,
    ArmorSeries,
    EquippedItem,
    EquipmentError,
    GarmentClass,
    atomic_disassembly_plan,
    dependent_armor_items,
    validate_armor_equip,
    validate_armor_unequip,
    vera_armor_configuration,
)
from sofia.modules.avatar.wardrobe_equipment_catalog import (
    EquipmentDesignRegistry,
    equipped_item_from_design_id,
)

HUMAN = "human"


def _design(design_id: str):
    return VERA_ARMOR_BY_DESIGN_ID[design_id]


def _item(design, counter: int, *, asset_verified: bool = True) -> EquippedItem:
    return EquippedItem.from_design(
        UUID(int=counter), design, asset_verified=asset_verified,
    )


def _equip_configuration(configuration_id: str):
    """Equip one approved Vera kit in its reviewed order."""
    config = vera_armor_configuration(configuration_id)
    equipped: list[EquippedItem] = []
    by_design_id: dict[str, EquippedItem] = {}
    for index, design_id in enumerate(config.equip_order(), start=1):
        candidate = _item(_design(design_id), index)
        decision = validate_armor_equip(
            equipped, candidate, body_profile=HUMAN, require_fit=True,
        )
        assert decision.allowed, decision.reason
        equipped.append(candidate)
        by_design_id[design_id] = candidate
    return config, tuple(equipped), by_design_id


def test_equipment_type_catalog_covers_every_armor_class_without_changing_clothing():
    assert {item.garment_class for item in EQUIPMENT_TYPES} == set(ARMOR_CLASSES)
    assert len(EQUIPMENT_TYPES) == len(ARMOR_CLASSES)
    assert equipment_type("armor_chest").garment_class is GarmentClass.ARMOR_CHEST
    assert (
        equipment_type_for_class(GarmentClass.ARMOR_GAUNTLET_LEFT).type_id
        == "armor_gauntlet_left"
    )
    assert equipment_type("armor_gauntlet_right").slots == (
        "right_hand", "right_fingers", "right_wrist",
    )

    from sofia.modules.avatar.wardrobe_types import garment_type

    assert garment_type("t_shirt").slots  # ordinary vocabulary still resolves


def test_ar01_armor_plate_without_undersuit_is_denied_and_state_is_unchanged():
    equipped: tuple[EquippedItem, ...] = ()
    candidate = _item(_design("vera_cqb_chest"), 1)
    decision = validate_armor_equip(
        equipped, candidate, body_profile=HUMAN, require_fit=True,
    )
    assert decision.status is ArmorDecisionStatus.DENIED
    assert "undersuit" in decision.reason
    assert equipped == ()
    assert decision.physical_protection is False


def test_ar02_wrong_undersuit_family_or_interface_is_denied_with_reason():
    undersuit = _item(_design("vera_undersuit_mark_iv"), 1)
    base = _item(_design("vera_base_mark_iv"), 2)
    equipped = (undersuit, base)

    wrong_interface = replace(
        _design("vera_mark_iv_chest"),
        design_id="test.wrong.interface.chest",
        armor=replace(
            _design("vera_mark_iv_chest").armor,
            undersuit_interface="aegis.armor.undersuit.mark_iv.v2",
        ),
    )
    interface_decision = validate_armor_equip(
        equipped,
        _item(wrong_interface, 3),
        body_profile=HUMAN,
        require_fit=True,
    )
    assert interface_decision.status is ArmorDecisionStatus.DENIED
    assert "undersuit" in interface_decision.reason
    assert "interface" in interface_decision.reason

    wrong_family = replace(
        _design("vera_odst_chest"),
        design_id="test.wrong.family.chest",
    )
    family_decision = validate_armor_equip(
        equipped,
        _item(wrong_family, 4),
        body_profile=HUMAN,
        require_fit=True,
    )
    assert family_decision.status is ArmorDecisionStatus.DENIED
    assert "undersuit" in family_decision.reason


def test_ar03_cqb_undersuit_base_and_parts_form_the_approved_metadata_loadout():
    config, equipped, by_design_id = _equip_configuration("cqb")
    assert config.family is ArmorFamily.MARK_IV
    assert config.series is ArmorSeries.MARK_IV_CQB
    assert config.primary_color == "#626262"
    assert config.visor_color == "#D4AF37"
    assert set(by_design_id) == set(config.equip_order())

    for design_id in config.equip_order():
        design = _design(design_id)
        verified = replace(design, asset_ref=f"test.asset.{design_id}")
        wearer = WearerProfile(
            body_profile=HUMAN,
            measurements={"height_inches": 70.0},
            anchors=verified.fit_anchors,
            rig_id="human.rig.v1",
        )
        result = evaluate_wearer_fit(
            verified,
            wearer,
            evidence_ref=f"test.fit.{design_id}",
            asset_verified=True,
        )
        assert result.status is WearerFitStatus.FITTED, result.reason
        assert result.mutates_canonical_body is False


def test_ar04_odst_hybrid_uses_mark_v_base_and_keeps_visor_color_unresolved():
    config, equipped, by_design_id = _equip_configuration("odst")
    assert config.family is ArmorFamily.MARK_V
    assert config.series is ArmorSeries.MARK_V
    assert config.primary_color == "#626262"
    assert config.visor_color is None
    assert "visor" in config.unresolved_color_channels

    helmet = _design("vera_odst_helmet")
    visor = _design("vera_odst_visor")
    shoulders = (
        _design("vera_odst_shoulder_left"),
        _design("vera_odst_shoulder_right"),
    )
    chest = _design("vera_odst_chest")
    assert helmet.armor is not None and helmet.armor.family is ArmorFamily.MARK_V
    assert visor.armor is not None and visor.armor.visor_color is None
    assert "visor" in visor.armor.unresolved_color_channels
    assert all(item.armor is not None for item in shoulders)
    assert chest.armor is not None and chest.armor.family is ArmorFamily.MARK_V
    assert {
        "vera_odst_helmet", "vera_odst_shoulder_left",
        "vera_odst_shoulder_right", "vera_odst_chest",
    } <= set(by_design_id)
    assert helmet.physical_protection is False


def test_ar05_mark_iv_part_on_mark_v_loadout_is_denied_without_normalization():
    equipped = (
        _item(_design("vera_undersuit_mark_v"), 1),
        _item(_design("vera_base_mark_v"), 2),
    )
    candidate = _item(_design("vera_mark_iv_chest"), 3)
    decision = validate_armor_equip(
        equipped, candidate, body_profile=HUMAN, require_fit=True,
    )
    assert decision.status is ArmorDecisionStatus.DENIED
    assert "undersuit" in decision.reason
    assert candidate.armor is not None
    assert candidate.armor.family is ArmorFamily.MARK_IV
    assert candidate.armor.base_series is ArmorSeries.MARK_IV
    assert len(equipped) == 2


def test_ar06_removing_supporting_armor_requires_atomic_disassembly():
    config, equipped, by_design_id = _equip_configuration("cqb")
    undersuit = by_design_id[config.undersuit_design_id]
    base = by_design_id[config.base_design_id]

    undersuit_decision = validate_armor_unequip(
        equipped, undersuit.item_instance_id,
    )
    assert undersuit_decision.status is ArmorDecisionStatus.ATOMIC_DISASSEMBLY_REQUIRED
    assert base.item_instance_id in undersuit_decision.dependent_item_ids
    undersuit_plan = atomic_disassembly_plan(
        equipped, undersuit.item_instance_id,
    )
    assert undersuit_plan[-1] == undersuit.item_instance_id
    assert set(undersuit_plan[:-1]) == set(undersuit_decision.dependent_item_ids)

    base_decision = validate_armor_unequip(equipped, base.item_instance_id)
    assert base_decision.status is ArmorDecisionStatus.ATOMIC_DISASSEMBLY_REQUIRED
    assert base_decision.dependent_item_ids
    base_plan = atomic_disassembly_plan(equipped, base.item_instance_id)
    assert base_plan[-1] == base.item_instance_id
    assert set(base_plan[:-1]) == set(base_decision.dependent_item_ids)

    chest = by_design_id["vera_cqb_chest"]
    part_decision = validate_armor_unequip(equipped, chest.item_instance_id)
    assert part_decision.status is ArmorDecisionStatus.ALLOWED
    assert dependent_armor_items(equipped, chest.item_instance_id) == ()


def test_ar07_sofia_anatomy_without_reviewed_clearance_is_unsupported():
    helmet = replace(
        _design("vera_cqb_helmet"),
        design_id="test.rigid.helmet",
        ear_clearance=False,
    )
    back = replace(
        _design("vera_cqb_back"),
        design_id="test.rigid.back",
        tail_clearance=False,
    )
    equipped = (
        _item(_design("vera_undersuit_mark_iv"), 1),
        _item(_design("vera_base_mark_iv_cqb"), 2),
    )

    helmet_decision = validate_armor_equip(
        equipped,
        _item(helmet, 3),
        body_profile=HUMAN,
        body_has_ears=True,
    )
    assert helmet_decision.status is ArmorDecisionStatus.DENIED
    assert "ear clearance" in helmet_decision.reason

    back_decision = validate_armor_equip(
        equipped,
        _item(back, 4),
        body_profile=HUMAN,
        body_has_tail=True,
    )
    assert back_decision.status is ArmorDecisionStatus.DENIED
    assert "tail clearance" in back_decision.reason

    ear_wearer = WearerProfile(
        body_profile=HUMAN,
        measurements={"height_inches": 70.0},
        anchors=helmet.fit_anchors,
        rig_id="sofia.rig.v1",
        has_ears=True,
    )
    fit = evaluate_wearer_fit(helmet, ear_wearer)
    assert fit.status is WearerFitStatus.UNSUPPORTED
    assert "ear clearance" in fit.reason
    assert fit.mutates_canonical_body is False

    tail_wearer = WearerProfile(
        body_profile=HUMAN,
        measurements={"height_inches": 70.0},
        anchors=back.fit_anchors,
        rig_id="sofia.rig.v1",
        has_tail=True,
    )
    tail_fit = evaluate_wearer_fit(back, tail_wearer)
    assert tail_fit.status is WearerFitStatus.UNSUPPORTED
    assert "tail clearance" in tail_fit.reason


def test_ar08_partial_left_right_plates_require_the_full_chain():
    base_loadout = (
        _item(_design("vera_undersuit_mark_iv"), 1),
        _item(_design("vera_base_mark_iv_cqb"), 2),
    )
    left = _item(_design("vera_cqb_shoulder_left"), 3)
    right = _item(_design("vera_cqb_shoulder_right"), 4)

    assert validate_armor_equip(
        base_loadout, left, body_profile=HUMAN, require_fit=True,
    ).allowed
    assert validate_armor_equip(
        base_loadout, right, body_profile=HUMAN, require_fit=True,
    ).allowed
    both = (*base_loadout, left, right)
    assert validate_armor_equip(
        both,
        _item(_design("vera_cqb_chest"), 5),
        body_profile=HUMAN,
        require_fit=True,
    ).allowed

    without_base = (_item(_design("vera_undersuit_mark_iv"), 6),)
    assert not validate_armor_equip(
        without_base, left, body_profile=HUMAN, require_fit=True,
    ).allowed

    gauntlet_type = equipment_type("armor_gauntlet_left")
    left_shoulder = _design("vera_cqb_shoulder_left")
    assert left_shoulder.armor is not None
    gauntlet = replace(
        left_shoulder,
        design_id="test.gauntlet.left",
        name="Test left gauntlet",
        garment_class=GarmentClass.ARMOR_GAUNTLET_LEFT,
        garment_type="armor_gauntlet_left",
        slots=gauntlet_type.slots,
        coverage=gauntlet_type.coverage,
        fit_anchors=gauntlet_type.fit_anchors,
        armor=replace(
            left_shoulder.armor,
            mount_id="mark_iv_cqb.forearm.left",
            socket="mark_iv_cqb.gauntlet.left",
        ),
    )
    gauntlet_decision = validate_armor_equip(
        base_loadout,
        _item(gauntlet, 7),
        body_profile=HUMAN,
        require_fit=True,
    )
    assert gauntlet_decision.allowed, gauntlet_decision.reason


def test_registry_projection_preserves_injected_design_version():
    registry = EquipmentDesignRegistry(VERA_ARMOR_DESIGNS)
    projected = equipped_item_from_design_id(
        UUID(int=401),
        "vera_cqb_chest",
        registry,
        design_version=1,
    )
    assert projected.garment_class is GarmentClass.ARMOR_CHEST
    assert projected.design_id == "vera_cqb_chest"
    with pytest.raises(EquipmentError):
        equipped_item_from_design_id(
            UUID(int=402),
            "vera_cqb_chest",
            registry,
            design_version=99,
        )
