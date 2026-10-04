"""Data-backed outerwear inventory."""
from importlib.resources import files
import json

from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _rows():
    resource = files("sofia.avatar").joinpath("wardrobe_data", "outerwear.json")
    raw = json.loads(resource.read_text(encoding="utf-8"))
    assert raw["schema"] == "sofia.avatar.wardrobe.garments.v1"
    return raw["garments"]


def test_outerwear_file_has_twenty_distinct_owned_pieces():
    rows = _rows()
    assert len(rows) == 20
    assert len({row["item_id"] for row in rows}) == 20


def test_engineer_jacket_is_now_data_backed_and_canonical():
    catalog = build_starter_wardrobe()
    by_id = {bp.garment.item_id: bp for bp in catalog.blueprints}
    jacket = by_id["day.engineer_jacket"]

    assert jacket.provenance == "canonical_clothing_design"
    assert jacket.design.garment_type == "engineer_jacket"


def test_outerwear_covers_weather_work_casual_lounge_and_formal_roles():
    rows = _rows()
    types = {row["garment_type"] for row in rows}
    profiles = {row["profile"] for row in rows}

    assert {"engineer_jacket", "bomber_jacket", "windbreaker",
            "rain_jacket", "cropped_jacket", "denim_jacket",
            "leather_jacket", "fleece_jacket", "cardigan",
            "utility_vest", "puffer_vest", "parka", "trench_coat",
            "long_coat", "coat", "cape"} <= types
    assert {"technical", "casual", "wind", "rain", "cool_weather",
            "cold_weather", "smart", "lounge"} <= profiles
