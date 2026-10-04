"""Private-content balance for tops and bottoms."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating, ExposureZone


def _raw(name):
    resource = files("sofia.avatar").joinpath("wardrobe_data", name)
    return json.loads(resource.read_text(encoding="utf-8"))["garments"]


def test_tops_and_bottoms_each_keep_twenty_with_two_lewd_two_explicit():
    for filename in ("tops.json", "bottoms.json"):
        rows = _raw(filename)
        assert len(rows) == 20
        assert sum(row["content_rating"] == "lewd" for row in rows) == 2
        assert sum(row["content_rating"] == "explicit" for row in rows) == 2
        assert sum(row["content_rating"] == "standard" for row in rows) == 16
        assert all(
            row["private_only"]
            for row in rows
            if row["content_rating"] != "standard"
        )


def test_loaded_explicit_tops_and_bottoms_do_not_claim_exposed_coverage():
    catalog = build_starter_wardrobe()
    private = [
        bp for bp in catalog.blueprints
        if bp.content_rating is not ContentRating.STANDARD
    ]
    tops = [
        bp for bp in private
        if bp.garment.family.value == "top"
    ]
    bottoms = [
        bp for bp in private
        if bp.garment.family.value == "bottom"
    ]

    assert sum(bp.content_rating is ContentRating.LEWD for bp in tops) == 2
    assert sum(bp.content_rating is ContentRating.EXPLICIT for bp in tops) == 2
    assert sum(bp.content_rating is ContentRating.LEWD for bp in bottoms) == 2
    assert sum(bp.content_rating is ContentRating.EXPLICIT for bp in bottoms) == 2

    for bp in tops:
        if bp.content_rating is ContentRating.EXPLICIT:
            assert bp.exposure == (ExposureZone.NIPPLES,)
            assert "torso" not in bp.garment.coverage

    for bp in bottoms:
        if bp.content_rating is ContentRating.EXPLICIT:
            assert bp.exposure == (ExposureZone.GENITALS,)
            assert "pelvis" not in bp.garment.coverage
