"""Avatar A0 metadata fixtures, not geometry/cloth simulation/age verification."""
import pytest
from sofia.avatar import (
    Garment, Layer, PreviewRequest, Wardrobe, WardrobeConflict,
    WardrobeError, VisibilityDenied,
)


def garment(item_id="shirt", layer=Layer.BASE, slots=("torso",), coverage=("torso",),
            asset_ref=None, **kwargs):
    return Garment(item_id, item_id, layer, slots, coverage, asset_ref=asset_ref, **kwargs)


def outfit():
    return Wardrobe((garment(asset_ref="asset.shirt"),
                     garment("trousers", slots=("pelvis", "legs"),
                             coverage=("pelvis", "legs"), asset_ref="asset.trousers")))


@pytest.mark.parametrize("layer", list(Layer))
def test_supported_layers(layer):
    assert garment(layer=layer).layer == layer


def test_full_clothed_outfit_with_assets_is_public_ready():
    w = outfit()
    state = w.selection(("shirt", "trousers"))
    assert state.covered_default and state.asset_refs_present
    w.require_public_ready(state, assets_verified_by_renderer=True)


def test_no_nude_or_partially_clothed_public_fallback():
    w = outfit()
    for ids in ((), ("shirt",), ("trousers",)):
        with pytest.raises(VisibilityDenied):
            w.require_public_ready(w.selection(ids))


def test_metadata_only_cannot_claim_render_ready():
    w = Wardrobe((garment(), garment("bottoms", slots=("pelvis",), coverage=("pelvis",))))
    state = w.selection(("shirt", "bottoms"))
    assert state.covered_default and not state.asset_refs_present
    with pytest.raises(VisibilityDenied):
        w.require_public_ready(state, assets_verified_by_renderer=True)


def test_underwear_and_outerwear_coexist_with_base_layer():
    w = Wardrobe((garment("bra", Layer.UNDERWEAR),
                  garment("shirt", Layer.BASE),
                  garment("jacket", Layer.OUTER)))
    state = w.selection(("bra", "shirt", "jacket"))
    assert state.item_ids == ("bra", "shirt", "jacket")


def test_two_items_in_same_layer_same_slot_conflict():
    w = Wardrobe((garment("shirt"), garment("other")))
    with pytest.raises(WardrobeConflict):
        w.selection(("shirt", "other"))


def test_same_layer_different_slots_allowed():
    w = Wardrobe((garment("shirt"), garment("pants", slots=("pelvis",), coverage=("pelvis",))))
    assert w.selection(("shirt", "pants")).covered_default


@pytest.mark.parametrize("ids", [("missing",), ("shirt", "shirt"), ["shirt"]])
def test_unknown_duplicate_or_non_tuple_selection_denied(ids):
    with pytest.raises((WardrobeConflict, WardrobeError)):
        outfit().selection(ids)


def test_missing_ear_tail_clearance_rejected():
    w = Wardrobe((garment("hood", slots=("head", "ears"), coverage=("head", "ears")),))
    with pytest.raises(WardrobeConflict, match="ear"):
        w.selection(("hood",))
    w = Wardrobe((garment("coat", slots=("torso", "tail"), coverage=("torso",)),))
    with pytest.raises(WardrobeConflict, match="tail"):
        w.selection(("coat",))


def test_explicit_ear_tail_clearance_allowed():
    w = Wardrobe((garment("hood", slots=("head", "ears"), coverage=("head",),
                          ear_clearance=True),
                  garment("coat", Layer.OUTER, slots=("torso", "tail"),
                          coverage=("torso",), tail_clearance=True)))
    assert len(w.selection(("hood", "coat")).item_ids) == 2


@pytest.mark.parametrize("preview", [
    PreviewRequest(),
    PreviewRequest(adult_verified=True),
    PreviewRequest(adult_verified=True, owner_verified=True),
    PreviewRequest(adult_verified=True, owner_verified=True, private_local_session=True),
    PreviewRequest(True, True, True, True, True),
])
def test_restricted_preview_denies_unknown_or_incomplete_facts(preview):
    with pytest.raises(VisibilityDenied):
        outfit().restricted_preview(request=preview)


def test_restricted_preview_requires_all_verified_facts_and_no_stop():
    preview = PreviewRequest(True, True, True, True, False)
    outfit().restricted_preview(request=preview)


@pytest.mark.parametrize("bad", [None, "true", 1])
def test_restricted_preview_rejects_nonboolean_trusted_facts(bad):
    with pytest.raises(WardrobeError):
        PreviewRequest(adult_verified=bad)


def test_non_preview_object_denied():
    with pytest.raises(VisibilityDenied):
        outfit().restricted_preview(request="yes")


@pytest.mark.parametrize("bad", ["", "bad name", "x" * 129, None])
def test_invalid_garment_ids(bad):
    with pytest.raises(WardrobeError):
        garment(bad)


def test_bad_coverage_rejected():
    with pytest.raises(WardrobeError):
        garment(coverage=("pelvis",))


def test_duplicate_catalogue_ids_rejected():
    with pytest.raises(WardrobeError):
        Wardrobe((garment(), garment()))


def test_flags_must_be_real_bool():
    with pytest.raises(WardrobeError):
        garment(tail_clearance=1)


def test_declared_asset_refs_do_not_prove_actual_renderer_assets():
    w = outfit()
    state = w.selection(("shirt", "trousers"))
    with pytest.raises(VisibilityDenied):
        w.require_public_ready(state)
    with pytest.raises(VisibilityDenied):
        w.require_public_ready(state, assets_verified_by_renderer="true")
