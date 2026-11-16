"""Remote Fleet naming transport adapter acceptance and falsification tests."""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.callsign_remote import REMOTE_SCHEMA
from sofia.platform.ops.callsign_remote_transport import (
    MAX_REPLY_BYTES,
    PinnedHttpsCallsignReadTransport,
    REMOTE_CALLSIGN_READ_PATH,
    RemoteCallsignTransportAdapter,
    RemoteCallsignTransportError,
)
from sofia.platform.ops.callsigns import SCHEMA
from sofia.platform.distributed.model import (
    DistributedNode, NodeEnrollment,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
AUTH = str(uuid4())
PLATFORM = str(uuid4())


def _fixture():
    key = Ed25519PrivateKey.generate()
    der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, der, sha256(der).hexdigest()


def _signed_reply(
    key: Ed25519PrivateKey,
    nonce: str,
    *,
    revision: int = 4,
    name: str = "Artemis",
    issued_at: datetime = NOW,
    expires_at: datetime | None = None,
) -> bytes:
    signed = {
        "schema": REMOTE_SCHEMA,
        "authority_id": AUTH,
        "platform_id": PLATFORM,
        "nonce": nonce,
        "issued_at": issued_at.isoformat(),
        "expires_at": (expires_at or (NOW + timedelta(seconds=20))).isoformat(),
        "snapshot": {
            "schema": SCHEMA,
            "authority_id": AUTH,
            "platform_id": PLATFORM,
            "revision": revision,
            "name": name,
            "display": name,
            "registered": True,
            "locked": False,
            "core_id": None,
            "core_generation": None,
            "attachment_revision": 0,
            "status": "VERIFIED",
        },
    }
    encoded = json.dumps(
        signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()
    signed["signature_b64"] = b64encode(
        key.sign(b"aegis.fleet.callsign.remote-read.v1\0" + encoded)
    ).decode()
    return json.dumps(signed, separators=(",", ":")).encode()


class FakeAuthenticatedTransport:
    """Stand-in for an existing pinned/authenticated Fleet request channel."""

    def __init__(self, key: Ed25519PrivateKey) -> None:
        self.key = key
        self.mode = "ok"
        self.last_raw: bytes | None = None
        self.calls: list[tuple[bytes, float]] = []

    def request(self, body: bytes, *, timeout_seconds: float) -> bytes:
        self.calls.append((body, timeout_seconds))
        request = json.loads(body.decode("utf-8"))
        nonce = request["nonce"]
        if self.mode == "offline":
            raise ConnectionError("authenticated link disconnected")
        if self.mode == "oversized":
            return b"{" + b"x" * (MAX_REPLY_BYTES + 1) + b"}"
        if self.mode == "replay":
            assert self.last_raw is not None
            return self.last_raw
        if self.mode == "stale":
            raw = _signed_reply(
                self.key, nonce,
                issued_at=NOW - timedelta(minutes=2),
                expires_at=NOW - timedelta(minutes=1),
            )
        elif self.mode == "rollback":
            raw = _signed_reply(self.key, nonce, revision=3)
        elif self.mode == "equivocation":
            raw = _signed_reply(self.key, nonce, revision=4, name="Venus")
        else:
            raw = _signed_reply(self.key, nonce)
        self.last_raw = raw
        return raw


def _adapter(key, der, pin, transport, **overrides):
    values = {
        "authority_id": AUTH,
        "platform_id": PLATFORM,
        "authority_public_key_der": der,
        "expected_key_sha256": pin,
        "transport": transport,
        "clock": lambda: NOW + timedelta(seconds=1),
    }
    values.update(overrides)
    return RemoteCallsignTransportAdapter(**values)


def test_pinned_signed_projection_is_verified_exactly():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    adapter = _adapter(key, der, pin, transport)

    result = adapter.display()
    assert result["status"] == "VERIFIED"
    assert result["name"] == "Artemis"
    assert result["revision"] == 4
    assert result["authority_id"] == AUTH
    assert result["platform_id"] == PLATFORM
    assert transport.calls and transport.calls[0][1] > 0


def test_wrong_pin_der_identity_or_key_type_is_refused_at_construction():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    with pytest.raises(ValueError, match="SHA-256"):
        _adapter(key, der, "0" * 64, transport)
    with pytest.raises(ValueError, match="DER"):
        _adapter(key, der, sha256(b"not-der").hexdigest(), transport)
    with pytest.raises(ValueError, match="canonical"):
        _adapter(key, der, pin, transport, authority_id="NOT-A-UUID")

    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

    x_der = X25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(ValueError, match="Ed25519"):
        _adapter(key, x_der, sha256(x_der).hexdigest(), transport)


@pytest.mark.parametrize("mode", ["replay", "stale", "rollback"])
def test_replay_stale_and_rollback_replies_never_replace_verified_cache(mode):
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    adapter = _adapter(key, der, pin, transport)

    verified = adapter.display()
    assert verified["status"] == "VERIFIED"
    assert verified["revision"] == 4

    transport.mode = mode
    refused = adapter.display()
    assert refused["status"] == "CACHED"
    assert refused["revision"] == 4
    assert refused["name"] == "Artemis"


def test_conflicting_signed_snapshot_at_one_revision_is_not_a_refresh():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    adapter = _adapter(key, der, pin, transport)

    assert adapter.display()["name"] == "Artemis"
    transport.mode = "equivocation"
    refused = adapter.display()
    assert refused["status"] == "CACHED"
    assert refused["name"] == "Artemis"
    assert refused["revision"] == 4


def test_disconnect_reports_unconfirmed_then_cached_without_false_freshness():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    transport.mode = "offline"
    adapter = _adapter(key, der, pin, transport)

    assert adapter.display()["status"] == "UNCONFIRMED"
    assert adapter.display()["revision"] is None

    transport.mode = "ok"
    verified = adapter.display()
    assert verified["status"] == "VERIFIED"

    transport.mode = "offline"
    cached = adapter.display()
    assert cached["status"] == "CACHED"
    assert cached["name"] == "Artemis"
    assert cached["revision"] == 4


def test_request_nonce_replay_and_oversized_reply_are_rejected():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    adapter = _adapter(key, der, pin, transport)
    request = {
        "schema": REMOTE_SCHEMA,
        "authority_id": AUTH,
        "platform_id": PLATFORM,
        "nonce": "a" * 32,
    }
    assert adapter.exchange(request)["schema"] == REMOTE_SCHEMA
    with pytest.raises(RemoteCallsignTransportError, match="nonce"):
        adapter.exchange(request)

    transport.mode = "oversized"
    with pytest.raises(RemoteCallsignTransportError, match="size bound"):
        adapter.exchange(
            {**request, "nonce": "b" * 32}
        )


def test_request_size_and_target_are_bounded():
    key, der, pin = _fixture()
    transport = FakeAuthenticatedTransport(key)
    adapter = _adapter(key, der, pin, transport)
    with pytest.raises(RemoteCallsignTransportError, match="target"):
        adapter.exchange({
            "schema": REMOTE_SCHEMA,
            "authority_id": str(uuid4()),
            "platform_id": PLATFORM,
            "nonce": "a" * 32,
        })
    with pytest.raises(RemoteCallsignTransportError, match="fields"):
        adapter.exchange({
            "schema": REMOTE_SCHEMA,
            "authority_id": AUTH,
            "platform_id": PLATFORM,
            "nonce": "a" * 32,
            "extra": "x",
        })


class FakePinnedJsonTransport:
    """Stand-in for PinnedHttpsRemoteTransport's authenticated JSON exchange."""

    def __init__(self, key: Ed25519PrivateKey) -> None:
        self.key = key
        self.mode = "ok"
        self.calls: list[tuple[object, str, str, dict]] = []

    def request_json(self, enrollment, method, path, payload=None):
        self.calls.append((enrollment, method, path, dict(payload or {})))
        if self.mode == "offline":
            raise RuntimeError("pinned mTLS link disconnected")
        if self.mode == "oversized":
            return {
                "schema": REMOTE_SCHEMA,
                "padding": "x" * (MAX_REPLY_BYTES + 1),
            }
        nonce = payload["nonce"]
        revision = 3 if self.mode == "rollback" else 4
        return json.loads(
            _signed_reply(self.key, nonce, revision=revision).decode()
        )


def _enrollment():
    return NodeEnrollment(
        DistributedNode(uuid4(), "Artemis"), "a" * 64, NOW, "Sparks",
    )


def _production_transport(key, *, path=REMOTE_CALLSIGN_READ_PATH):
    pinned = FakePinnedJsonTransport(key)
    transport = PinnedHttpsCallsignReadTransport(
        transport=pinned, enrollment=_enrollment(),
        path=path, timeout_seconds=10.0,
    )
    return pinned, transport


def _naming_request() -> bytes:
    return json.dumps({
        "schema": REMOTE_SCHEMA,
        "authority_id": AUTH,
        "platform_id": PLATFORM,
        "nonce": "a" * 32,
    }, separators=(",", ":")).encode("utf-8")


def test_pinned_mtls_adapter_posts_to_the_remote_read_path():
    key, der, pin = _fixture()
    pinned, transport = _production_transport(key)
    adapter = _adapter(key, der, pin, transport)

    result = adapter.display()

    assert result["status"] == "VERIFIED"
    assert result["name"] == "Artemis"
    assert len(pinned.calls) == 1
    _enrollment_seen, method, path, payload = pinned.calls[0]
    assert method == "POST"
    assert path == REMOTE_CALLSIGN_READ_PATH
    assert payload["schema"] == REMOTE_SCHEMA
    assert payload["authority_id"] == AUTH
    assert payload["platform_id"] == PLATFORM


def test_pinned_mtls_adapter_reports_cached_then_unconfirmed_on_disconnect():
    key, der, pin = _fixture()
    pinned, transport = _production_transport(key)
    adapter = _adapter(key, der, pin, transport)

    assert adapter.display()["status"] == "VERIFIED"
    pinned.mode = "offline"
    assert adapter.display()["status"] == "CACHED"
    assert adapter.display()["revision"] == 4

    offline_key, offline_der, offline_pin = _fixture()
    offline_pinned, offline_transport = _production_transport(offline_key)
    offline_pinned.mode = "offline"
    offline_adapter = _adapter(
        offline_key, offline_der, offline_pin, offline_transport,
    )
    assert offline_adapter.display()["status"] == "UNCONFIRMED"
    assert offline_adapter.display()["revision"] is None


def test_pinned_mtls_adapter_rejects_rollback_replies():
    key, der, pin = _fixture()
    pinned, transport = _production_transport(key)
    adapter = _adapter(key, der, pin, transport)

    assert adapter.display()["revision"] == 4
    pinned.mode = "rollback"
    assert adapter.display()["status"] == "CACHED"
    assert adapter.display()["revision"] == 4


def test_pinned_mtls_adapter_bounds_request_reply_and_timeout():
    key, _der, _pin = _fixture()
    pinned, transport = _production_transport(key)

    with pytest.raises(RemoteCallsignTransportError, match="timeout"):
        transport.request(_naming_request(), timeout_seconds=999)
    with pytest.raises(RemoteCallsignTransportError, match="JSON"):
        transport.request(b"not-json", timeout_seconds=10)
    with pytest.raises(RemoteCallsignTransportError, match="bytes"):
        transport.request(b"", timeout_seconds=10)
    with pytest.raises(RemoteCallsignTransportError, match="size bound"):
        transport.request(
            b"{" + b"x" * (MAX_REPLY_BYTES + 1) + b"}",
            timeout_seconds=10,
        )

    pinned.mode = "oversized"
    with pytest.raises(RemoteCallsignTransportError, match="size bound"):
        transport.request(_naming_request(), timeout_seconds=10)


def test_pinned_mtls_adapter_requires_exact_enrollment_and_transport():
    key, _der, _pin = _fixture()
    pinned = FakePinnedJsonTransport(key)
    with pytest.raises(TypeError, match="NodeEnrollment"):
        PinnedHttpsCallsignReadTransport(
            transport=pinned, enrollment=object(),
        )
    with pytest.raises(TypeError, match="JSON transport"):
        PinnedHttpsCallsignReadTransport(
            transport=object(), enrollment=_enrollment(),
        )
    with pytest.raises(ValueError, match="path"):
        PinnedHttpsCallsignReadTransport(
            transport=pinned, enrollment=_enrollment(), path="relative",
        )
