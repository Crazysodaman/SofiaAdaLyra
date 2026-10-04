"""Data-backed owned bottoms inventory."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _raw():
    resource = files("sofia.avatar").joinpath("wardrobe_data", "bottoms.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def test_bottoms_json_defines_20_distinct_owned_bottoms():
    raw = _raw()
    assert raw["schema"] == "sofia.avatar.wardrobe.garments.v1"
    assert raw["category"] == "bottoms"
    assert len(raw["garments"]) == 20
    assert len({row["item_id"] for row in raw["garments"]}) == 20


def test_existing_day_and_night_bottoms_are_now_data_backed():
    raw = _raw()
    ids = {row["item_id"] for row in raw["garments"]}
    assert "day.utility_trousers" in ids
    assert "night.running_shorts" in ids

    catalog = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in catalog.blueprints}
    assert by_id["day.utility_trousers"].provenance == "canonical_clothing_design"
    assert by_id["night.running_shorts"].design.garment_type == "running_shorts"


def test_bottoms_cover_short_trouser_legging_denim_and_skirt_roles():
    raw = _raw()
    types = {row["garment_type"] for row in raw["garments"]}
    profiles = {row["profile"] for row in raw["garments"]}

    assert {"running_shorts", "athletic_shorts", "denim_shorts",
            "cargo_shorts", "lounge_shorts", "bike_shorts",
            "utility_trousers", "jeans", "leggings", "skirt"} <= types
    assert {"technical", "lounge", "hot_weather", "athletic",
            "denim", "casual", "smart"} <= profiles


def test_all_bottoms_keep_tail_clearance():
    raw = _raw()
    assert all("tail_clearance" in row["features"] for row in raw["garments"])
