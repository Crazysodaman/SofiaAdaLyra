"""Approved saved outfits and rope harness underlayer contracts."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe import Layer
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating, ExposureZone
from sofia.avatar.wardrobe_types import GarmentFamily, garment_type


def test_outfits_json_contains_twenty_public_and_three_private_presets():
    resource = files("sofia.avatar").joinpath("wardrobe_data", "outfits.json")
    raw = json.loads(resource.read_text(encoding="utf-8"))
    rows = raw["outfits"]

    assert raw["schema"] == "sofia.avatar.wardrobe.outfits.v1"
    assert len(rows) == 23
    assert sum(row["private_only"] for row in rows) == 3
    assert all(
        row["manual_only"]
        for row in rows
        if row["private_only"]
    )


def test_every_approved_outfit_has_underlayers():
    pack = build_starter_wardrobe()
    for plan in pack.presets:
        if plan.outfit_id == "fallback.covered":
            continue
        ids = set(plan.item_ids)
        if plan.outfit_id == "private.rope_harness":
            assert ids == {"under.private.rope_full_harness"}
            continue
        assert any(
            item == "base.bralette" or item.startswith("under.upper.")
            for item in ids
        )
        assert any(
            item == "base.briefs" or item.startswith("under.lower.")
            for item in ids
        )


def test_rope_harnesses_are_underwear_layer_private_and_exposure_aware():
    pack = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in pack.blueprints}
    breast = by_id["under.private.rope_breast_harness"]
    hip = by_id["under.private.rope_hip_harness"]
    full = by_id["under.private.rope_full_harness"]

    for blueprint in (breast, hip, full):
        definition = garment_type(blueprint.design.garment_type)
        assert definition.family is GarmentFamily.UNDERWEAR
        assert definition.layer is Layer.UNDERWEAR
        assert blueprint.private_only is True
        assert blueprint.content_rating is ContentRating.EXPLICIT
        assert blueprint.garment.coverage == ()

    assert breast.exposure == (ExposureZone.NIPPLES,)
    assert hip.exposure == (ExposureZone.GENITALS,)
    assert full.exposure == (
        ExposureZone.NIPPLES,
        ExposureZone.GENITALS,
    )


def test_private_rope_harness_outfit_uses_full_harness_as_underlayer():
    pack = build_starter_wardrobe()
    plan = pack.preset("private.rope_harness")
    selection = pack.wardrobe.selection(plan.item_ids)

    assert plan.item_ids == ("under.private.rope_full_harness",)
    assert plan.private_only is True
    assert plan.manual_only is True
    assert selection.private_only is True
    assert selection.covered_default is False
