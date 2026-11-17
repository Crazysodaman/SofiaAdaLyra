"""Effect-free rig/scene and authoring-manifest validation boundaries."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.avatar3d.analysis import (
    RIG_COMPATIBILITY_CAPABILITY_ID, capability_registrations as avatar3d_regs,
    review_rig_scene_compatibility,
)
from sofia.modules.avatar_studio.analysis import (
    MANIFEST_CAPABILITY_ID, capability_registrations as avatar_studio_regs,
    review_authoring_manifest,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def rig_data(**change):
    data = {
        "model_id": "model:sofia3d",
        "rig_id": "rig:fox1",
        "model_sha256": SHA,
        "bones": [
            {"id": "bone:root", "parent_id": None, "wardrobe_refs": []},
            {"id": "bone:spine", "parent_id": "bone:root", "wardrobe_refs": ["wardrobe:jacket"]},
        ],
        "morphs": [{"id": "morph:smile", "bone_id": "bone:spine"}],
        "wardrobes": [{
            "id": "wardrobe:jacket",
            "required_bone_ids": ["bone:spine"],
            "required_morph_ids": ["morph:smile"],
        }],
    }
    data.update(change)
    return data


def rig_snapshot(observed_at=None, **change):
    return {
        "source_ref": "assets:review",
        "observed_at": observed_at or NOW.isoformat(),
        "rig": rig_data(**change),
    }


def asset(asset_id="asset:base", **change):
    data = {
        "id": asset_id,
        "kind": "scene",
        "digest": SHA,
        "layer_slot": "scene",
        "layer_order": 0,
        "audience": "public",
        "depends_on": [],
        "reviewed": True,
    }
    data.update(change)
    return data


def manifest_data(**change):
    data = {
        "manifest_version": "2.0.0",
        "scene_id": "scene:livingroom",
        "revision": 3,
        "audience": "public",
        "assets": [asset()],
    }
    data.update(change)
    return data


def manifest_snapshot(observed_at=None, **change):
    return {
        "source_ref": "assets:authoring",
        "observed_at": observed_at or NOW.isoformat(),
        "manifest": manifest_data(**change),
    }


def test_rig_scene_compatibility_happy_path_is_effect_free():
    report = review_rig_scene_compatibility(rig_snapshot(), now=NOW)
    assert report["status"] == "compatible" and report["compatible"] is True
    assert report["findings"] == [] and report["inspected_count"] == 4
    assert report["rig"]["bone_count"] == 2
    assert report["effect"] == "none" and report["action_authorized"] is False
    assert report["data_persisted"] is False and report["render_claimed"] is False
    assert report["rig_modified"] is False
    assert report["evidence_class"] == "supplied_unverified"


@pytest.mark.parametrize("change,expected", [
    ({"bones": [
        {"id": "bone:root", "parent_id": None, "wardrobe_refs": []},
        {"id": "bone:spine", "parent_id": "bone:missing", "wardrobe_refs": []},
    ]}, "missing_parent_bone"),
    ({"morphs": [{"id": "morph:smile", "bone_id": "bone:missing"}]}, "missing_morph_bone"),
    ({"wardrobes": [{
        "id": "wardrobe:jacket", "required_bone_ids": ["bone:missing"],
        "required_morph_ids": ["morph:smile"],
    }]}, "missing_wardrobe_bone"),
    ({"wardrobes": [{
        "id": "wardrobe:jacket", "required_bone_ids": ["bone:spine"],
        "required_morph_ids": ["morph:missing"],
    }]}, "missing_wardrobe_morph"),
    ({"bones": [
        {"id": "bone:root", "parent_id": "bone:spine", "wardrobe_refs": []},
        {"id": "bone:spine", "parent_id": "bone:root", "wardrobe_refs": []},
    ]}, "bone_cycle"),
])
def test_rig_scene_missing_references_are_incompatible(change, expected):
    report = review_rig_scene_compatibility(rig_snapshot(**change), now=NOW)
    assert report["status"] == "incompatible" and report["compatible"] is False
    assert expected in report["findings"] and report["render_claimed"] is False


@pytest.mark.parametrize("change", [
    {"model_id": "C:/Users/alice/model"},
    {"rig_id": "rigs/../../secret"},
    {"bones": [{"id": "bone:root", "parent_id": "private/root", "wardrobe_refs": []}]},
    {"model_sha256": "A" * 64},
    {"model_sha256": "a" * 63},
])
def test_rig_scene_rejects_unsafe_paths_and_bad_digests(change):
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(rig_snapshot(**change), now=NOW)


@pytest.mark.parametrize("change", [
    {"bones": [
        {"id": "bone:root", "parent_id": None, "wardrobe_refs": []},
        {"id": "bone:root", "parent_id": None, "wardrobe_refs": []},
    ]},
    {"morphs": [
        {"id": "morph:smile", "bone_id": "bone:spine"},
        {"id": "morph:smile", "bone_id": "bone:spine"},
    ]},
    {"bones": [{"id": "bone:root", "parent_id": None,
                "wardrobe_refs": ["wardrobe:jacket", "wardrobe:jacket"]}]},
])
def test_rig_scene_rejects_duplicate_references(change):
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(rig_snapshot(**change), now=NOW)


def test_rig_scene_rejects_oversized_and_unknown_fields():
    oversized = [{"id": f"bone:{index}", "parent_id": None, "wardrobe_refs": []}
                 for index in range(129)]
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(rig_snapshot(bones=oversized), now=NOW)
    too_many_refs = [f"wardrobe:{index}" for index in range(65)]
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(
            rig_snapshot(bones=[{"id": "bone:root", "parent_id": None,
                                 "wardrobe_refs": too_many_refs}]),
            now=NOW,
        )
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(rig_snapshot(execute=True), now=NOW)
    with pytest.raises(ValueError):
        review_rig_scene_compatibility(
            rig_snapshot(bones=[{"id": "bone:root", "parent_id": None,
                                 "wardrobe_refs": [], "rotate": True}]),
            now=NOW,
        )


def test_rig_scene_stale_or_future_never_leaks_or_claims_render():
    stale = rig_snapshot(observed_at=(NOW - timedelta(hours=2)).isoformat())
    future = rig_snapshot(observed_at=(NOW + timedelta(minutes=10)).isoformat())
    for report in (review_rig_scene_compatibility(stale, now=NOW),
                   review_rig_scene_compatibility(future, now=NOW)):
        assert report["status"] == "unknown" and report["compatible"] is None
        assert report["rig"] is None and report["render_claimed"] is False
        assert report["findings"] == ["snapshot_timestamp_invalid"]
        assert "model:sofia3d" not in json.dumps(report)


def test_authoring_manifest_happy_path_is_effect_free_and_public():
    report = review_authoring_manifest(manifest_snapshot(assets=[
        asset("asset:base", kind="scene", layer_slot="scene", layer_order=0),
        asset("asset:hair", kind="wardrobe", layer_slot="hair", layer_order=10,
              depends_on=["asset:base"]),
    ]), now=NOW)
    assert report["status"] == "reviewed" and report["compatible"] is True
    assert report["classification"] == "public" and report["review_required"] is False
    assert report["findings"] == [] and len(report["assets"]) == 2
    assert report["effect"] == "none" and report["action_authorized"] is False
    assert report["render_claimed"] is False and report["assets_modified"] is False
    assert report["wardrobe_modified"] is False


@pytest.mark.parametrize("change,expected", [
    ({"manifest_version": "3.0.0"}, "unsupported_manifest_version"),
    ({"assets": []}, "empty_manifest"),
    ({"assets": [asset("asset:base", layer_order=0),
                 asset("asset:hair", layer_slot="scene", layer_order=0)]}, "duplicate_slot_layer"),
    ({"assets": [asset("asset:base", depends_on=["asset:missing"])]}, "missing_asset_dependency"),
    ({"assets": [asset("asset:base", depends_on=["asset:base"])]}, "self_dependency"),
    ({"assets": [asset("asset:base", depends_on=["asset:hair"]),
                 asset("asset:hair", layer_slot="hair", layer_order=10)]}, "forward_dependency"),
])
def test_authoring_manifest_rejects_incompatible_layers(change, expected):
    report = review_authoring_manifest(manifest_snapshot(**change), now=NOW)
    assert report["compatible"] is False and expected in report["findings"]
    assert report["render_claimed"] is False and report["assets_modified"] is False


def test_authoring_manifest_review_is_required_without_blocking_compatibility():
    report = review_authoring_manifest(manifest_snapshot(assets=[
        asset("asset:base", reviewed=False),
    ]), now=NOW)
    assert report["compatible"] is True and report["review_required"] is True
    assert report["findings"] == ["asset_review_missing"]


@pytest.mark.parametrize("change", [
    {"scene_id": "C:/Users/alice/scene"},
    {"scene_id": "scenes/../../secret"},
    {"assets": [asset("assets/../../secret")]},
    {"assets": [asset("asset:base", digest="A" * 64)]},
    {"assets": [asset("asset:base", digest="a" * 63)]},
])
def test_authoring_manifest_rejects_unsafe_paths_and_bad_digests(change):
    with pytest.raises(ValueError):
        review_authoring_manifest(manifest_snapshot(**change), now=NOW)


@pytest.mark.parametrize("change", [
    {"assets": [asset("asset:base"), asset("asset:base")]},
    {"assets": [asset("asset:base", depends_on=["asset:hair", "asset:hair"])]},
])
def test_authoring_manifest_rejects_duplicate_identities(change):
    with pytest.raises(ValueError):
        review_authoring_manifest(manifest_snapshot(**change), now=NOW)


def test_authoring_manifest_rejects_oversized_and_unknown_fields():
    oversized = [asset(f"asset:{index}", layer_order=index) for index in range(129)]
    with pytest.raises(ValueError):
        review_authoring_manifest(manifest_snapshot(assets=oversized), now=NOW)
    many_dependencies = [f"asset:{index}" for index in range(65)]
    with pytest.raises(ValueError):
        review_authoring_manifest(
            manifest_snapshot(assets=[asset("asset:base", depends_on=many_dependencies)]),
            now=NOW,
        )
    with pytest.raises(ValueError):
        review_authoring_manifest(manifest_snapshot(execute=True), now=NOW)
    with pytest.raises(ValueError):
        review_authoring_manifest(
            manifest_snapshot(assets=[asset("asset:base", install=True)]),
            now=NOW,
        )
    with pytest.raises(ValueError):
        review_authoring_manifest(manifest_snapshot(manifest_version="v2"), now=NOW)


def test_authoring_manifest_private_classification_never_leaks_asset_ids():
    report = review_authoring_manifest(manifest_snapshot(assets=[
        asset("asset:secret", audience="private", layer_slot="hair", layer_order=10),
    ]), now=NOW)
    assert report["classification"] == "private"
    assert report["compatible"] is False
    assert "private_asset_in_public_manifest" in report["findings"]
    assert report["assets"] is None
    assert "asset:secret" not in json.dumps(report)


def test_authoring_manifest_stale_masks_private_manifest():
    stale = manifest_snapshot(observed_at=(NOW - timedelta(hours=2)).isoformat(),
                              assets=[asset("asset:secret", audience="private")])
    report = review_authoring_manifest(stale, now=NOW)
    assert report["status"] == "unknown" and report["classification"] is None
    assert report["manifest"] is None and report["assets"] is None
    assert report["findings"] == ["snapshot_timestamp_invalid"]
    assert "asset:secret" not in json.dumps(report)


def _registered(registrations, capability_id):
    return next((cap, handler) for cap, handler in registrations if cap.name == capability_id)


def test_new_capabilities_register_with_exact_bounded_requests():
    for registrations, capability_id, snapshot in (
        (avatar3d_regs(), RIG_COMPATIBILITY_CAPABILITY_ID, rig_snapshot()),
        (avatar_studio_regs(), MANIFEST_CAPABILITY_ID,
         manifest_snapshot(observed_at=datetime.now(timezone.utc).isoformat())),
    ):
        assert len(registrations) == 2
        assert len({cap.name for cap, _ in registrations}) == 2
        capability, handler = _registered(registrations, capability_id)
        assert isinstance(capability, Capability) and capability.name == capability_id
        result = handler(CapabilityRequest(
            capability=capability, parameters={"snapshot": snapshot},
            requested_scope=None, rationale="safe offline test",
        ))
        assert result["effect"] == "none" and result["action_authorized"] is False
        assert result["render_claimed"] is False and result["data_persisted"] is False
        with pytest.raises(ValueError):
            handler(CapabilityRequest(
                capability=capability, parameters={"execute": True},
                requested_scope=None, rationale="invalid action",
            ))
