"""AVATAR wardrobe design uniqueness and slot-matrix coverage."""
from dataclasses import replace

from sofia.avatar.wardrobe import LEAF_SLOTS, Layer
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_prebuild import DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID
from sofia.avatar.wardrobe_matrix import build_wardrobe_matrix


def test_starter_design_signatures_are_unique():
    pack = build_starter_wardrobe()
    signatures = [bp.design_signature for bp in pack.blueprints]

    assert len(signatures) == 154
    assert len(set(signatures)) == 154
    assert all(len(signature) == 64 for signature in signatures)
    assert all(bp.description.strip() for bp in pack.blueprints)


def test_design_signature_excludes_stable_item_id():
    pack = build_starter_wardrobe()
    original = pack.blueprints[0]
    renamed = replace(
        original,
        garment=replace(
            original.garment,
            item_id="proof.same-design-different-id",
        ),
        design=replace(
            original.design,
            item_id="proof.same-design-different-id",
        ),
    )

    assert renamed.design_signature == original.design_signature


def test_day_matrix_contains_every_leaf_slot_and_layer():
    pack = build_starter_wardrobe()
    plan = pack.preset(DAY_DEFAULT_OUTFIT_ID)
    matrix = build_wardrobe_matrix(pack, plan.item_ids)
    grid = matrix.as_dict()

    assert set(grid) == set(LEAF_SLOTS)
    expected_layers = {layer.name.lower() for layer in Layer}
    assert all(set(row) == expected_layers for row in grid.values())

    assert grid["torso"]["base"]["garment_id"] == "day.technical_top"
    assert grid["torso"]["outer"]["garment_id"] == "day.engineer_jacket"
    assert grid["left_foot"]["base"]["garment_id"] == "day.work_boots"
    assert grid["right_foot"]["base"]["garment_id"] == "day.work_boots"
    assert (
        grid["left_hand"]["accessory"]["garment_id"]
        == "day.fingerless_gloves"
    )
    assert (
        grid["right_hand"]["accessory"]["garment_id"]
        == "day.fingerless_gloves"
    )


def test_night_matrix_projects_running_short_visual_metadata():
    pack = build_starter_wardrobe()
    plan = pack.preset(NIGHT_LOUNGE_OUTFIT_ID)
    matrix = build_wardrobe_matrix(pack, plan.item_ids)
    grid = matrix.as_dict()

    pelvis = grid["pelvis"]["base"]
    left_thigh = grid["left_thigh"]["base"]
    tail = grid["tail"]["base"]

    assert pelvis["garment_id"] == "night.running_shorts"
    assert left_thigh["garment_id"] == "night.running_shorts"
    assert tail["garment_id"] == "night.running_shorts"
    assert pelvis["primary_hex"] == "#3A245C"
    assert pelvis["accent_hexes"] == ["#19D3C5"]
    assert "small circuit mark" in pelvis["description"].casefold()


def test_builtin_catalog_uses_native_leaf_slots():
    pack = build_starter_wardrobe()
    legacy_bilateral = {
        "legs", "feet", "hands", "ears", "shoulders", "upper_arms",
        "forearms", "wrists", "fingers", "thighs", "calves", "ankles",
    }

    for blueprint in pack.blueprints:
        assert not (legacy_bilateral & set(blueprint.garment.slots))
        assert not (legacy_bilateral & set(blueprint.garment.coverage))
