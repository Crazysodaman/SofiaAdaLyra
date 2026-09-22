"""Only metadata tests: not asset availability, fit, opacity, or render proof."""
import json
from dataclasses import replace

import pytest

from sofia.avatar.wardrobe import Garment, Layer, VisibilityDenied, WardrobeError
from sofia.avatar.wardrobe_catalog import (
    DRAFT_STATUS, GarmentBlueprint, RequestStatus, StyleInput,
    WardrobePrebuild, build_starter_wardrobe,
)


def test_three_distinct_covered_presets_validate_against_actual_wardrobe():
    pack = build_starter_wardrobe()
    assert {p.outfit_id for p in pack.presets} == {
        "engineer.signature", "lounge.relaxed", "fallback.covered"
    }
    assert all(pack.wardrobe.selection(p.item_ids).covered_default for p in pack.presets)


def test_garments_are_blueprints_only_and_never_renderer_ready():
    pack = build_starter_wardrobe()
    for plan in pack.presets:
        selection = pack.wardrobe.selection(plan.item_ids)
        assert not selection.asset_refs_present
        with pytest.raises(VisibilityDenied):
            pack.wardrobe.require_public_ready(selection, assets_verified_by_renderer=True)
    assert all(bp.garment.asset_ref is None for bp in pack.blueprints)


def test_engineer_layering_clearances_and_named_fit_references():
    pack = build_starter_wardrobe()
    garments = pack.wardrobe.garments(pack.preset("engineer.signature").item_ids)
    assert any(g.item_id == "engineer.gauntlets" and g.layer is Layer.ACCESSORY for g in garments)
    assert any(g.item_id == "engineer.jacket" and g.layer is Layer.OUTER for g in garments)
    assert all(g.tail_clearance for g in garments if "tail" in g.slots)
    assert any("tail.opening.clearance" in bp.fit_anchors for bp in pack.blueprints)


def test_lounge_outfit_has_proposed_colors_and_tail_clearance():
    pack = build_starter_wardrobe()
    garment = next(bp for bp in pack.blueprints if bp.garment.item_id == "lounge.sweats")
    assert garment.garment.tail_clearance
    assert garment.provenance == "design_proposal_review_required"
    assert pack.preset("lounge.relaxed").lounge


def test_missing_or_wrong_outfit_id_is_denied():
    with pytest.raises(WardrobeError):
        build_starter_wardrobe().preset("not.here")


def test_manifest_json_serializable_and_explicitly_unbuilt():
    manifest = build_starter_wardrobe().manifest()
    assert manifest["stage"] == DRAFT_STATUS
    assert all(x["asset_ref"] is None for x in manifest["garments"])
    assert all(x["provenance"] in {
        "canonical_clothing_design", "design_proposal_review_required"
    } for x in manifest["garments"])
    assert json.loads(json.dumps(manifest)) == manifest


def test_request_does_not_invent_user_likes():
    pack = build_starter_wardrobe()
    assert len(pack.inputs) == 2
    assert all(record.status is RequestStatus.USER_REQUESTED for record in pack.inputs)
    assert not any(record.status is RequestStatus.USER_LIKED for record in pack.inputs)
    assert all(record.source_id.startswith("chat.") for record in pack.inputs)


def test_undocumented_preference_requires_real_source():
    with pytest.raises(WardrobeError):
        StyleInput("engineer.signature", RequestStatus.USER_LIKED,
                   "not a source", "Unproven preference")


def test_malformed_blueprint_rejected():
    original = build_starter_wardrobe().blueprints[0]
    with pytest.raises(WardrobeError):
        replace(original, primary_hex="purple")
    with pytest.raises(WardrobeError):
        replace(original, fit_anchors=("repeat", "repeat"))
    with pytest.raises(WardrobeError):
        replace(original, garment=replace(original.garment, asset_ref="fake.rendered.asset"))


def test_preset_cannot_reference_missing_blueprint():
    pack = build_starter_wardrobe()
    with pytest.raises(WardrobeError):
        replace(pack, blueprints=pack.blueprints[:-1])


def test_underwear_and_outerwear_share_body_without_same_layer_conflicts():
    pack = build_starter_wardrobe()
    garments = pack.wardrobe.garments(pack.preset("engineer.signature").item_ids)
    torso_layers = [g.layer for g in garments if "torso" in g.slots]
    assert torso_layers == [Layer.UNDERWEAR, Layer.BASE, Layer.OUTER]


def test_canonical_and_proposed_specs_separate_without_overwriting_canon():
    pack = build_starter_wardrobe()
    jacket = next(bp for bp in pack.blueprints if bp.garment.item_id == "engineer.jacket")
    assert jacket.provenance == "canonical_clothing_design"
    assert any("16 in" in note for note in jacket.construction)
    lounge = next(bp for bp in pack.blueprints if bp.garment.item_id == "lounge.top")
    assert lounge.provenance == "design_proposal_review_required"
