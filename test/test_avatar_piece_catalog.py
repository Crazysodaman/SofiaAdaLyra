"""Structured wardrobe type vocabulary and starter-closet contracts."""
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_types import all_garment_types, garment_type


def test_creator_vocabulary_has_real_garment_types_not_style_permutations():
    ids = {item.type_id for item in all_garment_types()}
    assert {
        "t_shirt",
        "crop_top",
        "long_sleeve_tee",
        "hoodie",
        "running_shorts",
        "athletic_shorts",
        "denim_shorts",
        "cargo_shorts",
        "lounge_shorts",
        "utility_trousers",
        "jeans",
        "leggings",
        "dress",
        "engineer_jacket",
        "work_boots",
        "sneakers",
    } <= ids


def test_garment_types_own_slot_and_creator_capability_rules():
    tee = garment_type("t_shirt")
    shorts = garment_type("running_shorts")

    assert tee.supports_sleeve_length is True
    assert tee.supports_rise is False
    assert shorts.supports_rise is True
    assert shorts.supports_sleeve_length is False
    assert shorts.tail_clearance is True
    assert "torso" in tee.slots
    assert "pelvis" in shorts.slots


def test_owned_closet_includes_data_backed_underlayers():
    pack = build_starter_wardrobe()
    summary = pack.closet_summary()

    assert len(pack.blueprints) == 154
    assert len(pack.presets) == 24
    assert summary["starter_piece_count"] == 154
    assert summary["outfit_count"] == 24
    assert summary["all_designs_unique"] is True


def test_running_shorts_match_structured_creator_example():
    pack = build_starter_wardrobe()
    shorts = next(
        bp for bp in pack.blueprints
        if bp.garment.item_id == "night.running_shorts"
    )
    design = shorts.design

    assert design.garment_type == "running_shorts"
    assert design.fit == "fitted"
    assert design.rise == "mid"
    assert design.length == "short"
    assert design.material == "performance-knit"
    assert design.primary == "dark_violet"
    assert design.accent == "cyan"
    assert design.pattern == "none"
    assert design.graphic.enabled is True
    assert design.graphic.placement == "left_leg"
    assert design.graphic.design == "small_circuit_mark"
    assert design.features == ("drawstring", "side_slits", "tail_clearance")
    assert design.description.strip()
