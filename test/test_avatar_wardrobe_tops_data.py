"""Data-backed owned tops inventory."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _raw():
    resource = files("sofia.avatar").joinpath("wardrobe_data", "tops.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def test_tops_json_defines_20_distinct_owned_tops():
    raw = _raw()
    assert raw["schema"] == "sofia.avatar.wardrobe.garments.v1"
    assert raw["category"] == "tops"
    assert len(raw["garments"]) == 20
    assert len({row["item_id"] for row in raw["garments"]}) == 20


def test_existing_day_and_night_tops_are_now_data_backed():
    raw = _raw()
    ids = {row["item_id"] for row in raw["garments"]}
    assert "day.technical_top" in ids
    assert "night.lounge_tee" in ids

    catalog = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in catalog.blueprints}
    assert by_id["day.technical_top"].provenance == "canonical_clothing_design"
    assert by_id["night.lounge_tee"].design.garment_type == "t_shirt"


def test_tops_cover_multiple_styles_and_environment_roles():
    raw = _raw()
    profiles = {row["profile"] for row in raw["garments"]}
    types = {row["garment_type"] for row in raw["garments"]}

    assert {"technical", "casual", "lounge", "hot_weather", "athletic",
            "cool_weather", "cold_weather", "smart"} <= profiles
    assert {"t_shirt", "crop_top", "tank_top", "long_sleeve_tee",
            "button_up", "hoodie", "sweater"} <= types
