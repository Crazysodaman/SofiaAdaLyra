"""Data-backed footwear inventory."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _rows():
    resource = files("sofia.avatar").joinpath("wardrobe_data", "footwear.json")
    raw = json.loads(resource.read_text(encoding="utf-8"))
    assert raw["schema"] == "sofia.avatar.wardrobe.garments.v1"
    return raw["garments"]


def test_footwear_file_has_twenty_distinct_owned_pieces():
    rows = _rows()
    assert len(rows) == 20
    assert len({row["item_id"] for row in rows}) == 20


def test_engineer_boots_are_now_data_backed_and_canonical():
    catalog = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in catalog.blueprints}
    boots = by_id["day.work_boots"]

    assert boots.provenance == "canonical_clothing_design"
    assert boots.design.garment_type == "work_boots"


def test_footwear_covers_weather_activity_lounge_and_formal_roles():
    rows = _rows()
    types = {row["garment_type"] for row in rows}
    profiles = {row["profile"] for row in rows}

    assert {"sneakers", "running_shoes", "high_top_sneakers",
            "ankle_boots", "combat_boots", "knee_boots", "rain_boots",
            "winter_boots", "hiking_boots", "slippers", "house_shoes",
            "sandals", "slides", "flats", "loafers", "heeled_boots",
            "dress_heels", "work_boots"} <= types
    assert {"work", "casual", "athletic", "wet_weather", "cold_weather",
            "outdoor", "lounge", "summer", "smart"} <= profiles
