import pytest

from sofia.avatar.wardrobe import Garment, Layer, Wardrobe
from sofia.avatar.shared_wardrobe_state import (
    PresentationMode, SharedWardrobeState, TransitionStatus,
    WardrobeStateConflict, WardrobeStateDenied,
)


def garment(item_id, layer, slots, coverage, asset_ref=None, **kwargs):
    return Garment(item_id, item_id, layer, slots, coverage, asset_ref=asset_ref, **kwargs)


def wardrobe():
    return Wardrobe((
        garment("shirt", Layer.BASE, ("torso",), ("torso",), "asset.shirt"),
        garment("pants", Layer.BASE, ("pelvis", "legs"), ("pelvis", "legs"), "asset.pants"),
        garment("jacket", Layer.OUTER, ("torso",), ("torso",), "asset.jacket"),
        garment("lounge_top", Layer.BASE, ("torso",), ("torso",), "asset.lounge_top"),
        garment("lounge_pants", Layer.BASE, ("pelvis", "legs"), ("pelvis", "legs"), "asset.lounge_pants"),
    ))


def state(mode=PresentationMode.TEXT_FALLBACK, verified=False):
    return SharedWardrobeState(
        wardrobe(),
        initial_item_ids=("shirt", "pants"),
        initial_outfit_id="engineer.base",
        initial_mode=mode,
        avatar_initially_verified=verified,
    )


def test_one_authoritative_state_drives_text_projection():
    s = state()
    p = s.text_projection()
    assert p.current_item_ids == s.state.item_ids == ("shirt", "pants")
    assert p.current_outfit_id == "engineer.base"
    assert p.presentation_mode is PresentationMode.TEXT_FALLBACK
    assert not p.avatar_visible


def test_avatar_change_is_not_current_before_verified_ack():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    p = s.text_projection()
    assert p.current_item_ids == ("shirt", "pants")
    assert p.pending_item_ids == ("lounge_top", "lounge_pants")
    assert p.pending_status is TransitionStatus.PENDING
    assert s.state.revision == 1


def test_verified_avatar_ack_commits_same_state_for_text_and_visual():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    current = s.acknowledge_avatar(
        operation_id="change1", renderer_succeeded=True, assets_verified=True
    )
    assert current.revision == 2
    assert current.item_ids == ("lounge_top", "lounge_pants")
    assert current.avatar_visible
    assert s.text_projection().current_item_ids == current.item_ids
    assert s.text_projection().pending_item_ids is None


def test_renderer_failure_keeps_last_acknowledged_outfit():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    current = s.acknowledge_avatar(
        operation_id="change1", renderer_succeeded=False, assets_verified=False
    )
    assert current.revision == 1
    assert current.item_ids == ("shirt", "pants")
    assert s.text_projection().current_item_ids == ("shirt", "pants")


def test_failed_visual_change_can_explicitly_commit_as_text_fallback():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    s.acknowledge_avatar(
        operation_id="change1", renderer_succeeded=False, assets_verified=False
    )
    current = s.acknowledge_text_fallback(
        operation_id="change1", renderer_unavailable=True
    )
    assert current.revision == 2
    assert current.item_ids == ("lounge_top", "lounge_pants")
    assert current.presentation_mode is PresentationMode.TEXT_FALLBACK
    assert not current.avatar_visible
    assert current.avatar_synced_revision is None


def test_no_renderer_can_commit_pending_change_directly_to_text_fallback():
    s = state()
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    current = s.acknowledge_text_fallback(
        operation_id="change1", renderer_unavailable=True
    )
    assert current.revision == 2
    assert current.item_ids == ("lounge_top", "lounge_pants")
    assert s.text_projection().current_outfit_id == "lounge"


