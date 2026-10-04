"""Data-backed dresses and other one-piece garments."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating, ExposureZone


DRESS_TYPES = {"dress", "open_bust_dress", "open_crotch_dress"}


def _rows():
    resource = files("sofia.avatar").joinpath(
        "wardrobe_data", "one_pieces.json"
    )
    raw = json.loads(resource.read_text(encoding="utf-8"))
    assert raw["schema"] == "sofia.avatar.wardrobe.garments.v1"
    return raw["garments"]


def test_one_piece_file_has_ten_dresses_and_ten_other_one_pieces():
    rows = _rows()
    dresses = [row for row in rows if row["garment_type"] in DRESS_TYPES]
    others = [row for row in rows if row["garment_type"] not in DRESS_TYPES]

    assert len(rows) == 20
    assert len(dresses) == 10
    assert len(others) == 10
    assert len({row["item_id"] for row in rows}) == 20


def test_each_half_has_two_lewd_and_two_explicit_private_pieces():
    rows = _rows()
    groups = (
        [row for row in rows if row["garment_type"] in DRESS_TYPES],
        [row for row in rows if row["garment_type"] not in DRESS_TYPES],
    )

    for group in groups:
        assert sum(row["content_rating"] == "standard" for row in group) == 6
        assert sum(row["content_rating"] == "lewd" for row in group) == 2
        assert sum(row["content_rating"] == "explicit" for row in group) == 2
        assert all(
            row["private_only"]
            for row in group
            if row["content_rating"] != "standard"
        )


def test_loaded_explicit_one_pieces_do_not_claim_exposed_regions():
    catalog = build_starter_wardrobe()
    explicit = [
        bp for bp in catalog.blueprints
        if bp.content_rating is ContentRating.EXPLICIT
        and bp.garment.family.value == "one_piece"
    ]

    assert len(explicit) == 4
    nipple = [
        bp for bp in explicit
        if bp.exposure == (ExposureZone.NIPPLES,)
    ]
    genital = [
        bp for bp in explicit
        if bp.exposure == (ExposureZone.GENITALS,)
    ]
    assert len(nipple) == 2
    assert len(genital) == 2
    assert all("torso" not in bp.garment.coverage for bp in nipple)
    assert all("pelvis" not in bp.garment.coverage for bp in genital)


def test_one_piece_inventory_covers_multiple_construction_types():
    types = {row["garment_type"] for row in _rows()}
    assert {"dress", "jumpsuit", "romper", "bodysuit", "overalls",
            "unitard", "open_bust_dress", "open_crotch_dress",
            "open_bust_one_piece", "open_crotch_one_piece"} <= types
