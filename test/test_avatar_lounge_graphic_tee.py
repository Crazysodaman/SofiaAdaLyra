"""Canonical graphic lounge metadata and manual-selection contracts."""
from datetime import datetime, timezone

from sofia.avatar.wardrobe_catalog import (
    GRAPHIC_OUTFIT_ID,
    GRAPHIC_REQUEST_SOURCE_ID,
    GRAPHIC_TEE_ID,
    SPARKS_LIKED_OUTFIT_SOURCE_IDS,
    RequestStatus,
    build_starter_wardrobe,
)
from sofia.avatar.wardrobe_planner import (
    Activity,
    OutfitPlanner,
    Season,
    WardrobeContext,
)


def test_graphic_lounge_is_in_canonical_catalog_but_manual_only():
    catalog = build_starter_wardrobe()
    plain = catalog.preset("lounge.relaxed")
    graphic = catalog.preset(GRAPHIC_OUTFIT_ID)

    assert plain.manual_only is False
    assert graphic.manual_only is True
    assert graphic.lounge is True


def test_graphic_replaces_only_shirt_not_pants_or_underlayers():
    catalog = build_starter_wardrobe()
    original = catalog.preset("lounge.relaxed").item_ids
    graphic = catalog.preset(GRAPHIC_OUTFIT_ID).item_ids

    assert len(original) == len(graphic)
    assert tuple(item for item in graphic if item != GRAPHIC_TEE_ID) == tuple(
        item for item in original if item != "lounge.top"
    )
    assert catalog.wardrobe.selection(graphic).covered_default


def test_graphic_blueprint_has_no_claimed_asset_and_same_fit_slots():
    catalog = build_starter_wardrobe()
    garments = {
        blueprint.garment.item_id: blueprint
        for blueprint in catalog.blueprints
    }
    graphic = garments[GRAPHIC_TEE_ID]
    plain = garments["lounge.top"]

    assert graphic.garment.asset_ref is None
    assert graphic.garment.layer == plain.garment.layer
    assert graphic.garment.slots == plain.garment.slots
    assert graphic.garment.coverage == plain.garment.coverage
    assert graphic.fit_anchors == plain.fit_anchors
    assert graphic.provenance == "design_proposal_review_required"


def test_graphic_request_is_not_misrepresented_as_a_like():
    catalog = build_starter_wardrobe()
    requests = [
        entry
        for entry in catalog.inputs
        if entry.subject_id == GRAPHIC_TEE_ID
    ]
    assert len(requests) == 1
    assert requests[0].status is RequestStatus.USER_REQUESTED
    assert requests[0].source_id == GRAPHIC_REQUEST_SOURCE_ID

    likes = tuple(
        entry
        for entry in catalog.inputs
        if (
            entry.status is RequestStatus.USER_LIKED
            and entry.source_id in SPARKS_LIKED_OUTFIT_SOURCE_IDS
        )
    )
    assert {entry.subject_id for entry in likes} == {
        "engineer.signature",
        "lounge.relaxed",
    }
    assert GRAPHIC_TEE_ID not in {
        entry.subject_id
        for entry in likes
    }


def test_manual_graphic_outfit_is_excluded_from_automatic_planner():
    catalog = build_starter_wardrobe()
    planner = OutfitPlanner(catalog.wardrobe, catalog.presets)
    context = WardrobeContext(
        now=datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc),
        season=Season.AUTUMN,
        activity=Activity.RELAXING,
    )

    proposal = planner.suggest(context)
    assert proposal.outfit_id != GRAPHIC_OUTFIT_ID


def test_manifest_marks_manual_outfits_explicitly():
    manifest = build_starter_wardrobe().manifest()
    graphic = next(
        outfit
        for outfit in manifest["outfits"]
        if outfit["outfit_id"] == GRAPHIC_OUTFIT_ID
    )
    assert graphic["manual_only"] is True
    assert all(item["asset_ref"] is None for item in manifest["garments"])
