"""Deferred end-to-end canonical Main read cursor tests.

The server never accepts a phone's self-declared source audience.
No tests or CI run during V18 development coding.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from test.test_mobile_main_history import _setup, _allow_private_main, _record


def _canonical(path, source_id, sequence):
    with sqlite3.connect(path) as db:
        updated = db.execute(
            "UPDATE lifelong_thread_event SET canonical_sequence=?,"
            "turn_position=0 WHERE source_message_id=?",
            (sequence, source_id),
        )
        assert updated.rowcount == 1
        db.commit()


def _seen(gateway, bearer, *, mode=False, sequence=1, source_id="source-1"):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/main/seen",
        payload={
            "device_id": "android-owner", "private_mode": mode,
            "canonical_sequence": sequence, "turn_position": 0,
            "message_id": source_id,
        },
    )


def test_mobile_read_progress_is_durable_monotonic_and_audience_scoped(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    _allow_private_main(path)
    bearer = gateway.credentials.enroll("android-owner")
    try:
        for i in (1, 2, 3):
            _record(
                source, social, gateway, private_mode=False,
                text=f"Public message {i}", number=i,
            )
            _canonical(path, f"source-{i}", i)
        _record(
            source, social, gateway, private_mode=True,
            text="Private-only data", number=4,
        )
        _canonical(path, "source-4", 4)

        page = gateway.dispatch_authenticated(
            credential=bearer, operation="/v1/mobile/main/page",
            payload={
                "device_id": "android-owner", "private_mode": False,
                "before": None, "limit": 30,
            },
        )
        assert page["last_seen"] is None
        assert len(page["messages"]) == 3

        assert _seen(gateway, bearer, sequence=3, source_id="source-3")[
            "last_seen"
        ]["canonical_sequence"] == 3
        # Stale offline pages never regress read progress.
        assert _seen(gateway, bearer, sequence=1, source_id="source-1")[
            "last_seen"
        ]["canonical_sequence"] == 3
        with pytest.raises(PermissionError, match="audience"):
            _seen(gateway, bearer, sequence=4, source_id="source-4")
        assert gateway.main_history(
            device_id="android-owner", private_mode=False,
        )["last_seen"]["canonical_sequence"] == 3
        assert gateway.main_history(
            device_id="android-owner", private_mode=True,
        )["last_seen"] is None

        # The persistent marker survives gateway restart, but no trans-
        # audience session reuse or source message copy is needed.
        from sofia.mobile.gateway import MobileCompanionGateway
        restart = MobileCompanionGateway(app, state_path=path)
        assert restart.main_history(
            device_id="android-owner", private_mode=False,
        )["last_seen"]["canonical_sequence"] == 3
    finally:
        source.close()


def test_new_device_pairing_epoch_cannot_adopt_old_last_seen(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    first = gateway.credentials.enroll("android-owner")
    try:
        _record(
            source, social, gateway, private_mode=False,
            text="old generation", number=1,
        )
        _canonical(path, "source-1", 1)
        assert _seen(gateway, first)["acknowledged"]
        second = gateway.credentials.enroll("android-owner", rotate=True)
        assert gateway.credentials.authenticate(first) is None
        assert gateway.credentials.authenticate(second) == "android-owner"
        assert gateway.main_history(
            device_id="android-owner", private_mode=False,
        )["last_seen"] is None
        with pytest.raises(PermissionError):
            _seen(gateway, second)
    finally:
        source.close()


@pytest.mark.parametrize("bad", (
    {"canonical_sequence": 0}, {"canonical_sequence": True},
    {"turn_position": 2}, {"turn_position": False},
    {"message_id": ""}, {"message_id": "x" * 161},
))
def test_read_receipt_input_validation(tmp_path, bad):
    path, source, social, app, gateway = _setup(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    try:
        payload = {
            "device_id": "android-owner", "private_mode": False,
            "canonical_sequence": 1, "turn_position": 0,
            "message_id": "source-1",
        }
        payload.update(bad)
        with pytest.raises((TypeError, ValueError)):
            gateway.dispatch_authenticated(
                credential=bearer, operation="/v1/mobile/main/seen",
                payload=payload,
            )
    finally:
        source.close()
