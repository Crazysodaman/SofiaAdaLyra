"""Packaged JSON wardrobe inventory is authoritative for underlayers."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating, ExposureZone


def _raw(filename):
    resource = files("sofia.avatar").joinpath("wardrobe_data", filename)
    return json.loads(resource.read_text(encoding="utf-8"))


def test_upper_and_lower_underlayer_files_each_define_24_owned_pieces():
    upper = _raw("underlayers_upper.json")
    lower = _raw("underlayers_lower.json")

    assert upper["schema"] == "sofia.avatar.wardrobe.garments.v1"
    assert lower["schema"] == "sofia.avatar.wardrobe.garments.v1"
    assert len(upper["garments"]) == 24
    assert len(lower["garments"]) == 24

    catalog = build_starter_wardrobe()
    owned = {bp.garment.item_id for bp in catalog.blueprints}
    assert {row["item_id"] for row in upper["garments"]} <= owned
    assert {row["item_id"] for row in lower["garments"]} <= owned


def test_private_content_counts_and_exposure_are_explicit_in_json():
    upper = _raw("underlayers_upper.json")["garments"]
    lower = _raw("underlayers_lower.json")["garments"]

    assert sum(row["content_rating"] == "lewd" for row in upper) == 2
    assert sum(row["content_rating"] == "explicit" for row in upper) == 2
    assert sum(row["content_rating"] == "lewd" for row in lower) == 2
    assert sum(row["content_rating"] == "explicit" for row in lower) == 2

    assert all(
        row["private_only"]
        for row in upper + lower
        if row["content_rating"] != "standard"
    )
    assert all(
        row["exposure"] == ["nipples"]
        for row in upper
        if row["content_rating"] == "explicit"
    )
    assert all(
        row["exposure"] == ["genitals"]
        for row in lower
        if row["content_rating"] == "explicit"
    )


def test_loaded_explicit_pieces_are_private_and_do_not_claim_default_coverage():
    catalog = build_starter_wardrobe()
    explicit = [
        bp for bp in catalog.blueprints
        if bp.content_rating is ContentRating.EXPLICIT
        and bp.garment.item_id.startswith(("under.upper.", "under.lower."))
    ]

    assert len(explicit) == 4
    assert all(bp.private_only for bp in explicit)
    assert all(bp.garment.coverage == () for bp in explicit)

    upper = [
        bp for bp in explicit
        if bp.exposure == (ExposureZone.NIPPLES,)
    ]
    lower = [
        bp for bp in explicit
        if bp.exposure == (ExposureZone.GENITALS,)
    ]
    assert len(upper) == 2
    assert len(lower) == 2


def test_canonical_default_underlayers_now_come_from_json():
    catalog = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in catalog.blueprints}

    assert by_id["base.bralette"].provenance == "canonical_clothing_design"
    assert by_id["base.briefs"].provenance == "canonical_clothing_design"
    assert by_id["base.bralette"].content_rating is ContentRating.STANDARD
    assert by_id["base.briefs"].content_rating is ContentRating.STANDARD


def test_manifest_exposes_rating_and_exposure_metadata():
    manifest = build_starter_wardrobe().manifest()
    rows = {row["item_id"]: row for row in manifest["garments"]}

    explicit_upper = rows["under.upper.open_cup_bralette"]
    explicit_lower = rows["under.lower.open_crotch_briefs"]

    assert explicit_upper["private_only"] is True
    assert explicit_upper["content_rating"] == "explicit"
    assert explicit_upper["exposure"] == ["nipples"]
    assert explicit_upper["coverage"] == []

    assert explicit_lower["private_only"] is True
    assert explicit_lower["content_rating"] == "explicit"
    assert explicit_lower["exposure"] == ["genitals"]
    assert explicit_lower["coverage"] == []
