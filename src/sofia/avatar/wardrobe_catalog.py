"""Small reviewed starter wardrobe built from structured garment designs.

The type vocabulary lives in wardrobe_types.py; validated JSON loading lives
in wardrobe_loader.py and prebuild contracts in wardrobe_prebuild.py. This catalog contains only
pieces Sofía currently owns as design metadata. No blueprint claims a mesh,
texture, renderer asset, or proof that an item is visibly worn.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .wardrobe_prebuild import (DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID,
    FALLBACK_OUTFIT_ID, GarmentBlueprint, WardrobePrebuild, StyleInput, RequestStatus)
from .wardrobe_loader import _load_wardrobe_data_file
from .wardrobe import Garment, Wardrobe
from .wardrobe_generated_store import generated_wardrobe_path
from .wardrobe_design import ComfortProfile, ContextProfile, EnvironmentProfile, FabricWeight, GarmentDesign, GraphicDesign, HumidityProfile, MaterialProperties, MoistureProfile, MovementProfile, PrecipitationProfile, RatedContext, Suitability, SunlightProfile, TemperatureProfile, TraitLevel, WindProfile, validate_design
from .wardrobe_planner import Activity, OutfitPlan, Season


ALL_SEASONS = frozenset(Season)


def _load_underlayer_blueprints() -> tuple[GarmentBlueprint, ...]:
    return (
        *_load_wardrobe_data_file("underlayers_upper.json", _blueprint),
        *_load_wardrobe_data_file("underlayers_lower.json", _blueprint),
    )


def _starter_profiles(
    item_id: str,
) -> tuple[
    MaterialProperties,
    EnvironmentProfile,
    ContextProfile,
    ComfortProfile,
]:
    """Return reviewed creator/environment metadata for one starter garment."""

    generic_context = ContextProfile(
        dayparts=RatedContext(
            good=("morning", "afternoon", "evening", "night", "late_night"),
        ),
        seasons=RatedContext(
            good=("spring", "summer", "autumn", "winter"),
        ),
        activities=RatedContext(
            good=("conversation", "relaxing"),
            acceptable=("engineering", "lab", "sleep", "formal"),
        ),
        settings=RatedContext(
            good=("home", "private", "casual_public"),
            acceptable=("workshop", "lab", "office", "outdoor"),
        ),
        formality=RatedContext(
            good=("lounge", "casual"),
            acceptable=("work", "smart_casual"),
            poor=("formal",),
        ),
        movement=MovementProfile(
            mobility=Suitability.GOOD,
            seated_comfort=Suitability.GOOD,
            active_comfort=Suitability.GOOD,
        ),
    )
    generic_environment = EnvironmentProfile(
        temperature=TemperatureProfile(
            5.0, 15.0, 28.0, 38.0, FabricWeight.LIGHT
        ),
        precipitation=PrecipitationProfile(
            dry=Suitability.EXCELLENT,
            mist=Suitability.GOOD,
            drizzle=Suitability.ACCEPTABLE,
            rain=Suitability.POOR,
            heavy_rain=Suitability.UNSUITABLE,
            snow=Suitability.POOR,
        ),
        moisture=MoistureProfile(
            quick_dry=True,
            water_resistance=TraitLevel.LOW,
            absorbency=TraitLevel.LOW,
            wet_comfort=Suitability.ACCEPTABLE,
        ),
        humidity=HumidityProfile(
            low=Suitability.GOOD,
            moderate=Suitability.EXCELLENT,
            high=Suitability.GOOD,
        ),
        wind=WindProfile(
            resistance=TraitLevel.LOW,
            strong_wind=Suitability.POOR,
        ),
        sunlight=SunlightProfile(
            direct_sun=Suitability.GOOD,
            uv_protection=TraitLevel.LOW,
        ),
        indoor=Suitability.EXCELLENT,
        outdoor=Suitability.GOOD,
    )
    generic_material = MaterialProperties(
        stretch=TraitLevel.MODERATE,
        fabric_weight=FabricWeight.LIGHT,
        texture="smooth",
        breathability=TraitLevel.HIGH,
        insulation=TraitLevel.LOW,
    )
    generic_comfort = ComfortProfile(
        softness=TraitLevel.HIGH,
        flexibility=TraitLevel.HIGH,
        compression=TraitLevel.LOW,
        heat_retention=TraitLevel.LOW,
        ventilation=TraitLevel.HIGH,
        skin_contact=Suitability.EXCELLENT,
    )

    if item_id in {"base.bralette", "base.briefs"}:
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="soft_smooth",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    5.0, 16.0, 30.0, 40.0, FabricWeight.LIGHT
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.ACCEPTABLE,
            ),
            generic_context,
            generic_comfort,
        )

    if item_id == "day.technical_top":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="smooth_technical",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    6.0, 13.0, 25.0, 31.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.POOR,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.GOOD,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("spring", "autumn"),
                    good=("summer", "winter"),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab"),
                    good=("conversation", "workshop"),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab"),
                    good=("office", "casual_public", "home"),
                    acceptable=("outdoor",),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual", "smart_casual"),
                    poor=("formal", "lounge"),
                ),
                emotion_styles=RatedContext(
                    good=("focused", "energetic", "confident"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.MODERATE,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.GOOD,
            ),
        )

    if item_id == "day.utility_trousers":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.MIDWEIGHT,
                texture="smooth_woven",
                breathability=TraitLevel.MODERATE,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    0.0, 10.0, 24.0, 32.0, FabricWeight.MIDWEIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.ACCEPTABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.MODERATE,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.ACCEPTABLE,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.MODERATE,
                    strong_wind=Suitability.GOOD,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.MODERATE,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("spring", "autumn", "winter"),
                    good=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation", "casual"),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("office", "casual_public", "home"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    acceptable=("smart_casual",),
                    poor=("formal", "lounge"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.MODERATE,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.MODERATE,
                skin_contact=Suitability.GOOD,
            ),
        )

    if item_id == "day.engineer_jacket":
        return (
            MaterialProperties(
                stretch=TraitLevel.MODERATE,
                fabric_weight=FabricWeight.MIDWEIGHT,
                texture="matte_shell",
                breathability=TraitLevel.LOW,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    -8.0, 4.0, 18.0, 25.0, FabricWeight.MIDWEIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.EXCELLENT,
                    rain=Suitability.GOOD,
                    heavy_rain=Suitability.ACCEPTABLE,
                    snow=Suitability.GOOD,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.HIGH,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.EXCELLENT,
                    moderate=Suitability.GOOD,
                    high=Suitability.POOR,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.HIGH,
                    strong_wind=Suitability.EXCELLENT,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.POOR,
                    uv_protection=TraitLevel.HIGH,
                ),
                indoor=Suitability.ACCEPTABLE,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    poor=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("autumn", "winter"),
                    good=("spring",),
                    poor=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation", "outdoor"),
                    poor=("relaxing", "sleep"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("office", "casual_public"),
                    acceptable=("home",),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("smart_casual",),
                    acceptable=("casual",),
                    poor=("lounge",),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.ACCEPTABLE,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.LOW,
                flexibility=TraitLevel.MODERATE,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.LOW,
                skin_contact=Suitability.ACCEPTABLE,
            ),
        )

    if item_id in {"day.work_socks", "day.fingerless_gloves", "day.utility_belt"}:
        return (
            generic_material,
            generic_environment,
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    good=("spring", "summer", "autumn", "winter"),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation",),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab"),
                    good=("office", "casual_public", "home"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    acceptable=("smart_casual",),
                    poor=("formal", "lounge"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            generic_comfort,
        )

    if item_id == "day.work_boots":
        return (
            MaterialProperties(
                stretch=TraitLevel.LOW,
                fabric_weight=FabricWeight.HEAVY,
                texture="matte_structured",
                breathability=TraitLevel.LOW,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    -10.0, 3.0, 22.0, 31.0, FabricWeight.HEAVY
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.EXCELLENT,
                    rain=Suitability.EXCELLENT,
                    heavy_rain=Suitability.GOOD,
                    snow=Suitability.GOOD,
                ),
                moisture=MoistureProfile(
                    quick_dry=False,
                    water_resistance=TraitLevel.HIGH,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.GOOD,
                    high=Suitability.POOR,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.HIGH,
                    strong_wind=Suitability.EXCELLENT,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.ACCEPTABLE,
                    uv_protection=TraitLevel.HIGH,
                ),
                indoor=Suitability.GOOD,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    poor=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("autumn", "winter"),
                    good=("spring",),
                    acceptable=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop", "outdoor"),
                    good=("conversation",),
                    poor=("relaxing", "sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("casual_public",),
                    acceptable=("home", "office"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    poor=("lounge", "formal"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.ACCEPTABLE,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.LOW,
                flexibility=TraitLevel.MODERATE,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.LOW,
                skin_contact=Suitability.ACCEPTABLE,
            ),
        )

    if item_id == "night.lounge_tee":
        return (
            MaterialProperties(
                stretch=TraitLevel.MODERATE,
                fabric_weight=FabricWeight.LIGHT,
                texture="soft_brushed",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    10.0, 18.0, 28.0, 34.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.ACCEPTABLE,
                    rain=Suitability.POOR,
                    heavy_rain=Suitability.UNSUITABLE,
                    snow=Suitability.UNSUITABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=False,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.MODERATE,
                    wet_comfort=Suitability.POOR,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.ACCEPTABLE,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.ACCEPTABLE,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("evening", "night", "late_night"),
                    acceptable=("morning", "afternoon"),
                ),
                seasons=RatedContext(
                    excellent=("spring", "summer"),
                    good=("autumn",),
                    acceptable=("winter",),
                ),
                activities=RatedContext(
                    excellent=("relaxing", "sleep", "gaming", "casual_home"),
                    good=("conversation",),
                    poor=("engineering", "lab", "workshop"),
                    unsuitable=("formal",),
                ),
                settings=RatedContext(
                    excellent=("home", "private"),
                    acceptable=("casual_public",),
                    poor=("office", "workshop", "lab", "outdoor"),
                    unsuitable=("formal_event",),
                ),
                formality=RatedContext(
                    excellent=("lounge", "casual"),
                    poor=("work", "smart_casual"),
                    unsuitable=("formal",),
                ),
                emotion_styles=RatedContext(
                    excellent=("relaxed", "cozy", "playful"),
                    good=("fond", "settled"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.EXCELLENT,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.HIGH,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.NONE,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.EXCELLENT,
            ),
        )

    if item_id == "night.running_shorts":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="smooth_performance",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    14.5, 20.0, 32.0, 38.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.UNSUITABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.EXCELLENT,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.GOOD,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("evening", "night", "late_night"),
                    acceptable=("morning", "afternoon"),
                ),
                seasons=RatedContext(
                    excellent=("spring", "summer"),
                    good=("autumn",),
                    poor=("winter",),
                ),
                activities=RatedContext(
                    excellent=("relaxing", "exercise", "gaming", "casual_home"),
                    good=("conversation", "sleep", "casual_outing"),
                    poor=("engineering", "lab", "workshop"),
                    unsuitable=("formal",),
                ),
                settings=RatedContext(
                    excellent=("home", "private"),
                    good=("casual_public", "outdoor"),
                    poor=("workshop", "lab", "office"),
                    unsuitable=("formal_event",),
                ),
                formality=RatedContext(
                    excellent=("lounge", "casual"),
                    poor=("work", "smart_casual"),
                    unsuitable=("formal",),
                ),
                emotion_styles=RatedContext(
                    excellent=("relaxed", "playful", "energetic", "cozy"),
                    good=("fond", "settled"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.EXCELLENT,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.HIGH,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.MODERATE,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.EXCELLENT,
            ),
        )

    return generic_material, generic_environment, generic_context, generic_comfort


def _blueprint(
    design: GarmentDesign,
    *,
    canonical: bool = False,
    apply_starter_profiles: bool = True,
    provenance: str | None = None,
) -> GarmentBlueprint:
    if apply_starter_profiles:
        material_properties, environment, context, comfort = _starter_profiles(
            design.item_id
        )
        design = replace(
            design,
            material_properties=material_properties,
            environment=environment,
            context=context,
            comfort=comfort,
        )
    definition = validate_design(design)
    garment = Garment(
        item_id=design.item_id,
        name=design.name,
        layer=definition.layer,
        slots=definition.slots,
        coverage=definition.coverage,
        tail_clearance=(
            definition.tail_clearance or "tail_clearance" in design.features
        ),
        ear_clearance=(
            definition.ear_clearance or "ear_clearance" in design.features
        ),
        asset_ref=None,
        private_only=design.private_only,
    )
    return GarmentBlueprint(
        garment=garment,
        design=design,
        provenance=(
            provenance
            if provenance is not None
            else (
                "canonical_clothing_design"
                if canonical
                else "design_proposal_review_required"
            )
        ),
    )


def _no_graphic() -> GraphicDesign:
    return GraphicDesign()


def build_starter_wardrobe(
    *,
    state_path: str | Path | None = None,
) -> WardrobePrebuild:
    """Build seed wardrobe plus Sofía-accepted generated garments."""
    generated_blueprints: tuple[GarmentBlueprint, ...] = ()
    if state_path is not None:
        generated_path = generated_wardrobe_path(state_path)
        if generated_path.is_file():
            generated_blueprints = _load_wardrobe_data_file(
                generated_path,
                _blueprint,
            )
    blueprints = (
        *_load_underlayer_blueprints(),
        *_load_wardrobe_data_file("tops.json", _blueprint),
        *_load_wardrobe_data_file("bottoms.json", _blueprint),
        *_load_wardrobe_data_file("one_pieces.json", _blueprint),
        *_load_wardrobe_data_file("footwear.json", _blueprint),
        *_load_wardrobe_data_file("outerwear.json", _blueprint),
        *generated_blueprints,
        _blueprint(
            GarmentDesign(
                "day.work_socks", "Technical crew socks", "crew_socks",
                "fitted", None, "crew", None,
                "moisture-wicking technical knit", "black", "crimson",
                "solid", _no_graphic(),
                ("reinforced_heel", "reinforced_toe"),
                ("day", "engineer", "technical"), False,
                "Black technical crew socks in moisture-wicking knit with "
                "subtle crimson trim and reinforced heel and toe zones."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.fingerless_gloves", "Technical fingerless gloves",
                "fingerless_gloves", "fitted", None, "wrist", None,
                "stretch technical textile", "black", "cyan",
                "panelled", _no_graphic(), ("grip_palms",),
                ("day", "engineer", "technical", "accessory"), False,
                "Close-fitting black fingerless technical gloves with small "
                "cyan panel accents and textured grip palms."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.utility_belt", "Low-profile utility belt", "belt",
                "fitted", None, "waist", None,
                "matte technical webbing", "black", "crimson",
                "solid", _no_graphic(),
                ("low_profile_buckle", "small_utility_pouch"),
                ("day", "engineer", "technical", "accessory"), False,
                "A slim black technical utility belt with a compact buckle, "
                "small practical pouch, and restrained crimson hardware detail."
            ),
            canonical=True,
        ),
    )

    wardrobe = Wardrobe(tuple(bp.garment for bp in blueprints))
    day_items = (
        "base.bralette", "base.briefs", "day.technical_top",
        "day.utility_trousers", "day.engineer_jacket", "day.work_socks",
        "day.work_boots", "day.fingerless_gloves", "day.utility_belt",
    )
    night_items = (
        "base.bralette", "base.briefs", "night.lounge_tee",
        "night.running_shorts",
    )
    fallback_items = (
        "base.bralette", "base.briefs", "day.technical_top",
        "day.utility_trousers",
    )
    presets = (
        OutfitPlan(
            DAY_DEFAULT_OUTFIT_ID,
            day_items,
            frozenset({Activity.CONVERSATION, Activity.ENGINEERING, Activity.LAB}),
            ALL_SEASONS,
            style_tags=("day", "engineer", "technical", "canonical"),
            display_name="Day Engineer Outfit",
        ),
        OutfitPlan(
            NIGHT_LOUNGE_OUTFIT_ID,
            night_items,
            frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}),
            ALL_SEASONS,
            lounge=True,
            style_tags=("night", "lounge", "soft", "cozy"),
            display_name="Late-Night Lounge Outfit",
        ),
        OutfitPlan(
            FALLBACK_OUTFIT_ID,
            fallback_items,
            frozenset(Activity),
            ALL_SEASONS,
            style_tags=("covered", "fallback", "technical"),
            display_name="Covered Fallback Outfit",
            manual_only=True,
        ),
    )
    inputs = (
        StyleInput(
            DAY_DEFAULT_OUTFIT_ID,
            RequestStatus.USER_REQUESTED,
            "chat.2026-10-04.request.day_default",
            "Sparks requested a rebuilt default daytime outfit using the new structured wardrobe layout.",
        ),
        StyleInput(
            NIGHT_LOUNGE_OUTFIT_ID,
            RequestStatus.USER_REQUESTED,
            "chat.2026-10-04.request.night_lounge",
            "Sparks requested a rebuilt late-night lounge outfit using the new structured wardrobe layout.",
        ),
    )
    return WardrobePrebuild(wardrobe, blueprints, presets, inputs)
