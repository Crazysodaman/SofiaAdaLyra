"""No-effect remote Fleet naming proof tests, including falsification cases."""
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.callsign_remote import (
    REMOTE_SCHEMA, RemoteCallsignReadClient, RemoteCallsignRejected,
    verify_remote_callsign_reply,
)
from sofia.platform.ops.callsigns import SCHEMA

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
AUTH = str(uuid4())
PLATFORM = str(uuid4())


def _fixture():
    key = Ed25519PrivateKey.generate()
    der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, der, sha256(der).hexdigest()


def _reply(key, request_nonce, **changes):
    signed = {
        "schema": REMOTE_SCHEMA,
        "authority_id": AUTH,
        "platform_id": PLATFORM,
        "nonce": request_nonce,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(seconds=20)).isoformat(),
        "snapshot": {
            "schema": SCHEMA, "authority_id": AUTH, "platform_id": PLATFORM,
            "revision": 4, "name": "Artemis", "display": "Artemis",
            "registered": True, "locked": False, "core_id": None,
            "core_generation": None, "attachment_revision": 0, "status": "VERIFIED",
        },
    }
    signed.update(changes)
    encoded = json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    signed["signature_b64"] = b64encode(key.sign(b"aegis.fleet.callsign.remote-read.v1\0" + encoded)).decode()
    return signed


def _verify(reply, der, pin, nonce, **kwargs):
    return verify_remote_callsign_reply(
        reply, authority_id=AUTH, platform_id=PLATFORM, nonce=nonce,
        authority_public_key_der=der, expected_key_sha256=pin,
        now=kwargs.get("now", NOW + timedelta(seconds=1)),
    )


def test_pinned_signed_projection_is_verified_only_for_exact_nonce_and_target():
    key, der, pin = _fixture()
    nonce = "a" * 32
    result = _verify(_reply(key, nonce), der, pin, nonce)
    assert result["name"] == "Artemis" and result["revision"] == 4
    assert result["status"] == "VERIFIED"


@pytest.mark.parametrize("change", [
    {"authority_id": str(uuid4())}, {"platform_id": str(uuid4())},
    {"nonce": "b" * 32}, {"expires_at": (NOW + timedelta(minutes=2)).isoformat()},
    {"issued_at": (NOW + timedelta(minutes=2)).isoformat()},
])
def test_wrong_target_nonce_or_time_cannot_be_marked_verified(change):
    key, der, pin = _fixture()
    with pytest.raises(RemoteCallsignRejected):
        _verify(_reply(key, "a" * 32, **change), der, pin, "a" * 32)


def test_tampering_and_wrong_signer_fail_closed():
    key, der, pin = _fixture()
    attacker, other_der, other_pin = _fixture()
    reply = _reply(key, "a" * 32)
    reply["snapshot"]["name"] = "Stolen"
    with pytest.raises(RemoteCallsignRejected):
        _verify(reply, der, pin, "a" * 32)
    with pytest.raises(RemoteCallsignRejected):
        _verify(_reply(attacker, "a" * 32), der, pin, "a" * 32)
    with pytest.raises(RemoteCallsignRejected):
        _verify(_reply(key, "a" * 32), der, other_pin, "a" * 32)


@pytest.mark.parametrize("patch", [
    {"revision": True}, {"revision": -1}, {"locked": "false"},
    {"display": "different"}, {"status": "CACHED"},
    {"core_generation": 1}, {"registered": False},
    {"name": "x\x1b[31m"}, {"unexpected": "secret"},
])
def test_signed_but_invalid_projection_is_rejected(patch):
    key, der, pin = _fixture()
    base = _reply(key, "a" * 32)
    base["snapshot"].update(patch)
    with pytest.raises(RemoteCallsignRejected):
        _verify(_reply(key, "a" * 32, snapshot=base["snapshot"]), der, pin, "a" * 32)


def test_oversized_reply_and_signature_format_are_rejected():
    key, der, pin = _fixture()
    nonce = "a" * 32
    over = _reply(key, nonce, extra="x" * 9000)
    with pytest.raises(RemoteCallsignRejected):
        _verify(over, der, pin, nonce)
    bad = _reply(key, nonce)
    bad["signature_b64"] = "not-base64@"
    with pytest.raises(RemoteCallsignRejected):
        _verify(bad, der, pin, nonce)


def test_remote_client_displays_cached_or_unconfirmed_not_false_freshness():
    key, der, pin = _fixture()
    mode = ["offline"]
    def transport(req):
        if mode[0] == "offline":
            raise ConnectionError("disconnected")
        if mode[0] == "rollback":
            return _reply(key, req["nonce"], snapshot={
                **_reply(key, req["nonce"])["snapshot"], "revision": 3,
            })
        return _reply(key, req["nonce"])
    client = RemoteCallsignReadClient(
        authority_id=AUTH, platform_id=PLATFORM,
        authority_public_key_der=der, expected_key_sha256=pin,
        transport=transport, clock=lambda: NOW + timedelta(seconds=1),
    )
    first = client.display()
    assert first["status"] == "UNCONFIRMED" and first["revision"] is None
    mode[0] = "online"
    good = client.display()
    assert good["status"] == "VERIFIED" and good["revision"] == 4
    mode[0] = "rollback"
    stale = client.display()
    assert stale["status"] == "CACHED" and stale["revision"] == 4
    assert not hasattr(client, "core_rename")
