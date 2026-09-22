"""Metadata-only graphic tee tests; not print art, fitted meshes or rendering."""

import pytest

from sofia.avatar.lounge_graphic_tee import (
    GRAPHIC_OUTFIT_ID, GRAPHIC_REQUEST_SOURCE_ID, GRAPHIC_TEE_ID,
    build_graphic_lounge_variation,
)
from sofia.avatar.style_context import project_style_context
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import RequestStatus


def test_plain_lounge_remains_default_and_graphic_is_explicit():
    variant = build_graphic_lounge_variation()
    assert variant.select_lounge().outfit_id == "lounge.relaxed"
    assert variant.select_lounge(graphic_requested=True).outfit_id == GRAPHIC_OUTFIT_ID
    assert variant.optional_plan not in variant.catalog.presets


def test_graphic_replaces_only_shirt_not_pants_or_underlayers():
    variant = build_graphic_lounge_variation()
    original = variant.catalog.preset("lounge.relaxed").item_ids
    graphic = variant.optional_plan.item_ids
    assert len(original) == len(graphic)
    assert tuple(item for item in graphic if item != GRAPHIC_TEE_ID) == tuple(
        item for item in original if item != "lounge.top"
    )
    assert variant.catalog.wardrobe.selection(graphic).covered_default


def test_graphic_blueprint_has_no_claimed_asset_and_same_fit_slots():
    variant = build_graphic_lounge_variation()
    garments = {bp.garment.item_id: bp for bp in variant.catalog.blueprints}
    graphic = garments[GRAPHIC_TEE_ID]
    plain = garments["lounge.top"]
    assert graphic.garment.asset_ref is None
    assert graphic.garment.layer == plain.garment.layer
    assert graphic.garment.slots == plain.garment.slots
    assert graphic.garment.coverage == plain.garment.coverage
    assert graphic.fit_anchors == plain.fit_anchors
    assert graphic.provenance == "design_proposal_review_required"


def test_request_is_not_misrepresented_as_like_or_sofia_preference():
    variant = build_graphic_lounge_variation()
    requests = [entry for entry in variant.catalog.inputs if entry.subject_id == GRAPHIC_TEE_ID]
    assert len(requests) == 1
    assert requests[0].status is RequestStatus.USER_REQUESTED
    assert requests[0].source_id == GRAPHIC_REQUEST_SOURCE_ID
    projection = project_style_context(
        variant.catalog,
        reviewed_source_ids=frozenset({
            "chat.2026-09-22.like.both.engineer",
            "chat.2026-09-22.like.both.lounge",
        }),
    ).for_chat()
    assert {entry["subject_id"] for entry in projection["liked_by_sparks"]} == {
        "engineer.signature", "lounge.relaxed"
    }
    assert GRAPHIC_TEE_ID not in {entry["subject_id"] for entry in projection["liked_by_sparks"]}
    assert projection["sofia_preference_claims"] == []


def test_manifest_exports_explicit_variant_without_false_asset_claim():
    variant = build_graphic_lounge_variation()
    manifest = variant.manifest()
    assert len(manifest["garments"]) == 17
    assert len(manifest["outfits"]) == 3
    assert manifest["optional_outfits"][0]["selection"] == "explicit_optional_not_automatic"
    assert manifest["optional_outfits"][0]["outfit_id"] == GRAPHIC_OUTFIT_ID
    assert len(manifest["graphic_print_concepts"]) == 3
    assert all(item["asset_ref"] is None for item in manifest["garments"])


def test_graphic_toggle_requires_strict_boolean():
    variant = build_graphic_lounge_variation()
    for invalid in (1, "true", None):
        with pytest.raises(WardrobeError):
            variant.select_lounge(graphic_requested=invalid)
