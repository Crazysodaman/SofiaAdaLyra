"""Read-only signed Fleet naming response verification, without network authority.

A transport caller must supply separately enrolled, pinned mTLS connectivity.
A verified naming display is NOT an owner grant, Core attach permission, or
permission to rename. This module does not install endpoints or access hosts.
"""
from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import secrets
from typing import Callable, Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.ops.callsigns import SCHEMA, normalize_callsign

REMOTE_SCHEMA = "aegis.fleet.callsign.remote-read.v1"
_DOMAIN = b"aegis.fleet.callsign.remote-read.v1\x00"
_MAX_REPLY_BYTES = 8192
_MAX_TTL = timedelta(seconds=30)
_CLOCK_SKEW = timedelta(seconds=5)
_REPLY_FIELDS = frozenset({"schema", "authority_id", "platform_id", "nonce", "issued_at", "expires_at", "snapshot", "signature_b64"})
_SNAPSHOT_FIELDS = frozenset({"schema", "authority_id", "platform_id", "revision", "name", "display", "registered", "locked", "core_id", "core_generation", "attachment_revision", "status"})


class RemoteCallsignRejected(ValueError):
    """Remote naming data is not authenticated, current, or scoped."""


def _canonical_uuid(value: object) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise RemoteCallsignRejected("noncanonical identity")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise RemoteCallsignRejected("invalid identity") from exc
    if parsed.int == 0 or str(parsed) != value:
        raise RemoteCallsignRejected("noncanonical identity")
    return value


def _time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise RemoteCallsignRejected("invalid response time")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RemoteCallsignRejected("invalid response time") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise RemoteCallsignRejected("timezone-aware response time required")
    return moment.astimezone(timezone.utc)


