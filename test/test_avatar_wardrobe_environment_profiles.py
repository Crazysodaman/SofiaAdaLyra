"""Rich garment environment/context metadata contracts."""
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import (
    FabricWeight,
    Suitability,
    TraitLevel,
)


def _piece(item_id):
    return next(
        bp for bp in build_starter_wardrobe().blueprints
        if bp.garment.item_id == item_id
    )


def test_running_shorts_have_rich_environment_context_and_comfort():
    design = _piece("night.running_shorts").design

    assert design.environment.temperature.minimum_c == 5.0
    assert design.environment.temperature.preferred_minimum_c == 15.0
    assert design.environment.temperature.preferred_maximum_c == 32.0
    assert design.environment.temperature.maximum_c == 39.0
    assert design.environment.temperature.thermal_weight is FabricWeight.LIGHT

    assert design.environment.precipitation.dry is Suitability.EXCELLENT
    assert design.environment.precipitation.rain is Suitability.ACCEPTABLE
    assert design.environment.precipitation.snow is Suitability.POOR
    assert design.environment.moisture.quick_dry is True
    assert design.environment.humidity.high is Suitability.GOOD
    assert design.environment.wind.strong_wind is Suitability.ACCEPTABLE
    assert design.environment.indoor is Suitability.EXCELLENT
    assert design.environment.outdoor is Suitability.EXCELLENT

    assert design.context.dayparts.rating("late_night") is Suitability.GOOD
    assert design.context.seasons.rating("summer") is Suitability.GOOD
    assert design.context.activities.rating("exercise") is Suitability.EXCELLENT
    assert design.context.settings.rating("home") is Suitability.GOOD
    assert design.context.formality.rating("formal") is Suitability.POOR
    assert design.context.movement.active_comfort is Suitability.EXCELLENT

    assert design.material_properties.stretch is TraitLevel.HIGH
    assert design.material_properties.breathability is TraitLevel.HIGH
    assert design.comfort.ventilation is TraitLevel.HIGH
    assert design.comfort.skin_contact is Suitability.GOOD


def test_jacket_and_lounge_tee_encode_different_environment_roles():
    jacket = _piece("day.engineer_jacket").design
    lounge = _piece("night.lounge_tee").design

    assert jacket.environment.wind.resistance is TraitLevel.MODERATE
    assert jacket.environment.precipitation.rain is Suitability.ACCEPTABLE
    assert jacket.context.activities.rating("engineering") is Suitability.EXCELLENT

    assert lounge.environment.indoor is Suitability.EXCELLENT
    assert lounge.environment.precipitation.heavy_rain is Suitability.UNSUITABLE
    assert lounge.context.activities.rating("relaxing") is Suitability.EXCELLENT
    assert lounge.context.activities.rating("engineering") is Suitability.POOR


def test_manifest_exposes_creator_profiles_and_no_maintenance_block():
    manifest = build_starter_wardrobe().manifest()
    shorts = next(
        row for row in manifest["garments"]
        if row["item_id"] == "night.running_shorts"
    )

    assert shorts["material_properties"]["breathability"] == "high"
    assert shorts["environment"]["temperature"]["preferred_minimum_f"] == 59.0
    assert shorts["environment"]["temperature"]["preferred_maximum_f"] == 89.6
    assert shorts["environment"]["moisture"]["quick_dry"] is True
    assert shorts["context"]["dayparts"]["good"] == [
        "morning", "afternoon", "evening", "night", "late_night"
    ]
    assert shorts["comfort"]["ventilation"] == "high"
    assert "maintenance" not in shorts
    assert list(shorts)[-1] == "description"


def test_unprofiled_authored_design_defaults_to_unspecified_not_guesswork():
    from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
    from sofia.avatar.wardrobe_design import GraphicDesign

    catalog = build_starter_wardrobe()
    blueprint = WardrobeStudio(catalog).design_piece(
        GarmentDesignRequest(
            item_id="studio.unprofiled.tee",
            name="Unprofiled test tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="cotton knit",
            primary="black",
            accent=None,
            pattern="solid",
            graphic=GraphicDesign(),
            features=(),
            description="A test tee whose environment metadata was not supplied.",
        )
    )

    assert blueprint.design.environment.indoor is Suitability.UNSPECIFIED
    assert blueprint.design.context.dayparts.rating("night") is Suitability.UNSPECIFIED
    assert blueprint.design.comfort.softness is TraitLevel.UNSPECIFIED
