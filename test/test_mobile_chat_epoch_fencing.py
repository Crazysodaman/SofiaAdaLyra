"""Deferred mobile credential epoch fencing at chat claim and settlement.

All requests use canonical synthetic SQLite and the real gateway dispatch.
No live host, LLM, Android build or tests are run in this coding pass.
"""
import sqlite3

import pytest

from sofia.mobile.gateway import MobileCredentialRevoked
from test.test_mobile_gateway import _gateway


def _dispatch(gateway, bearer, *, request_id="mobile-race-001"):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/chat",
        payload={
            "device_id": "android-owner",
            "private_mode": False,
            "request_id": request_id,
            "message": "This must not cross pairing generations",
        },
    )


def test_old_bearer_cannot_admit_new_turn_after_rotation_between_checks(
    tmp_path, monkeypatch,
):
    app, gateway = _gateway(tmp_path)
    old_bearer = gateway.credentials.enroll("android-owner")
    original = gateway.chat
    rotated = []

    def rotate_before_admission(**kwargs):
        rotated.append(gateway.credentials.enroll(
            "android-owner", rotate=True,
        ))
        return original(**kwargs)

    monkeypatch.setattr(gateway, "chat", rotate_before_admission)
    with pytest.raises(MobileCredentialRevoked, match="turn admission"):
        _dispatch(gateway, old_bearer)
    assert rotated and gateway.credentials.authenticate(rotated[0]) == "android-owner"
    assert app.conversation.calls == []
    with sqlite3.connect(gateway.state_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM mobile_turn_receipt "
            "WHERE request_id='mobile-race-001'"
        ).fetchone()[0] == 0


def test_rotating_bearer_during_generation_returns_uncertain_not_completed(
    tmp_path, monkeypatch,
):
    app, gateway = _gateway(tmp_path)
    old_bearer = gateway.credentials.enroll("android-owner")
    original = app.conversation.respond
    rotated = []

    def rotate_during_cognition(*args, **kwargs):
        output = original(*args, **kwargs)
        rotated.append(gateway.credentials.enroll(
            "android-owner", rotate=True,
        ))
        return output

    monkeypatch.setattr(app.conversation, "respond", rotate_during_cognition)
    with pytest.raises(MobileCredentialRevoked, match="result settlement"):
        _dispatch(gateway, old_bearer, request_id="mobile-race-002")
    assert len(app.conversation.calls) == 1
    assert gateway.credentials.authenticate(old_bearer) is None
    with sqlite3.connect(gateway.state_path) as db:
        row = db.execute(
            "SELECT status,credential_generation,response_json "
            "FROM mobile_turn_receipt WHERE request_id='mobile-race-002'"
        ).fetchone()
    assert row == ("uncertain", 1, None)

    # The new bearer never inherits an old generation's response/cursor.
    from hashlib import sha256
    outcome = gateway.dispatch_authenticated(
        credential=rotated[0], operation="/v1/mobile/delivery/status",
        payload={
            "device_id": "android-owner", "private_mode": False,
            "request_id": "mobile-race-002",
            "content_sha256": sha256(
                b"This must not cross pairing generations"
            ).hexdigest(),
        },
    )
    assert outcome == {"status": "not_found"}


def test_same_live_bearer_completes_one_canonical_chat(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    result = _dispatch(gateway, bearer, request_id="mobile-race-003")
    assert result["delivery_receipt"]["logical_status"] == "completed"
    assert result["delivery_receipt"]["credential_generation"] == 1
    assert len(app.conversation.calls) == 1
