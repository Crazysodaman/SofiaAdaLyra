"""Deferred four OS-window privacy journeys, zero ambient screen access."""
from datetime import datetime,timedelta,timezone
import sqlite3
import pytest
from sofia.vision.journeys import (
    ScreenJourney,ScreenJourneyReceiptStore,
    propose_owner_screen_journey,journey_policy,
    accept_actual_picked_frame,compare_two_approved_observations,
)
pytestmark=pytest.mark.pkg_interact
NOW=datetime(2026,10,11,18,tzinfo=timezone.utc)


def request(mode=ScreenJourney.LOOK_AT_WINDOW,*,at=NOW):
    return propose_owner_screen_journey(
        journey=mode,principal_id="person:sparks",
        audience_id="local:text",device_id="venus-desktop",
        target_id="os-picker-window-guid:123",
        purpose="inspect only this approved example window",at=at,
    )


def test_four_owner_journeys_are_distinct_and_have_no_action_authority():
    assert set(ScreenJourney)=={
        ScreenJourney.LOOK_AT_WINDOW,ScreenJourney.SHOW_CHANGES,
        ScreenJourney.WATCH_ONE_APP,ScreenJourney.NAVIGATE_GUIDANCE,
    }
    for mode in ScreenJourney:
        p=journey_policy(mode)
        assert p.max_seconds<=300
        assert p.permits_mouse_keyboard is False
        assert p.permits_background_capture is False
        assert p.permits_unselected_windows is False
        assert p.permits_private_history_in_memory is False
        requested=request(mode)
        assert requested.os_picker_confirmed is False
        assert requested.actual_capture_available is False
        assert requested.permit.observation_kind==(
            "bounded_follow" if mode is ScreenJourney.WATCH_ONE_APP
            else "snapshot"
        )
    assert journey_policy(ScreenJourney.WATCH_ONE_APP).max_seconds==180


def test_owner_ui_request_without_actual_os_picker_never_produces_image_receipt():
    proposal=request()
    with pytest.raises(PermissionError,match="picker"):
        accept_actual_picked_frame(
            proposal,pixel_bytes=b"opaque_real_jpeg_fixture",at=NOW,
            actual_os_picker_selected_target_id=proposal.permit.target_id,
            confirmed_interactive_os_picker=False,
        )
    with pytest.raises(PermissionError,match="picker"):
        accept_actual_picked_frame(
            proposal,pixel_bytes=b"opaque_real_jpeg_fixture",at=NOW,
            actual_os_picker_selected_target_id="different-window-guid",
            confirmed_interactive_os_picker=True,
        )
    with pytest.raises(PermissionError,match="protected"):
        accept_actual_picked_frame(
            proposal,pixel_bytes=b"opaque_real_jpeg_fixture",at=NOW,
            actual_os_picker_selected_target_id=proposal.permit.target_id,
            confirmed_interactive_os_picker=True,
            protected_surface=True,
        )


def test_bounded_receipt_only_after_adapter_reports_correct_window_and_bytes(tmp_path):
    owner=request()
    evidence=accept_actual_picked_frame(
        owner,pixel_bytes=b"fake byte fixture standing in for actual captured bytes",
        at=NOW,
        actual_os_picker_selected_target_id=owner.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    assert evidence.receipt.actual_frame_available is True
    assert evidence.semantic_content_verified is False
    assert evidence.authorized_action is False
    assert evidence.pixel_content_persisted is False
    state=tmp_path/"sofia.db"
    store=ScreenJourneyReceiptStore(state)
    store.record(evidence)
    store.record(evidence)
    result=store.status(principal_id="person:sparks",audience_id="local:text")
    assert len(result["observations"])==1
    assert result["pixel_storage"] is False
    assert result["screen_control_authorized"] is False
    assert store.status(principal_id="person:sparks",audience_id="discord:private")["observations"]==()
    with sqlite3.connect(state) as db:
        rows=db.execute(
            "SELECT digest_sha256,target_hash,has_pixels FROM vision_observed_frame"
        ).fetchall()
    assert len(rows)==1
    assert len(rows[0][0])==64 and len(rows[0][1])==64 and rows[0][2]==0


def test_bounded_watch_can_store_multiple_digests_but_no_pixels(tmp_path):
    watch=request(ScreenJourney.WATCH_ONE_APP)
    first=accept_actual_picked_frame(
        watch,pixel_bytes=b"mock frame one",at=NOW,
        actual_os_picker_selected_target_id=watch.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    second=accept_actual_picked_frame(
        watch,pixel_bytes=b"mock frame two",at=NOW+timedelta(seconds=1),
        actual_os_picker_selected_target_id=watch.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    store=ScreenJourneyReceiptStore(tmp_path/"sofia.db")
    store.record(first)
    store.record(second)
    assert len(store.status(principal_id="person:sparks",audience_id="local:text")["observations"])==2
    with pytest.raises(PermissionError,match="expired"):
        accept_actual_picked_frame(
            watch,pixel_bytes=b"after session deadline",
            at=NOW+timedelta(seconds=181),
            actual_os_picker_selected_target_id=watch.permit.target_id,
            confirmed_interactive_os_picker=True,
        )


def test_changes_only_compare_same_approved_target_not_semantic_scene(tmp_path):
    before=request(ScreenJourney.SHOW_CHANGES,at=NOW)
    after=request(ScreenJourney.SHOW_CHANGES,at=NOW+timedelta(seconds=1))
    obs1=accept_actual_picked_frame(
        before,pixel_bytes=b"frame a",
        at=NOW,actual_os_picker_selected_target_id=before.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    obs2=accept_actual_picked_frame(
        after,pixel_bytes=b"frame b",
        at=NOW+timedelta(seconds=1),
        actual_os_picker_selected_target_id=after.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    compared=compare_two_approved_observations(obs1,obs2)
    assert compared.same_selected_window is True
    assert compared.pixel_digest_changed is True
    assert compared.semantic_change_observed is False
    assert compared.authorized_action is False
    different=request(ScreenJourney.LOOK_AT_WINDOW)
    other=accept_actual_picked_frame(
        different,pixel_bytes=b"different",
        at=NOW,actual_os_picker_selected_target_id=different.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    with pytest.raises(PermissionError,match="same approved"):
        compare_two_approved_observations(obs1,other)


def test_no_real_capture_bytes_means_no_screen_observation():
    owner=request()
    with pytest.raises(ValueError,match="frame"):
        accept_actual_picked_frame(
            owner,pixel_bytes=b"",at=NOW,
            actual_os_picker_selected_target_id=owner.permit.target_id,
            confirmed_interactive_os_picker=True,
        )
    with pytest.raises(ValueError,match="frame"):
        accept_actual_picked_frame(
            owner,pixel_bytes=b"x"*(64*1024*1024+1),at=NOW,
            actual_os_picker_selected_target_id=owner.permit.target_id,
            confirmed_interactive_os_picker=True,
        )