def test_avatar_must_resync_exact_fallback_revision_before_visible():
    s = state()
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    s.acknowledge_text_fallback(
        operation_id="change1", renderer_unavailable=True
    )
    with pytest.raises(WardrobeStateConflict):
        s.sync_avatar(
            expected_revision=1, renderer_succeeded=True, assets_verified=True
        )
    current = s.sync_avatar(
        expected_revision=2, renderer_succeeded=True, assets_verified=True
    )
    assert current.avatar_visible
    assert current.presentation_mode is PresentationMode.AVATAR_PRIMARY
    assert current.avatar_synced_revision == 2


def test_failed_resync_keeps_text_fallback_and_same_outfit():
    s = state()
    before = s.state
    current = s.sync_avatar(
        expected_revision=1, renderer_succeeded=False, assets_verified=False
    )
    assert current.item_ids == before.item_ids
    assert current.revision == before.revision
    assert current.presentation_mode is PresentationMode.TEXT_FALLBACK
    assert not current.avatar_visible


def test_renderer_loss_hides_avatar_without_changing_clothes():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    current = s.force_text_fallback(renderer_unavailable=True)
    assert current.revision == 1
    assert current.item_ids == ("shirt", "pants")
    assert not current.avatar_visible


def test_partial_or_uncovered_normal_state_is_denied():
    s = state()
    with pytest.raises(WardrobeStateDenied):
        s.propose(operation_id="bad", item_ids=("shirt",), expected_revision=1)


def test_stale_and_concurrent_changes_are_denied():
    s = state()
    with pytest.raises(WardrobeStateConflict):
        s.propose(
            operation_id="stale",
            item_ids=("lounge_top", "lounge_pants"),
            expected_revision=2,
        )
    s.propose(
        operation_id="one",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
    )
    with pytest.raises(WardrobeStateConflict):
        s.propose(
            operation_id="two",
            item_ids=("shirt", "pants", "jacket"),
            expected_revision=1,
        )


def test_text_fallback_requires_trusted_unavailable_fact():
    s = state()
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
    )
    with pytest.raises(WardrobeStateDenied):
        s.acknowledge_text_fallback(
            operation_id="change1", renderer_unavailable=False
        )
    assert s.state.revision == 1


def test_non_boolean_renderer_receipts_are_denied():
    s = state()
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
    )
    with pytest.raises(WardrobeStateDenied):
        s.acknowledge_avatar(
            operation_id="change1", renderer_succeeded=1, assets_verified=True
        )


def test_cancel_discards_uncommitted_change():
    s = state()
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
    )
    s.cancel(operation_id="change1")
    assert s.state.item_ids == ("shirt", "pants")
    assert s.pending is None
    with pytest.raises(WardrobeStateConflict):
        s.propose(
            operation_id="change1",
            item_ids=("lounge_top", "lounge_pants"),
            expected_revision=1,
        )


def test_snapshot_is_only_for_resolved_state():
    s = state()
    snap = s.snapshot()
    assert snap["revision"] == 1
    assert snap["presentation_mode"] == "text_fallback"
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
    )
    with pytest.raises(WardrobeStateConflict):
        s.snapshot()


def test_avatar_primary_initialization_requires_verified_visual_state():
    with pytest.raises(WardrobeStateDenied):
        state(PresentationMode.AVATAR_PRIMARY, False)


def test_failed_transition_is_visible_to_text_as_failed_but_not_current():
    s = state(PresentationMode.AVATAR_PRIMARY, True)
    s.propose(
        operation_id="change1",
        item_ids=("lounge_top", "lounge_pants"),
        expected_revision=1,
        outfit_id="lounge",
    )
    s.acknowledge_avatar(
        operation_id="change1", renderer_succeeded=False, assets_verified=False
    )
    projection = s.text_projection()
    assert projection.current_item_ids == ("shirt", "pants")
    assert projection.pending_item_ids == ("lounge_top", "lounge_pants")
    assert projection.pending_status is TransitionStatus.RENDER_FAILED
    with pytest.raises(WardrobeStateConflict):
        s.propose(
            operation_id="change2",
            item_ids=("lounge_top", "lounge_pants"),
            expected_revision=1,
        )
