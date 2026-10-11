"""CA-4104 source generation isolation for operator-repaired phone identity.

Authored for the deferred regression campaign. Not executed.
"""
from contextlib import closing
import sqlite3

import pytest

from sofia.mobile.gateway import MobileDeliveryConflict
from test.test_mobile_main_history import _setup, _record


def test_repaired_device_does_not_inherit_previous_generation_sessions_or_main(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    try:
        old_token = gateway.credentials.enroll("android-owner")
        original = gateway._principal("android-owner", private_mode=False)
        assert gateway.credentials.active_generation("android-owner") == 1
        old = gateway._conversation("android-owner", private_mode=False)
        _record(
            source, social, gateway, private_mode=False,
            text="Only previous enrollment may read", number=1,
        )
        assert len(gateway.main_history(
            device_id="android-owner", private_mode=False,
        )["messages"]) == 1

        rotated = gateway.credentials.enroll("android-owner", rotate=True)
        assert gateway.credentials.authenticate(old_token) is None
        assert gateway.credentials.authenticate(rotated) == "android-owner"
        assert gateway.credentials.active_generation("android-owner") == 2

        new_principal = gateway._principal("android-owner", private_mode=False)
        assert original.audience_id != new_principal.audience_id
        assert new_principal.audience_id.endswith(":g2")
        latest = gateway._conversation("android-owner", private_mode=False)
        assert latest.session_id != old.session_id
        assert gateway.main_history(
            device_id="android-owner", private_mode=False,
        )["messages"] == []

        with closing(sqlite3.connect(path)) as db:
            rows = db.execute(
                "SELECT credential_generation,session_id FROM "
                "mobile_conversation_binding_v3 "
                "WHERE device_id='android-owner' AND presentation_mode='standard' "
                "ORDER BY credential_generation",
            ).fetchall()
        assert rows == [(1, old.session_id), (2, latest.session_id)]
        restarted = type(gateway)(app, state_path=path)
        assert restarted._conversation(
            "android-owner", private_mode=False,
        ).session_id == latest.session_id
    finally:
        source.close()


def test_revoke_returns_no_active_binding_generation(tmp_path):
    path, source, _, _, gateway = _setup(tmp_path)
    try:
        gateway.credentials.enroll("android-owner")
        assert gateway.credentials.active_generation("android-owner") == 1
        assert gateway.credentials.revoke("android-owner")
        assert gateway.credentials.active_generation("android-owner") is None
    finally:
        source.close()


def test_original_completed_request_receipt_cannot_be_replayed_after_repair(tmp_path):
    from test.test_mobile_gateway import _gateway
    app, gateway = _gateway(tmp_path)
    gateway.credentials.enroll("android-owner")
    args = {
        "device_id": "android-owner",
        "message": "A private message bound to generation one",
        "private_mode": False,
        "request_id": "request-stable-before-rotation",
    }
    gateway.chat(**args)
    gateway.credentials.enroll("android-owner", rotate=True)
    with pytest.raises(MobileDeliveryConflict):
        gateway.chat(**args)
    assert len(app.conversation.calls) == 1
