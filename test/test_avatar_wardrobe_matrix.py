"""AVATAR wardrobe uniqueness, bikini catalog, and slot-matrix coverage."""
from dataclasses import replace

from sofia.avatar.wardrobe import LEAF_SLOTS, Layer
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_matrix import build_wardrobe_matrix


def test_full_wardrobe_counts_and_design_signatures_are_unique():
    pack = build_starter_wardrobe()
    summary = pack.closet_summary()

    assert len(pack.blueprints) == 978
    assert len(pack.presets) == 310
    assert summary["total_piece_count"] == 978
    assert summary["outfit_count"] == 310
    assert summary["bikini_outfit_count"] == 6
    assert summary["unique_design_signature_count"] == 978
    assert summary["duplicate_design_signature_count"] == 0
    assert summary["all_designs_unique"] is True
    assert all(blueprint.description.strip() for blueprint in pack.blueprints)


def test_design_signature_is_not_just_the_garment_id():
    pack = build_starter_wardrobe()
    original = pack.blueprints[0]
    renamed_id_only = replace(
        original,
        garment=replace(
            original.garment,
            item_id="proof.same-design-different-id",
        ),
    )

    assert renamed_id_only.design_signature == original.design_signature


def test_six_bikini_outfits_are_distinct_complete_two_piece_sets():
    pack = build_starter_wardrobe()
    bikinis = tuple(
        plan
        for plan in pack.presets
        if plan.outfit_id.startswith("swim.bikini.")
    )

    assert len(bikinis) == 6
    assert len({plan.display_name for plan in bikinis}) == 6
    assert all(len(plan.item_ids) == 2 for plan in bikinis)
    assert all(plan.manual_only for plan in bikinis)

    bikini_piece_ids = {
        item_id
        for plan in bikinis
        for item_id in plan.item_ids
    }
    assert len(bikini_piece_ids) == 12

    blueprints = {
        blueprint.garment.item_id: blueprint
        for blueprint in pack.blueprints
    }
    signatures = {
        blueprints[item_id].design_signature
        for item_id in bikini_piece_ids
    }
    descriptions = {
        blueprints[item_id].description
        for item_id in bikini_piece_ids
    }
    assert len(signatures) == 12
    assert len(descriptions) == 12

    for plan in bikinis:
        selection = pack.wardrobe.selection(plan.item_ids)
        assert selection.covered_default
        assert not selection.private_only


def test_slot_matrix_contains_every_slot_and_layer_plus_visual_metadata():
    pack = build_starter_wardrobe()
    plan = pack.preset("swim.bikini.04")
    matrix = build_wardrobe_matrix(pack, plan.item_ids)
    grid = matrix.as_dict()

    assert set(grid) == set(LEAF_SLOTS)
    expected_layers = {layer.name.lower() for layer in Layer}
    assert all(set(row) == expected_layers for row in grid.values())

    torso = grid["torso"]["base"]
    pelvis = grid["pelvis"]["base"]
    tail = grid["tail"]["base"]

    assert torso is not None
    assert pelvis is not None
    assert tail is not None
    assert torso["garment_id"] == "closet.swim.bikini.04.top"
    assert pelvis["garment_id"] == "closet.swim.bikini.04.bottom"
    assert tail["garment_id"] == "closet.swim.bikini.04.bottom"
    assert "one-shoulder" in torso["description"]
    assert "asymmetric-waist" in pelvis["description"]
    assert len(torso["design_signature"]) == 64
    assert len(pelvis["design_signature"]) == 64

    assert grid["head"]["base"] is None
    assert grid["torso"]["outer"] is None
    assert "feet" not in grid
    assert "hands" not in grid
    assert "ears" not in grid


def test_matrix_expands_broad_bilateral_slots_to_left_and_right_leaf_cells():
    pack = build_starter_wardrobe()
    plan = pack.preset("engineer.signature")
    matrix = build_wardrobe_matrix(pack, plan.item_ids)
    grid = matrix.as_dict()

    left_foot = grid["left_foot"]["base"]
    right_foot = grid["right_foot"]["base"]
    left_hand = grid["left_hand"]["base"]
    right_hand = grid["right_hand"]["base"]

    assert left_foot is not None
    assert right_foot is not None
    assert left_foot["garment_id"] == "engineer.boots"
    assert right_foot["garment_id"] == "engineer.boots"

    assert left_hand is not None
    assert right_hand is not None
    assert left_hand["garment_id"] == "engineer.gloves"
    assert right_hand["garment_id"] == "engineer.gloves"


def test_matrix_expands_ears_shoulders_and_leg_segments_without_broad_cells():
    pack = build_starter_wardrobe()
    plan = pack.preset("seasonal.winter.normal.01")
    matrix = build_wardrobe_matrix(pack, plan.item_ids)
    grid = matrix.as_dict()

    assert "shoulders" not in grid
    assert "upper_arms" not in grid
    assert "legs" not in grid
    assert "calves" not in grid
    assert "ankles" not in grid

    assert "left_shoulder" in grid
    assert "right_shoulder" in grid
    assert "left_upper_arm" in grid
    assert "right_upper_arm" in grid
    assert "left_leg" in grid
    assert "right_leg" in grid
    assert "left_calf" in grid
    assert "right_calf" in grid
    assert "left_ankle" in grid
    assert "right_ankle" in grid


def test_builtin_catalog_uses_native_leaf_slots_not_legacy_bilateral_shorthand():
    pack = build_starter_wardrobe()
    legacy_bilateral = {
        "legs", "feet", "hands", "ears", "shoulders", "upper_arms",
        "forearms", "wrists", "fingers", "thighs", "calves", "ankles",
    }

    for blueprint in pack.blueprints:
        assert not (legacy_bilateral & set(blueprint.garment.slots))
        assert not (legacy_bilateral & set(blueprint.garment.coverage))
