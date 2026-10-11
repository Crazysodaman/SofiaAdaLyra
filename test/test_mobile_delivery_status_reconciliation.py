"""Deferred original-authority mobile send reconciliation contracts.

Tests query ONLY persisted canonical receipts. They never replay an
uncertain send, admit a request from another pairing epoch or bypass
the host private-chat policy.
"""
from hashlib import sha256

import pytest

from sofia.mobile.gateway import (
    MobileCredentialRevoked, MobileDeliveryConflict,
)
from test.test_mobile_gateway import _gateway


def _chat(gateway, bearer, *, text="A unique train-layout turn", mode=False,
          request_id="original-reconciliation-001"):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/chat",
        payload={
            "device_id": "android-owner", "private_mode": mode,
            "message": text, "request_id": request_id,
        },
    )


def _check(gateway, bearer, *, text="A unique train-layout turn",
           mode=False, request_id="original-reconciliation-001",
           device="android-owner"):
    return gateway.dispatch_authenticated(
        credential=bearer, operation="/v1/mobile/delivery/status",
        payload={
            "device_id": device, "private_mode": mode,
            "request_id": request_id,
            "content_sha256": sha256(text.strip().encode("utf-8")).hexdigest(),
        },
    )


def test_reconnect_reads_real_completion_without_calling_cognition_again(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    accepted = _chat(gateway, bearer)
    assert accepted["delivery_receipt"]["logical_status"] == "completed"
    before = len(app.conversation.calls)

    recovered = _check(gateway, bearer)
    assert recovered["status"] == "completed"
    assert recovered["result"] == accepted
    assert len(app.conversation.calls) == before


def test_status_never_treats_missing_receipt_as_unsent_or_rerunnable(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    unknown = _check(gateway, bearer)
    assert unknown == {"status": "not_found"}
    assert app.conversation.calls == []


def test_reconciliation_never_discloses_cross_mode_device_or_epoch(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    _chat(gateway, bearer)
    other = gateway.credentials.enroll("android-other")

    assert _check(gateway, bearer, mode=True) == {"status": "not_found"}
    with pytest.raises(PermissionError):
        _check(gateway, other)
    assert _check(gateway, other, device="android-other") == {
        "status": "not_found"
    }

    renewed = gateway.credentials.enroll("android-owner", rotate=True)
    with pytest.raises(MobileCredentialRevoked):
        _check(gateway, bearer)
    assert _check(gateway, renewed) == {"status": "not_found"}


def test_status_rejects_same_request_id_with_different_original_bytes(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    _chat(gateway, bearer)
    with pytest.raises(MobileDeliveryConflict):
        _check(gateway, bearer, text="different payload")


def test_failed_original_inference_remains_uncertain_and_never_reruns(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    def fail(*args, **kwargs):
        app.conversation.calls.append(("attempt",))
        raise OSError("Venus remote GPU unavailable")
    app.conversation.respond = fail

    with pytest.raises(OSError):
        _chat(gateway, bearer)
    assert _check(gateway, bearer) == {"status": "uncertain"}
    assert len(app.conversation.calls) == 1


def test_private_receipt_requires_current_host_private_chat_approval(tmp_path):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    _chat(gateway, bearer, mode=True)
    assert _check(gateway, bearer, mode=True)["status"] == "completed"
    gateway.permissions.set_private_adult_authority(
        private_chat=False, adult_chat=True, adult_avatar=True,
        adult_external_delivery=False,
    )
    with pytest.raises(PermissionError, match="private delivery"):
        _check(gateway, bearer, mode=True)


@pytest.mark.parametrize("bad", (
    {"request_id": ""}, {"request_id": "unsafe/../../filename"},
    {"content_sha256": "garbage"}, {"content_sha256": "G" * 64},
    {"private_mode": 1}, {"extra": "shadow authority"},
))
def test_delivery_status_rejects_malformed_or_overbroad_requests(tmp_path, bad):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    payload = {
        "device_id": "android-owner", "private_mode": False,
        "request_id": "original-reconciliation-001",
        "content_sha256": sha256(b"A unique train-layout turn").hexdigest(),
    }
    payload.update(bad)
    with pytest.raises((TypeError, ValueError)):
        gateway.dispatch_authenticated(
            credential=bearer, operation="/v1/mobile/delivery/status",
            payload=payload,
        )
    assert app.conversation.calls == []


@pytest.mark.parametrize("revoked", ("adult_chat", "adult_avatar"))
def test_revoked_adult_presentation_grants_block_completed_replay(
    tmp_path, revoked,
):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    saved = _chat(gateway, bearer, mode=True)
    assert saved["adult_chat_enabled"] is True
    assert saved["adult_avatar_enabled"] is True
    assert _check(gateway, bearer, mode=True)["status"] == "completed"
    prior_calls = len(app.conversation.calls)

    gateway.permissions.set_private_adult_authority(
        private_chat=True,
        adult_chat=revoked != "adult_chat",
        adult_avatar=revoked != "adult_avatar",
        adult_external_delivery=False,
    )
    with pytest.raises(PermissionError, match="current adult"):
        _check(gateway, bearer, mode=True)
    with pytest.raises(PermissionError, match="current adult"):
        _chat(gateway, bearer, mode=True)
    assert len(app.conversation.calls) == prior_calls

    # Revoking an egress grant does not erase or rewrite source evidence.
    gateway.permissions.set_private_adult_authority(
        private_chat=True, adult_chat=True, adult_avatar=True,
        adult_external_delivery=False,
    )
    restored = _check(gateway, bearer, mode=True)
    assert restored["status"] == "completed"
    assert restored["result"] == saved
    assert len(app.conversation.calls) == prior_calls


def test_standard_completed_recovery_does_not_require_unrelated_adult_grants(
    tmp_path,
):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    _chat(gateway, bearer, mode=False)
    gateway.permissions.set_private_adult_authority(
        private_chat=False, adult_chat=False, adult_avatar=False,
        adult_external_delivery=False,
    )
    assert _check(gateway, bearer, mode=False)["status"] == "completed"
