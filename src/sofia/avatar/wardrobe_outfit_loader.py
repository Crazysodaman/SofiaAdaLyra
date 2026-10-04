"""Validated saved-outfit JSON loading for Sofía's wardrobe."""
from __future__ import annotations

from importlib.resources import files
import json

from .wardrobe import Wardrobe, WardrobeError
from .wardrobe_planner import Activity, OutfitPlan, Season, Weather


def _enum_set(enum_type, values: object, label: str):
    if not isinstance(values, list) or not values:
        raise WardrobeError(f"outfit {label} must be a nonempty list")
    try:
        result = frozenset(enum_type(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise WardrobeError(f"invalid outfit {label}") from exc
    if len(result) != len(values):
        raise WardrobeError(f"duplicate outfit {label}")
    return result


def load_outfit_data_file(
    filename: str,
    wardrobe: Wardrobe,
) -> tuple[OutfitPlan, ...]:
    resource = files("sofia.avatar").joinpath("wardrobe_data", filename)
    try:
        raw = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WardrobeError(f"cannot load outfit data file: {filename}") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != "sofia.avatar.wardrobe.outfits.v1"
        or not isinstance(raw.get("outfits"), list)
    ):
        raise WardrobeError("unknown wardrobe outfit data schema")

    result: list[OutfitPlan] = []
    seen: set[str] = set()
    for row in raw["outfits"]:
        if not isinstance(row, dict):
            raise WardrobeError("outfit record must be an object")
        outfit_id = row.get("outfit_id")
        if not isinstance(outfit_id, str) or outfit_id in seen:
            raise WardrobeError("invalid or duplicate saved outfit ID")
        seen.add(outfit_id)
        item_ids = row.get("item_ids")
        if not isinstance(item_ids, list) or not item_ids or any(
            not isinstance(item, str) for item in item_ids
        ):
            raise WardrobeError("saved outfit requires garment IDs")

        weather_raw = row.get("weather", [])
        if not isinstance(weather_raw, list):
            raise WardrobeError("outfit weather must be a list")
        try:
            weather = frozenset(Weather(value) for value in weather_raw)
        except (TypeError, ValueError) as exc:
            raise WardrobeError("invalid outfit weather") from exc

        plan = OutfitPlan(
            outfit_id=outfit_id,
            item_ids=tuple(item_ids),
            activities=_enum_set(
                Activity, row.get("activities"), "activities"
            ),
            seasons=_enum_set(Season, row.get("seasons"), "seasons"),
            weather=weather,
            lounge=row.get("lounge", False),
            private_only=row.get("private_only", False),
            style_tags=tuple(row.get("style_tags", ())),
            display_name=row.get("display_name"),
            manual_only=row.get("manual_only", False),
        )
        selected = wardrobe.selection(plan.item_ids)
        if plan.private_only:
            if not selected.private_only:
                raise WardrobeError(
                    "private saved outfit must contain private-only garment"
                )
            if not plan.manual_only:
                raise WardrobeError(
                    "private saved outfits must be manual-only"
                )
        elif selected.private_only or not selected.covered_default:
            raise WardrobeError(
                "public saved outfit must remain covered and non-private"
            )
        result.append(plan)
    return tuple(result)
