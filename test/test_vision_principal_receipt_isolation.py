"""Deferred regression: screen receipts are scoped to one principal and audience.

Uses local synthetic frame bytes and a canonical test database, not real OS
capture. No host, Windows picker, PipeWire or vision model invoked.
"""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import sqlite3

import pytest

from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.vision.journeys import (
    ScreenJourney, ScreenJourneyReceiptStore,
    propose_owner_screen_journey, accept_actual_picked_frame,
    compare_two_approved_observations,
)

pytestmark = pytest.mark.pkg_interact
NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)


def _evidence(principal="person:sparks", audience="local:text", at=NOW):
    request = propose_owner_screen_journey(
        journey=ScreenJourney.SHOW_CHANGES,
        principal_id=principal, audience_id=audience, device_id="venus",
        target_id="picked-example-window-id",
        purpose="test scoped historical receipts", at=at,
    )
    return accept_actual_picked_frame(
        request, pixel_bytes=b"synthetic frame fixture",
        actual_os_picker_selected_target_id=request.permit.target_id,
        confirmed_interactive_os_picker=True, at=at,
    )


def test_same_audience_does_not_disclose_another_principal_receipt(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ScreenJourneyReceiptStore(state)
    store.record(_evidence("person:sparks"))
    assert len(store.status(
        principal_id="person:sparks", audience_id="local:text",
    )["observations"]) == 1
    assert store.status(
        principal_id="person:other", audience_id="local:text",
    )["observations"] == ()
    assert store.status(
        principal_id="person:sparks", audience_id="discord:private",
    )["observations"] == ()
    for principal in ("", " ", None):
        with pytest.raises(ValueError, match="principal"):
            store.status(principal_id=principal, audience_id="local:text")


def test_cross_principal_frames_do_not_form_visual_change_claim():
    first = _evidence("person:sparks")
    second = _evidence("person:other", at=NOW + timedelta(seconds=1))
    with pytest.raises(PermissionError, match="same approved"):
        compare_two_approved_observations(first, second)


def test_legacy_audience_only_rows_are_not_assigned_an_owner(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE vision_observed_frame("
            "receipt_id TEXT PRIMARY KEY,permit_id TEXT NOT NULL,"
            "journey TEXT NOT NULL,audience_id TEXT NOT NULL,"
            "device_id TEXT NOT NULL,target_hash TEXT NOT NULL,"
            "digest_sha256 TEXT NOT NULL,observed_at TEXT NOT NULL,"
            "has_pixels INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO vision_observed_frame VALUES(?,?,?,?,?,?,?,?,0)",
            ("legacy", "old-permit", "show_me_what_changed", "local:text",
             "venus", "0" * 64, "1" * 64, NOW.isoformat()),
        )
    store = ScreenJourneyReceiptStore(state)
    assert store.status(
        principal_id="person:sparks", audience_id="local:text",
    )["observations"] == ()
    store.record(_evidence())
    visible = store.status(principal_id="person:sparks", audience_id="local:text")
    assert len(visible["observations"]) == 1
    with sqlite3.connect(state) as db:
        old_principal = db.execute(
            "SELECT principal_id FROM vision_observed_frame "
            "WHERE receipt_id='legacy'"
        ).fetchone()
    assert old_principal == ("",)


def test_snapshot_expires_exactly_at_its_deadline():
    request = propose_owner_screen_journey(
        journey=ScreenJourney.LOOK_AT_WINDOW,
        principal_id="person:sparks", audience_id="local:text",
        device_id="venus", target_id="picked-example-window-id",
        purpose="expiration-boundary test", at=NOW,
    )
    with pytest.raises(PermissionError, match="expired"):
        accept_actual_picked_frame(
            request, pixel_bytes=b"synthetic jpeg",
            actual_os_picker_selected_target_id=request.permit.target_id,
            confirmed_interactive_os_picker=True,
            at=request.permit.expires_at,
        )


def test_duplicate_frame_id_cannot_rebind_a_different_principal_or_device(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ScreenJourneyReceiptStore(state)
    original = _evidence()
    store.record(original)
    store.record(original)
    with pytest.raises(PermissionError, match="different source, scope"):
        store.record(replace(original, principal_id="person:other"))
    with pytest.raises(PermissionError, match="different source, scope"):
        store.record(replace(original, device_id="other-device"))
    assert store.status(
        principal_id="person:other", audience_id="local:text",
    )["observations"] == ()
    assert len(store.status(
        principal_id="person:sparks", audience_id="local:text",
    )["observations"]) == 1


def test_malformed_frame_receipt_cannot_be_promoted_to_observed_evidence():
    observation = _evidence()
    with pytest.raises(PermissionError, match="frame hash"):
        replace(
            observation,
            receipt=replace(observation.receipt, digest_sha256="bogus"),
        )
    with pytest.raises(PermissionError, match="frame hash"):
        replace(
            observation,
            observed_at=NOW + timedelta(seconds=1),
        )
