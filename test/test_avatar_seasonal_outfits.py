"""Seasonal wardrobe preset and self-composition contracts."""
from __future__ import annotations

from sofia.avatar.presentation import (
    AppearanceState,
    AudienceScope,
    PresentationAuthority,
    PrivatePresentationGrant,
)
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_outfit_catalog import generated_seasonal_outfits
from sofia.avatar.wardrobe_routine import Activity, Season
from sofia.avatar.wardrobe_studio import GarmentDesignRequest, WardrobeStudio


def grant():
    return PrivatePresentationGrant(True, True, True, True, False)


def test_each_season_has_25_normal_25_lounge_and_25_private_outfits():
    outfits = generated_seasonal_outfits()
    assert len(outfits) == 300
    for season in Season:
        rows = [plan for plan in outfits if plan.seasons == frozenset({season})]
        assert len([plan for plan in rows if not plan.lounge and not plan.private_only]) == 25
        assert len([plan for plan in rows if plan.lounge and not plan.private_only]) == 25
        assert len([plan for plan in rows if plan.private_only]) == 25


def test_all_300_outfits_use_real_catalog_pieces_and_respect_privacy():
    catalog = build_starter_wardrobe()
    seasonal = [
        plan for plan in catalog.presets
        if plan.outfit_id.startswith("seasonal.")
    ]
    assert len(seasonal) == 300
    for plan in seasonal:
        selected = catalog.wardrobe.selection(plan.item_ids)
        if plan.private_only:
            assert selected.private_only
        else:
            assert not selected.private_only
            assert selected.covered_default


def test_explicit_bra_and_panty_families_have_25_each():
    catalog = build_starter_wardrobe()
    bras = catalog.pieces(category="closet.bra", private_only=True)
    panties = catalog.pieces(category="closet.panty", private_only=True)
    assert len(bras) == 25
    assert len(panties) == 25
    assert all("Bra" in item.garment.name for item in bras)
    assert all("Panties" in item.garment.name for item in panties)


def test_studio_can_compose_new_public_outfit_from_individual_pieces():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)
    plan = studio.compose(
        outfit_id="studio.autumn.custom.01",
        item_ids=(
            "underlayer.top",
            "underlayer.bottom",
            "closet.normal.top.03",
            "closet.normal.bottom.08",
            "closet.normal.footwear.12",
            "closet.normal.neckwear.04",
        ),
        activities=frozenset({Activity.CONVERSATION}),
        seasons=frozenset({Season.AUTUMN}),
        style_tags=("self-composed", "autumn"),
        display_name="Autumn Workshop Casual",
    )
    assert plan.outfit_id == "studio.autumn.custom.01"
    assert not plan.private_only


def test_studio_refuses_private_piece_inside_public_composition():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)
    try:
        studio.compose(
            outfit_id="studio.bad.public",
            item_ids=("closet.private.bra.01", "closet.private.panty.01"),
            activities=frozenset({Activity.CONVERSATION}),
            seasons=frozenset({Season.SUMMER}),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("private pieces must not become public outfit")


def test_studio_can_design_new_piece_metadata_without_claiming_asset():
    studio = WardrobeStudio(build_starter_wardrobe())
    blueprint = studio.design_piece(
        GarmentDesignRequest(
            item_id="studio.top.crimson-night",
            name="Crimson Night Knit Top",
            category_id="closet.top",
            primary_hex="#8B1E3F",
            material="soft technical knit",
            style_tags=("self-designed", "crimson", "night"),
        )
    )
    assert blueprint.garment.asset_ref is None
    assert blueprint.garment.item_id == "studio.top.crimson-night"
    assert blueprint.provenance == "design_proposal_review_required"


def test_private_seasonal_outfit_requires_private_commit_and_public_stays_fallback():
    catalog = build_starter_wardrobe()
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits={plan.outfit_id: plan.item_ids for plan in catalog.presets},
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            "long layered", "deep crimson", "dark violet", ("engineer",)
        ),
    )
    target = "seasonal.winter.private.01"
    try:
        authority.propose_outfit(
            operation_id="private-without-flag",
            expected_revision=authority.current.revision,
            outfit_id=target,
            reason="bad route",
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("private outfit must require explicit private route")

    authority.propose_outfit(
        operation_id="private-winter",
        expected_revision=authority.current.revision,
        outfit_id=target,
        reason="private seasonal choice",
        private_only=True,
        daily=False,
    )
    authority.commit_text(
        operation_id="private-winter",
        renderer_unavailable=True,
        grant=grant(),
    )
    assert authority.projection(AudienceScope.PRIVATE, grant=grant()).outfit_id == target
    assert authority.projection(AudienceScope.PUBLIC).outfit_id == "engineer.signature"


def test_composed_outfit_can_register_present_and_survive_snapshot_restore(tmp_path):
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            "long layered", "deep crimson", "dark violet", ("engineer",)
        ),
    )
    studio = WardrobeStudio(catalog, authority=authority)
    plan = studio.compose(
        outfit_id="studio.spring.custom.01",
        item_ids=(
            "underlayer.top",
            "underlayer.bottom",
            "closet.normal.top.01",
            "closet.normal.bottom.02",
            "closet.normal.footwear.03",
        ),
        activities=frozenset({Activity.CONVERSATION}),
        seasons=frozenset({Season.SPRING}),
        style_tags=("self-composed", "spring"),
        display_name="Spring Self-Composed 01",
        register=True,
    )
    assert plan.outfit_id in authority.available_outfit_ids

    authority.propose_outfit(
        operation_id="studio-wear",
        expected_revision=authority.current.revision,
        outfit_id=plan.outfit_id,
        reason="self-composed outfit",
        daily=True,
    )
    authority.commit_text(
        operation_id="studio-wear",
        renderer_unavailable=True,
    )
    snapshot = authority.snapshot()

    restored = PresentationAuthority.restore(
        catalog.wardrobe,
        outfits=outfits,
        snapshot=snapshot,
    )
    assert restored.current.outfit_id == "studio.spring.custom.01"
    assert "studio.spring.custom.01" in restored.available_outfit_ids



def test_seasonal_outfit_combinations_are_distinct_across_all_seasons():
    outfits = generated_seasonal_outfits()

    normal = [
        plan.item_ids
        for plan in outfits
        if not plan.lounge and not plan.private_only
    ]
    lounge = [
        plan.item_ids
        for plan in outfits
        if plan.lounge and not plan.private_only
    ]
    private = [
        plan.item_ids
        for plan in outfits
        if plan.private_only
    ]

    assert len(normal) == 100
    assert len(set(normal)) == 100
    assert len(lounge) == 100
    assert len(set(lounge)) == 100
    assert len(private) == 100
    assert len(set(private)) == 100
