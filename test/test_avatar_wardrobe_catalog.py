"""Structured starter wardrobe catalog contracts."""
import json
from dataclasses import replace

import pytest

from sofia.avatar.wardrobe import Layer, VisibilityDenied, WardrobeError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_prebuild import (
    DAY_DEFAULT_OUTFIT_ID,
    DRAFT_STATUS,
    FALLBACK_OUTFIT_ID,
    NIGHT_LOUNGE_OUTFIT_ID,
    RequestStatus,
    StyleInput,
)


def test_approved_saved_outfits_and_fallback_ship():
    pack = build_starter_wardrobe()
    ids = {plan.outfit_id for plan in pack.presets}
    assert len(ids) == 24
    assert DAY_DEFAULT_OUTFIT_ID in ids
    assert NIGHT_LOUNGE_OUTFIT_ID in ids
    assert FALLBACK_OUTFIT_ID in ids
    assert "private.violet_tease" in ids
    assert "private.circuit_after_dark" in ids
    assert "private.rope_harness" in ids
    assert pack.preset(NIGHT_LOUNGE_OUTFIT_ID).lounge is True
    assert pack.preset(FALLBACK_OUTFIT_ID).manual_only is True

    for plan in pack.presets:
        selection = pack.wardrobe.selection(plan.item_ids)
        if plan.private_only:
            assert selection.private_only
            assert plan.manual_only
        else:
            assert selection.covered_default
            assert not selection.private_only


def test_blueprints_are_design_metadata_not_renderer_claims():
    pack = build_starter_wardrobe()
    for plan in pack.presets:
        selection = pack.wardrobe.selection(plan.item_ids)
        assert not selection.asset_refs_present
        with pytest.raises(VisibilityDenied):
            pack.wardrobe.require_public_ready(
                selection,
                assets_verified_by_renderer=True,
            )
    assert all(bp.garment.asset_ref is None for bp in pack.blueprints)


def test_day_outfit_preserves_layering_and_tail_clearance():
    pack = build_starter_wardrobe()
    garments = pack.wardrobe.garments(
        pack.preset(DAY_DEFAULT_OUTFIT_ID).item_ids
    )
    torso_layers = [g.layer for g in garments if "torso" in g.slots]
    assert torso_layers == [Layer.UNDERWEAR, Layer.BASE, Layer.OUTER]
    assert all(g.tail_clearance for g in garments if "tail" in g.slots)
    assert any(
        bp.garment.item_id == "day.engineer_jacket"
        and bp.provenance == "canonical_clothing_design"
        for bp in pack.blueprints
    )


def test_night_lounge_outfit_uses_new_structured_pieces():
    pack = build_starter_wardrobe()
    plan = pack.preset(NIGHT_LOUNGE_OUTFIT_ID)

    assert plan.item_ids == (
        "under.upper.lounge_bralette",
        "under.lower.lounge_boyshort",
        "night.lounge_tee",
        "night.running_shorts",
        "foot.soft_violet_slippers",
    )
    shorts = next(
        bp for bp in pack.blueprints
        if bp.garment.item_id == "night.running_shorts"
    )
    assert shorts.garment.tail_clearance is True
    assert shorts.provenance == "design_proposal_review_required"


def test_manifest_is_v2_json_serializable_and_modeler_ready():
    manifest = build_starter_wardrobe().manifest()

    assert manifest["schema"] == "sofia.avatar.wardrobe.prebuild.v2"
    assert manifest["stage"] == DRAFT_STATUS
    assert all(row["asset_ref"] is None for row in manifest["garments"])
    assert all("type" in row for row in manifest["garments"])
    assert all("fit" in row for row in manifest["garments"])
    assert all("length" in row for row in manifest["garments"])
    assert all("sleeve_length" in row for row in manifest["garments"])
    assert all("graphic" in row for row in manifest["garments"])
    assert all(row["description"].strip() for row in manifest["garments"])
    assert json.loads(json.dumps(manifest)) == manifest


def test_new_defaults_are_requests_not_invented_likes():
    pack = build_starter_wardrobe()

    assert {item.status for item in pack.inputs} == {
        RequestStatus.USER_REQUESTED
    }
    assert {item.subject_id for item in pack.inputs} == {
        DAY_DEFAULT_OUTFIT_ID,
        NIGHT_LOUNGE_OUTFIT_ID,
    }
    assert pack.reviewed_preferences() == ()


def test_invalid_style_source_and_unknown_preset_fail_closed():
    with pytest.raises(WardrobeError):
        StyleInput(
            DAY_DEFAULT_OUTFIT_ID,
            RequestStatus.USER_LIKED,
            "not a source",
            "Unproven preference",
        )
    with pytest.raises(WardrobeError):
        build_starter_wardrobe().preset("not.here")


def test_blueprint_rejects_claimed_asset_or_design_identity_mismatch():
    original = build_starter_wardrobe().blueprints[0]

    with pytest.raises(WardrobeError):
        replace(
            original,
            garment=replace(
                original.garment,
                asset_ref="fake.rendered.asset",
            ),
        )

    with pytest.raises(WardrobeError):
        replace(
            original,
            garment=replace(
                original.garment,
                item_id="different.id",
            ),
        )
