"""Validated packaged wardrobe JSON loading; catalog supplies blueprint construction."""
from __future__ import annotations
from importlib.resources import files
import json
from pathlib import Path
from .wardrobe import WardrobeError
from .wardrobe_design import ComfortProfile, ContentRating, ContextProfile, EnvironmentProfile, ExposureZone, FabricWeight, GarmentDesign, GraphicDesign, HumidityProfile, MaterialProperties, MoistureProfile, MovementProfile, PrecipitationProfile, RatedContext, Suitability, SunlightProfile, TemperatureProfile, TraitLevel, WindProfile
from typing import Callable
from .wardrobe_prebuild import GarmentBlueprint

def _enum_from_json(enum_type, value, label: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise WardrobeError(f"invalid {label} in wardrobe JSON") from exc


def _rated_context_from_json(raw: object) -> RatedContext:
    if not isinstance(raw, dict):
        raise WardrobeError("rated context in wardrobe JSON must be an object")
    keys = ("excellent", "good", "acceptable", "poor", "unsuitable")
    values: dict[str, tuple[str, ...]] = {}
    for key in keys:
        entry = raw.get(key, [])
        if not isinstance(entry, list) or any(not isinstance(v, str) for v in entry):
            raise WardrobeError("rated context lists must contain strings")
        values[key] = tuple(entry)
    return RatedContext(**values)


def _profiles_from_json(raw: object) -> tuple[
    MaterialProperties,
    EnvironmentProfile,
    ContextProfile,
    ComfortProfile,
]:
    if not isinstance(raw, dict):
        raise WardrobeError("wardrobe profile must be an object")
    material = raw.get("material_properties")
    environment = raw.get("environment")
    context = raw.get("context")
    comfort = raw.get("comfort")
    if not all(isinstance(value, dict) for value in (
        material, environment, context, comfort
    )):
        raise WardrobeError("wardrobe profile is missing structured sections")

    temperature = environment.get("temperature", {})
    precipitation = environment.get("precipitation", {})
    moisture = environment.get("moisture", {})
    humidity = environment.get("humidity", {})
    wind = environment.get("wind", {})
    sunlight = environment.get("sunlight", {})
    if not all(isinstance(value, dict) for value in (
        temperature, precipitation, moisture, humidity, wind, sunlight
    )):
        raise WardrobeError("invalid environment profile section")

    movement = context.get("movement", {})
    if not isinstance(movement, dict):
        raise WardrobeError("invalid movement profile section")

    return (
        MaterialProperties(
            stretch=_enum_from_json(
                TraitLevel, material.get("stretch", "unspecified"),
                "material stretch",
            ),
            fabric_weight=_enum_from_json(
                FabricWeight, material.get("fabric_weight", "unspecified"),
                "fabric weight",
            ),
            texture=material.get("texture"),
            breathability=_enum_from_json(
                TraitLevel, material.get("breathability", "unspecified"),
                "breathability",
            ),
            insulation=_enum_from_json(
                TraitLevel, material.get("insulation", "unspecified"),
                "insulation",
            ),
        ),
        EnvironmentProfile(
            temperature=TemperatureProfile(
                minimum_c=temperature.get("minimum_c"),
                preferred_minimum_c=temperature.get("preferred_minimum_c"),
                preferred_maximum_c=temperature.get("preferred_maximum_c"),
                maximum_c=temperature.get("maximum_c"),
                thermal_weight=_enum_from_json(
                    FabricWeight,
                    temperature.get("thermal_weight", "unspecified"),
                    "thermal weight",
                ),
            ),
            precipitation=PrecipitationProfile(
                **{
                    key: _enum_from_json(
                        Suitability,
                        precipitation.get(key, "unspecified"),
                        f"precipitation {key}",
                    )
                    for key in (
                        "dry", "mist", "drizzle", "rain", "heavy_rain", "snow"
                    )
                }
            ),
            moisture=MoistureProfile(
                quick_dry=moisture.get("quick_dry"),
                water_resistance=_enum_from_json(
                    TraitLevel,
                    moisture.get("water_resistance", "unspecified"),
                    "water resistance",
                ),
                absorbency=_enum_from_json(
                    TraitLevel,
                    moisture.get("absorbency", "unspecified"),
                    "absorbency",
                ),
                wet_comfort=_enum_from_json(
                    Suitability,
                    moisture.get("wet_comfort", "unspecified"),
                    "wet comfort",
                ),
            ),
            humidity=HumidityProfile(
                low=_enum_from_json(
                    Suitability, humidity.get("low", "unspecified"),
                    "low humidity",
                ),
                moderate=_enum_from_json(
                    Suitability, humidity.get("moderate", "unspecified"),
                    "moderate humidity",
                ),
                high=_enum_from_json(
                    Suitability, humidity.get("high", "unspecified"),
                    "high humidity",
                ),
            ),
            wind=WindProfile(
                resistance=_enum_from_json(
                    TraitLevel, wind.get("resistance", "unspecified"),
                    "wind resistance",
                ),
                strong_wind=_enum_from_json(
                    Suitability, wind.get("strong_wind", "unspecified"),
                    "strong-wind suitability",
                ),
            ),
            sunlight=SunlightProfile(
                direct_sun=_enum_from_json(
                    Suitability, sunlight.get("direct_sun", "unspecified"),
                    "direct-sun suitability",
                ),
                uv_protection=_enum_from_json(
                    TraitLevel, sunlight.get("uv_protection", "unspecified"),
                    "UV protection",
                ),
            ),
            indoor=_enum_from_json(
                Suitability, environment.get("indoor", "unspecified"),
                "indoor suitability",
            ),
            outdoor=_enum_from_json(
                Suitability, environment.get("outdoor", "unspecified"),
                "outdoor suitability",
            ),
        ),
        ContextProfile(
            dayparts=_rated_context_from_json(context.get("dayparts", {})),
            seasons=_rated_context_from_json(context.get("seasons", {})),
            activities=_rated_context_from_json(context.get("activities", {})),
            settings=_rated_context_from_json(context.get("settings", {})),
            formality=_rated_context_from_json(context.get("formality", {})),
            emotion_styles=_rated_context_from_json(
                context.get("emotion_styles", {})
            ),
            movement=MovementProfile(
                mobility=_enum_from_json(
                    Suitability, movement.get("mobility", "unspecified"),
                    "movement mobility",
                ),
                seated_comfort=_enum_from_json(
                    Suitability,
                    movement.get("seated_comfort", "unspecified"),
                    "seated comfort",
                ),
                active_comfort=_enum_from_json(
                    Suitability,
                    movement.get("active_comfort", "unspecified"),
                    "active comfort",
                ),
            ),
        ),
        ComfortProfile(
            softness=_enum_from_json(
                TraitLevel, comfort.get("softness", "unspecified"),
                "comfort softness",
            ),
            flexibility=_enum_from_json(
                TraitLevel, comfort.get("flexibility", "unspecified"),
                "comfort flexibility",
            ),
            compression=_enum_from_json(
                TraitLevel, comfort.get("compression", "unspecified"),
                "comfort compression",
            ),
            heat_retention=_enum_from_json(
                TraitLevel, comfort.get("heat_retention", "unspecified"),
                "heat retention",
            ),
            ventilation=_enum_from_json(
                TraitLevel, comfort.get("ventilation", "unspecified"),
                "ventilation",
            ),
            skin_contact=_enum_from_json(
                Suitability, comfort.get("skin_contact", "unspecified"),
                "skin contact",
            ),
        ),
    )


def _load_wardrobe_data_file(
    filename: str | Path,
    blueprint_factory: Callable[..., GarmentBlueprint],
) -> tuple[GarmentBlueprint, ...]:
    resource = (
        filename
        if isinstance(filename, Path)
        else files("sofia.avatar").joinpath("wardrobe_data", filename)
    )
    try:
        raw = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WardrobeError(f"cannot load wardrobe data file: {filename}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != (
        "sofia.avatar.wardrobe.garments.v1"
    ):
        raise WardrobeError("unknown wardrobe garment data schema")
    profiles = raw.get("profiles")
    garments = raw.get("garments")
    if not isinstance(profiles, dict) or not isinstance(garments, list):
        raise WardrobeError("wardrobe data file requires profiles and garments")

    result: list[GarmentBlueprint] = []
    for row in garments:
        if not isinstance(row, dict):
            raise WardrobeError("wardrobe garment record must be an object")
        profile_id = row.get("profile")
        if not isinstance(profile_id, str) or profile_id not in profiles:
            raise WardrobeError("wardrobe garment references unknown profile")
        material_properties, environment, context, comfort = (
            _profiles_from_json(profiles[profile_id])
        )
        graphic_raw = row.get("graphic", {})
        if not isinstance(graphic_raw, dict):
            raise WardrobeError("garment graphic must be an object")
        canonical = row.get("canonical", False)
        if type(canonical) is not bool:
            raise WardrobeError("garment canonical flag must be boolean")
        provenance = row.get("provenance")
        if provenance is not None and not isinstance(provenance, str):
            raise WardrobeError("garment provenance must be string or null")

        design = GarmentDesign(
            item_id=row.get("item_id"),
            name=row.get("name"),
            garment_type=row.get("garment_type"),
            fit=row.get("fit"),
            rise=row.get("rise"),
            length=row.get("length"),
            sleeve_length=row.get("sleeve_length"),
            material=row.get("material"),
            primary=row.get("primary"),
            accent=row.get("accent"),
            pattern=row.get("pattern"),
            graphic=GraphicDesign(
                enabled=graphic_raw.get("enabled", False),
                placement=graphic_raw.get("placement"),
                design=graphic_raw.get("design"),
            ),
            features=tuple(row.get("features", ())),
            style_tags=tuple(row.get("style_tags", ())),
            private_only=row.get("private_only", False),
            content_rating=_enum_from_json(
                ContentRating,
                row.get("content_rating", "standard"),
                "content rating",
            ),
            exposure=tuple(
                _enum_from_json(ExposureZone, zone, "exposure zone")
                for zone in row.get("exposure", ())
            ),
            description=row.get("description"),
            material_properties=material_properties,
            environment=environment,
            context=context,
            comfort=comfort,
        )
        result.append(
            blueprint_factory(
                design,
                canonical=canonical,
                apply_starter_profiles=False,
                provenance=provenance,
            )
        )
    return tuple(result)
