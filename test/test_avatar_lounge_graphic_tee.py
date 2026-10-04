"""Graphics are ordinary garment design data, not special-case pieces."""
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _piece(item_id):
    pack = build_starter_wardrobe()
    return next(bp for bp in pack.blueprints if bp.garment.item_id == item_id)


def test_night_lounge_tee_has_first_class_graphic_metadata():
    tee = _piece("night.lounge_tee").design

    assert tee.garment_type == "t_shirt"
    assert tee.sleeve_length == "short"
    assert tee.graphic.enabled is True
    assert tee.graphic.placement == "back_center"
    assert tee.graphic.design == "violet_cyan_circuit_fox"
    assert "graphic" in tee.style_tags


def test_running_short_graphic_is_not_a_separate_garment_type():
    shorts = _piece("night.running_shorts").design

    assert shorts.garment_type == "running_shorts"
    assert shorts.graphic.enabled is True
    assert shorts.graphic.placement == "left_leg"
    assert shorts.graphic.design == "small_circuit_mark"


def test_manifest_exposes_generic_graphic_shape_for_creator():
    garments = {
        row["item_id"]: row
        for row in build_starter_wardrobe().manifest()["garments"]
    }
    graphic = garments["night.running_shorts"]["graphic"]

    assert graphic == {
        "enabled": True,
        "placement": "left_leg",
        "design": "small_circuit_mark",
    }
