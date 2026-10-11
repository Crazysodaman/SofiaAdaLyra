"""Deferred mobile notice transaction fences against credential rotation.

Only canonical synthetic SQLite and in-process fake gateway objects are used.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from test.test_mobile_gateway import _gateway


NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _claim(gateway, bearer):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/notifications/claim",
        payload={"device_id": "android-owner", "private_mode": False},
    )


def _ack(gateway, bearer, handle):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/notifications/ack",
        payload={"device_id": "android-owner", "notification_id": handle},
    )


def test_rotated_bearer_cannot_claim_notification_after_original_dispatch(
    tmp_path, monkeypatch,
):
    _app, gateway = _gateway(tmp_path)
    old_bearer = gateway.credentials.enroll("android-owner")
    gateway.notifications.enqueue(
        notification_id="fixture:notice-claim-1",
        title="Routine note", content="Bounded notice", created_at=NOW,
    )
    original = gateway.notifications.claim_next
    rotated = []

    def rotate_during_claim(**kwargs):
        rotated.append(gateway.credentials.enroll(
            "android-owner", rotate=True,
        ))
        return original(**kwargs)

    monkeypatch.setattr(gateway.notifications, "claim_next", rotate_during_claim)
    with pytest.raises(PermissionError, match="pairing changed before notification"):
        _claim(gateway, old_bearer)

    assert rotated
    with sqlite3.connect(gateway.state_path) as db:
        state = db.execute(
            "SELECT status FROM mobile_notification "
            "WHERE notification_id='fixture:notice-claim-1'"
        ).fetchone()
    assert state == ("queued",)


def test_rotated_bearer_cannot_acknowledge_notification_or_complete_outreach(
    tmp_path, monkeypatch,
):
    _app, gateway = _gateway(tmp_path)
    old_bearer = gateway.credentials.enroll("android-owner")
    gateway.notifications.enqueue(
        notification_id="fixture:notice-ack-1",
        title="Routine note", content="Bounded notice", created_at=NOW,
    )
    first = _claim(gateway, old_bearer)
    handle = first["notification"]["id"]
    original = gateway.notifications.acknowledge

    def rotate_during_ack(*args, **kwargs):
        gateway.credentials.enroll("android-owner", rotate=True)
        return original(*args, **kwargs)

    monkeypatch.setattr(gateway.notifications, "acknowledge", rotate_during_ack)
    with pytest.raises(PermissionError, match="pairing changed before notification"):
        _ack(gateway, old_bearer, handle)

    with sqlite3.connect(gateway.state_path) as db:
        status = db.execute(
            "SELECT status FROM mobile_notification "
            "WHERE notification_id='fixture:notice-ack-1'"
        ).fetchone()
    assert status == ("claimed",)


def test_stable_paired_notification_claim_and_ack_still_succeed(tmp_path):
    _app, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("android-owner")
    gateway.notifications.enqueue(
        notification_id="fixture:ordinary-notice",
        title="Ordinary note", content="No private data", created_at=NOW,
    )
    receipt = _claim(gateway, token)
    handle = receipt["notification"]["id"]
    assert _ack(gateway, token, handle) == {"acknowledged": True}
    with sqlite3.connect(gateway.state_path) as db:
        assert db.execute(
            "SELECT status FROM mobile_notification "
            "WHERE notification_id='fixture:ordinary-notice'"
        ).fetchone() == ("displayed",)


def test_new_pairing_cannot_ack_older_generation_claim_until_reclaimed(
    tmp_path,
):
    _app, gateway = _gateway(tmp_path)
    old_token = gateway.credentials.enroll("android-owner")
    gateway.notifications.enqueue(
        notification_id="fixture:old-generation-claim",
        title="Deferred note", content="Original delivery", created_at=NOW,
    )
    first = _claim(gateway, old_token)
    handle = first["notification"]["id"]
    fresh_token = gateway.credentials.enroll("android-owner", rotate=True)

    with pytest.raises(PermissionError, match="another pairing generation"):
        _ack(gateway, fresh_token, handle)
    with sqlite3.connect(gateway.state_path) as db:
        assert db.execute(
            "SELECT status,claimed_generation FROM mobile_notification "
            "WHERE notification_id='fixture:old-generation-claim'"
        ).fetchone() == ("claimed", 1)

    # The original lease can legitimately expire. The new bearer then
    # claims the same queued notice under its OWN enrolled generation.
    new_generation = gateway.credentials.active_generation("android-owner")
    fingerprint = gateway.credentials._digest(fresh_token)
    reclaimed = gateway.notifications.claim_next(
        device_id="android-owner",
        now=datetime.now(timezone.utc) + timedelta(minutes=6),
        generation=new_generation,
        credential_sha256=fingerprint,
    )
    assert reclaimed is not None
    assert reclaimed.notification_id == "fixture:old-generation-claim"
    assert _ack(gateway, fresh_token, handle) == {"acknowledged": True}
    with sqlite3.connect(gateway.state_path) as db:
        assert db.execute(
            "SELECT status,claimed_generation FROM mobile_notification "
            "WHERE notification_id='fixture:old-generation-claim'"
        ).fetchone() == ("displayed", 2)