def _snapshot(value: object, *, authority_id: str, platform_id: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != _SNAPSHOT_FIELDS:
        raise RemoteCallsignRejected("unexpected naming projection fields")
    if (value["schema"] != SCHEMA or value["status"] != "VERIFIED"
            or value["authority_id"] != authority_id or value["platform_id"] != platform_id):
        raise RemoteCallsignRejected("naming projection identity mismatch")
    for field in ("revision", "attachment_revision"):
        if type(value[field]) is not int or not 0 <= value[field] < 2**63:
            raise RemoteCallsignRejected("invalid naming revision")
    if type(value["registered"]) is not bool or type(value["locked"]) is not bool:
        raise RemoteCallsignRejected("invalid naming state")
    name = value["name"]
    if name is None:
        if value["display"] != "UNASSIGNED":
            raise RemoteCallsignRejected("unassigned display mismatch")
    else:
        try:
            display, _ = normalize_callsign(name)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RemoteCallsignRejected("invalid remote callsign") from exc
        if display != name or value["display"] != name or not value["registered"]:
            raise RemoteCallsignRejected("remote callsign display mismatch")
    if not value["registered"] and (name is not None or value["locked"]):
        raise RemoteCallsignRejected("unregistered naming state mismatch")
    core_id = value["core_id"]
    generation = value["core_generation"]
    if core_id is None:
        if generation is not None:
            raise RemoteCallsignRejected("Core generation without identity")
    elif (_canonical_uuid(core_id) != core_id or type(generation) is not int
          or not 1 <= generation < 2**63):
        raise RemoteCallsignRejected("invalid attached Core generation")
    return dict(value)


def verify_remote_callsign_reply(
    reply: Mapping[str, object], *, authority_id: str, platform_id: str,
    nonce: str, authority_public_key_der: bytes, expected_key_sha256: str,
    now: datetime,
) -> dict[str, object]:
    """Verify an exact signed, nonce-bound, short-lived snapshot from one authority.

    Only the *designated authority's* independently pinned public key is
    accepted. Transport authentication and admission remain Fleet-owned.
    """
    authority_id = _canonical_uuid(authority_id)
    platform_id = _canonical_uuid(platform_id)
    if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
        raise RemoteCallsignRejected("invalid request nonce")
    if (type(reply) is not dict or set(reply) != _REPLY_FIELDS or reply["schema"] != REMOTE_SCHEMA
            or reply["authority_id"] != authority_id or reply["platform_id"] != platform_id
            or reply["nonce"] != nonce):
        raise RemoteCallsignRejected("unmatched remote naming reply")
    if not isinstance(authority_public_key_der, bytes) or len(authority_public_key_der) > 512:
        raise RemoteCallsignRejected("invalid pinned authority key")
    if (not isinstance(expected_key_sha256, str) or len(expected_key_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_key_sha256)
            or sha256(authority_public_key_der).hexdigest() != expected_key_sha256):
        raise RemoteCallsignRejected("designated authority pin mismatch")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise RemoteCallsignRejected("trusted aware clock required")
    start, end = _time(reply["issued_at"]), _time(reply["expires_at"])
    now = now.astimezone(timezone.utc)
    if not timedelta(0) < end - start <= _MAX_TTL or now < start - _CLOCK_SKEW or now > end:
        raise RemoteCallsignRejected("remote naming evidence expired or not current")
    if type(reply["signature_b64"]) is not str or len(reply["signature_b64"]) > 128:
        raise RemoteCallsignRejected("invalid signature encoding")
    snapshot = _snapshot(reply["snapshot"], authority_id=authority_id, platform_id=platform_id)
    signed = {key: reply[key] for key in _REPLY_FIELDS if key != "signature_b64"}
    try:
        raw = json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > _MAX_REPLY_BYTES:
            raise RemoteCallsignRejected("remote naming evidence exceeds size bound")
        signature = b64decode(reply["signature_b64"], validate=True)
        key = serialization.load_der_public_key(authority_public_key_der)
        if not isinstance(key, Ed25519PublicKey) or len(signature) != 64:
            raise RemoteCallsignRejected("invalid authority proof")
        key.verify(signature, _DOMAIN + raw)
    except (TypeError, ValueError, InvalidSignature, UnicodeError) as exc:
        raise RemoteCallsignRejected("remote naming signature verification failed") from exc
    return snapshot


class RemoteCallsignReadClient:
    """Read-only remote projection; no Core activity or naming write methods."""

    def __init__(self, *, authority_id: str, platform_id: str,
                 authority_public_key_der: bytes, expected_key_sha256: str,
                 transport: Callable[[dict[str, str]], Mapping[str, object]],
                 clock: Callable[[], datetime] | None = None):
        self.authority_id = _canonical_uuid(authority_id)
        self.platform_id = _canonical_uuid(platform_id)
        self.authority_public_key_der = authority_public_key_der
        self.expected_key_sha256 = expected_key_sha256
        if not callable(transport):
            raise TypeError("authenticated Fleet read transport required")
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._cached: dict[str, object] | None = None

    def display(self) -> dict[str, object]:
        nonce = secrets.token_hex(16)
        request = {"schema": REMOTE_SCHEMA, "authority_id": self.authority_id,
                   "platform_id": self.platform_id, "nonce": nonce}
        try:
            result = verify_remote_callsign_reply(
                self._transport(request), authority_id=self.authority_id,
                platform_id=self.platform_id, nonce=nonce,
                authority_public_key_der=self.authority_public_key_der,
                expected_key_sha256=self.expected_key_sha256, now=self._clock(),
            )
            if self._cached is not None:
                if result["revision"] < self._cached["revision"]:
                    raise RemoteCallsignRejected("remote naming revision rollback")
                # An authority revision is a durable state witness. Two distinct
                # signed projections at one revision are equivocation, NOT a
                # harmless refresh. Preserve the last confirmed display.
                if (result["revision"] == self._cached["revision"]
                        and result != self._cached):
                    raise RemoteCallsignRejected("conflicting signed naming revision")
            self._cached = result
            return dict(result)
        except (RemoteCallsignRejected, OSError, ConnectionError, TimeoutError):
            if self._cached is not None:
                return {**self._cached, "status": "CACHED"}
            return {"schema": SCHEMA, "authority_id": self.authority_id,
                    "platform_id": self.platform_id, "name": None, "display": "UNASSIGNED",
                    "revision": None, "status": "UNCONFIRMED"}
