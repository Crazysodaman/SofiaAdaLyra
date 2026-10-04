"""Wardrobe creator and composition contracts after catalog reset."""
from __future__ import annotations

import pytest

from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_prebuild import DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID
from sofia.avatar.wardrobe_design import (
    ComfortProfile,
    ContextProfile,
    EnvironmentProfile,
    FabricWeight,
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
)
from sofia.avatar.wardrobe_planner import Activity, Season


def test_studio_designs_structured_running_shorts():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)
    blueprint = studio.design_piece(
        GarmentDesignRequest(
            item_id="studio.running_shorts.violet",
            name="Violet circuit running shorts",
            garment_type="running_shorts",
            fit="fitted",
            rise="mid",
            length="short",
            sleeve_length=None,
            material="performance-knit",
            primary="dark_violet",
            accent="cyan",
            pattern="none",
            graphic=GraphicDesign(
                True,
                "left_leg",
                "small_circuit_mark",
            ),
            features=("drawstring", "side_slits", "tail_clearance"),
            style_tags=("athletic", "violet"),
            description=(
                "Fitted violet running shorts with cyan trim, a small circuit "
                "mark on the left leg, side slits, drawstring, and tail opening."
            ),
        )
    )

    assert blueprint.design.garment_type == "running_shorts"
    assert blueprint.design.rise == "mid"
    assert blueprint.garment.tail_clearance is True
    assert blueprint.garment.asset_ref is None


def test_top_creator_requires_explicit_sleeve_length():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)

    with pytest.raises(WardrobeError, match="sleeve_length"):
        studio.design_piece(
            GarmentDesignRequest(
                item_id="studio.top.bad",
                name="Incomplete T-shirt",
                garment_type="t_shirt",
                fit="relaxed",
                rise=None,
                length="hip",
                sleeve_length=None,
                material="cotton knit",
                primary="black",
                accent=None,
                pattern="solid",
                graphic=GraphicDesign(),
                features=(),
                description="A deliberately incomplete test design.",
            )
        )


def test_studio_composes_with_real_starter_pieces():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)

    plan = studio.compose(
        outfit_id="studio.day.minimal",
        item_ids=(
            "base.bralette",
            "base.briefs",
            "day.technical_top",
            "day.utility_trousers",
        ),
        activities=frozenset({Activity.CONVERSATION}),
        seasons=frozenset(Season),
        style_tags=("technical", "minimal"),
    )

    assert plan.item_ids[-2:] == (
        "day.technical_top",
        "day.utility_trousers",
    )
    assert catalog.wardrobe.selection(plan.item_ids).covered_default


def test_reset_has_no_generated_seasonal_inventory():
    catalog = build_starter_wardrobe()

    assert not any(
        plan.outfit_id.startswith("seasonal.")
        for plan in catalog.presets
    )
    preset_ids = {plan.outfit_id for plan in catalog.presets}
    assert DAY_DEFAULT_OUTFIT_ID in preset_ids
    assert NIGHT_LOUNGE_OUTFIT_ID in preset_ids
    assert "fallback.covered" in preset_ids
    assert len(preset_ids) == 24


def test_studio_preserves_explicit_environment_context_and_comfort_profiles():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)

    material_properties = MaterialProperties(
        stretch=TraitLevel.HIGH,
        fabric_weight=FabricWeight.LIGHT,
        texture="smooth_performance",
        breathability=TraitLevel.HIGH,
        insulation=TraitLevel.LOW,
    )
    environment = EnvironmentProfile(
        temperature=TemperatureProfile(
            12.0,
            18.0,
            29.0,
            35.0,
            FabricWeight.LIGHT,
        ),
        precipitation=PrecipitationProfile(
            dry=Suitability.EXCELLENT,
            mist=Suitability.GOOD,
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
    )
    context = ContextProfile(
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
            excellent=("relaxing", "gaming"),
            good=("conversation", "exercise"),
            poor=("engineering", "workshop"),
            unsuitable=("formal",),
        ),
        settings=RatedContext(
            excellent=("home", "private"),
            good=("casual_public",),
            poor=("workshop", "lab"),
        ),
        formality=RatedContext(
            excellent=("lounge", "casual"),
            poor=("work",),
            unsuitable=("formal",),
        ),
        emotion_styles=RatedContext(
            excellent=("relaxed", "playful"),
            good=("energetic",),
        ),
        movement=MovementProfile(
            mobility=Suitability.EXCELLENT,
            seated_comfort=Suitability.EXCELLENT,
            active_comfort=Suitability.GOOD,
        ),
    )
    comfort = ComfortProfile(
        softness=TraitLevel.HIGH,
        flexibility=TraitLevel.HIGH,
        compression=TraitLevel.LOW,
        heat_retention=TraitLevel.LOW,
        ventilation=TraitLevel.HIGH,
        skin_contact=Suitability.EXCELLENT,
    )

    blueprint = studio.design_piece(
        GarmentDesignRequest(
            item_id="studio.lounge_tee.custom",
            name="Custom late-night lounge tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="performance cotton-modal knit",
            primary="black",
            accent="cyan",
            pattern="solid",
            graphic=GraphicDesign(
                True,
                "left_chest",
                "small_circuit_mark",
            ),
            features=("soft_hem",),
            style_tags=("lounge", "night"),
            description=(
                "A relaxed black short-sleeve lounge tee with a small cyan "
                "circuit mark, designed for warm evenings and indoor comfort."
            ),
            material_properties=material_properties,
            environment=environment,
            context=context,
            comfort=comfort,
        )
    )

    assert blueprint.design.material_properties == material_properties
    assert blueprint.design.environment == environment
    assert blueprint.design.context == context
    assert blueprint.design.comfort == comfort
    assert (
        blueprint.design.environment.temperature.suitability_for(24.0)
        is Suitability.EXCELLENT
    )
    assert (
        blueprint.design.context.dayparts.rating("late_night")
        is Suitability.EXCELLENT
    )
    assert blueprint.design.environment.moisture.quick_dry is True
    assert not hasattr(blueprint.design, "maintenance")
