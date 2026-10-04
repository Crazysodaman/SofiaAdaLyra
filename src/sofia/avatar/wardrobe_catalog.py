"""Small reviewed starter wardrobe built from structured garment designs.

The type vocabulary lives in wardrobe_types.py. This catalog contains only
pieces Sofía currently owns as design metadata. No blueprint claims a mesh,
texture, renderer asset, or proof that an item is visibly worn.
"""
from __future__ import annotations

from dataclasses import replace

from .wardrobe import Garment, Wardrobe
from .wardrobe_prebuild import (
    DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID, FALLBACK_OUTFIT_ID,
    GarmentBlueprint, WardrobePrebuild, StyleInput, RequestStatus,
)
from .wardrobe_design import (
    ComfortProfile,
    ContextProfile,
    EnvironmentProfile,
    FabricWeight,
    GarmentDesign,
    GraphicDesign,
    HumidityProfile,
    MaterialProperties,
    MoistureProfile,
    MovementProfile,
    PrecipitationProfile,
    RatedContext,
    Suitability,
    SunlightProfile,
    TemperatureProfile,
    TraitLevel,
    WindProfile,
    resolve_color,
    validate_design,
)
from .wardrobe_types import garment_type
from .wardrobe_planner import (
    Activity,
    OutfitPlan,
    Season,
)


ALL_SEASONS = frozenset(Season)


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


def _blueprint(design: GarmentDesign, *, canonical: bool = False) -> GarmentBlueprint:
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
            "canonical_clothing_design"
            if canonical
            else "design_proposal_review_required"
        ),
    )


def _no_graphic() -> GraphicDesign:
    return GraphicDesign()


def build_starter_wardrobe() -> WardrobePrebuild:
    """Build the intentionally small day/night starter closet."""
    blueprints = (
        _blueprint(
            GarmentDesign(
                "base.bralette", "Soft technical bralette", "bralette",
                "fitted", None, "cropped", None,
                "soft breathable stretch knit", "black", "dark_violet",
                "solid", _no_graphic(), ("soft_band",),
                ("base", "technical", "soft"), False,
                "A simple black technical bralette in soft breathable stretch "
                "knit with a dark-violet band. Clean seams and low-profile "
                "edges keep it comfortable beneath other layers."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "base.briefs", "Soft technical briefs", "briefs",
                "fitted", "mid", "brief", None,
                "soft breathable stretch knit", "black", "dark_violet",
                "solid", _no_graphic(), ("soft_band", "tail_clearance"),
                ("base", "technical", "soft"), False,
                "Fitted black technical briefs with a mid rise, soft "
                "dark-violet waistband, and a comfortable tailored opening "
                "that preserves unrestricted tail movement."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.technical_top", "Fitted technical long-sleeve top",
                "long_sleeve_tee", "fitted", None, "hip", "long",
                "breathable performance-knit", "black", "crimson",
                "panelled",
                GraphicDesign(True, "left_chest", "small_cyan_circuit_mark"),
                ("reinforced_seams", "stretch_panels"),
                ("day", "engineer", "technical", "fitted"), False,
                "A fitted black long-sleeve technical top cut to the hip in "
                "breathable performance knit. Crimson seam accents follow the "
                "shoulders and sides, while a small cyan circuit mark sits on "
                "the left chest. The silhouette is clean and mobile, with "
                "reinforced seams and subtle stretch panels."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.utility_trousers", "Articulated utility trousers",
                "utility_trousers", "fitted", "mid", "full", None,
                "stretch technical weave", "charcoal", "dark_violet",
                "panelled",
                _no_graphic(),
                ("articulated_knees", "utility_pockets", "tail_clearance"),
                ("day", "engineer", "technical", "utility"), False,
                "Fitted charcoal utility trousers with a mid rise and full "
                "length, built from a flexible technical weave. Dark-violet "
                "panel accents, articulated knees, practical low-profile "
                "pockets, and a dedicated tail opening keep the look "
                "functional without becoming bulky."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.engineer_jacket", "Asymmetric engineer jacket",
                "engineer_jacket", "tailored", None, "hip", "long",
                "matte abrasion-resistant technical shell", "black", "crimson",
                "asymmetric_panelled", _no_graphic(),
                ("asymmetric_zip", "reinforced_panels", "cyan_micro_accents", "tail_clearance"),
                ("day", "engineer", "technical", "outerwear"), False,
                "A tailored hip-length black engineer jacket with long sleeves "
                "and an asymmetric front zip. Crimson edge lines, small cyan "
                "hardware accents, and reinforced shoulder and forearm panels "
                "give it a practical cyber-engineering look. The rear hem is "
                "shaped around the tail opening."
            ),
            canonical=True,
        ),
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
                "day.work_boots", "Mid-calf engineer boots", "work_boots",
                "fitted", None, "mid_calf", None,
                "matte technical leather and textile", "black", "dark_violet",
                "solid", _no_graphic(),
                ("grip_sole", "reinforced_toe", "side_zip"),
                ("day", "engineer", "technical", "footwear"), False,
                "Matte black mid-calf engineer boots with dark-violet paneling, "
                "a compact side zip, reinforced toe, and practical grip sole. "
                "The shape stays sleek rather than heavy."
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
        _blueprint(
            GarmentDesign(
                "night.lounge_tee", "Oversized late-night lounge T-shirt",
                "t_shirt", "oversized", None, "upper_thigh", "short",
                "soft brushed cotton-modal knit", "black", "dark_violet",
                "solid",
                GraphicDesign(True, "back_center", "violet_cyan_circuit_fox"),
                ("dropped_shoulders", "soft_hem"),
                ("night", "lounge", "soft", "cozy", "graphic"), False,
                "An oversized black late-night T-shirt in soft brushed "
                "cotton-modal knit, falling to the upper thigh with short "
                "sleeves and relaxed dropped shoulders. A dark-violet and cyan "
                "circuit-fox graphic sits across the upper back, while the "
                "front stays mostly clean."
            ),
        ),
        _blueprint(
            GarmentDesign(
                "night.running_shorts", "Fitted circuit running shorts",
                "running_shorts", "fitted", "mid", "short", None,
                "performance-knit", "dark_violet", "cyan", "none",
                GraphicDesign(True, "left_leg", "small_circuit_mark"),
                ("drawstring", "side_slits", "tail_clearance"),
                ("night", "lounge", "athletic", "soft"), False,
                "Fitted dark-violet running shorts with a mid rise and short "
                "athletic cut in soft performance knit. Cyan trim picks out the "
                "side seams, a small circuit mark sits on the left leg, and the "
                "design includes a drawstring, shallow side slits, and a "
                "comfortable tail opening."
            ),
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
