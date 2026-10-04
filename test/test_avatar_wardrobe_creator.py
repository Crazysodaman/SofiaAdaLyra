"""Wardrobe creator and composition contracts after catalog reset."""
from __future__ import annotations

import pytest

from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import (
    DAY_DEFAULT_OUTFIT_ID,
    NIGHT_LOUNGE_OUTFIT_ID,
    build_starter_wardrobe,
)
from sofia.avatar.wardrobe_design import GraphicDesign
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
    assert {
        plan.outfit_id for plan in catalog.presets
    } == {
        DAY_DEFAULT_OUTFIT_ID,
        NIGHT_LOUNGE_OUTFIT_ID,
        "fallback.covered",
    }
