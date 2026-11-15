"""Production adapter from an authenticated request transport to naming reads.

This module does not implement TLS, enrollment, key exchange or any Fleet
write operation. The caller supplies an already authenticated, pinned request
transport (for example one built on the existing mTLS HTTPS transport). This
adapter adds the exact naming-read contract:

* canonical authority/platform identity binding;
* an Ed25519 authority key supplied as DER and pinned by SHA-256;
* bounded request and reply bytes;
* fresh, single-use request nonces;
* delegated signature, expiry, revision rollback and equivocation checks via
  :class:`~sofia.platform.ops.callsign_remote.RemoteCallsignReadClient`.

On a transport disconnect the client truthfully returns ``UNCONFIRMED`` when
nothing was ever confirmed or ``CACHED`` with the last verified projection.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Mapping, Protocol
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.ops.callsign_remote import (
    REMOTE_SCHEMA,
    RemoteCallsignReadClient,
)

MAX_REQUEST_BYTES = 4096
MAX_REPLY_BYTES = 8192
_MAX_SEEN_NONCES = 256

_UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_NONCE = re.compile(r"[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REQUEST_FIELDS = frozenset({"schema", "authority_id", "platform_id", "nonce"})


class RemoteCallsignTransportError(OSError):
    """The authenticated transport failed or violated a bounded contract."""


class AuthenticatedRequestTransport(Protocol):
    """Existing authenticated transport; TLS and peer identity are its job."""

    def request(self, body: bytes, *, timeout_seconds: float) -> bytes:
        ...


def _canonical_uuid(value: object, label: str) -> str:
    if not isinstance(value, str) or _UUID_TEXT.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase canonical UUID")
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError(f"{label} must be a lowercase canonical UUID")
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class RemoteCallsignTransportAdapter:
    """Adapt a caller-owned authenticated transport to naming reads."""

    def __init__(
        self,
        *,
        authority_id: str,
        platform_id: str,
        authority_public_key_der: bytes,
        expected_key_sha256: str,
        transport: AuthenticatedRequestTransport,
        clock=None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.authority_id = _canonical_uuid(authority_id, "authority_id")
        self.platform_id = _canonical_uuid(platform_id, "platform_id")
        if not isinstance(authority_public_key_der, bytes) or not 1 <= len(
            authority_public_key_der
        ) <= 512:
            raise ValueError("pinned authority key must be bounded DER bytes")
        if (
            not isinstance(expected_key_sha256, str)
            or _SHA256.fullmatch(expected_key_sha256) is None
        ):
            raise ValueError("pinned authority key SHA-256 must be lowercase")
        if sha256(authority_public_key_der).hexdigest() != expected_key_sha256:
            raise ValueError("pinned authority key DER does not match its SHA-256")
        try:
            key = serialization.load_der_public_key(authority_public_key_der)
        except (TypeError, ValueError) as exc:
            raise ValueError("pinned authority key is not valid DER") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("pinned authority key must be Ed25519")
        if not callable(getattr(transport, "request", None)):
            raise TypeError("an existing authenticated request transport is required")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.authority_public_key_der = authority_public_key_der
        self.expected_key_sha256 = expected_key_sha256
        self._transport = transport
        self._timeout = float(timeout_seconds)
        self._seen_nonces: list[str] = []
        self._seen_nonce_set: set[str] = set()
        self._client = RemoteCallsignReadClient(
            authority_id=self.authority_id,
            platform_id=self.platform_id,
            authority_public_key_der=self.authority_public_key_der,
            expected_key_sha256=self.expected_key_sha256,
            transport=self.exchange,
            clock=clock,
        )

    def _remember_nonce(self, nonce: str) -> None:
        if nonce in self._seen_nonce_set:
            raise RemoteCallsignTransportError(
                "remote naming request nonce was already used"
            )
        self._seen_nonce_set.add(nonce)
        self._seen_nonces.append(nonce)
        if len(self._seen_nonces) > _MAX_SEEN_NONCES:
            oldest = self._seen_nonces.pop(0)
            self._seen_nonce_set.discard(oldest)

    def exchange(self, request: Mapping[str, str]) -> Mapping[str, object]:
        """Perform one bounded, authenticated naming request/reply exchange."""
        if type(request) is not dict or set(request) != _REQUEST_FIELDS:
            raise RemoteCallsignTransportError(
                "remote naming request fields are not exact"
            )
        if (
            request["schema"] != REMOTE_SCHEMA
            or request["authority_id"] != self.authority_id
            or request["platform_id"] != self.platform_id
        ):
            raise RemoteCallsignTransportError(
                "remote naming request target identity mismatch"
            )
        nonce = request["nonce"]
        if not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None:
            raise RemoteCallsignTransportError(
                "remote naming request requires a fresh nonce"
            )
        self._remember_nonce(nonce)
        body = _canonical_json(dict(request))
        if len(body) > MAX_REQUEST_BYTES:
            raise RemoteCallsignTransportError(
                "remote naming request exceeds its size bound"
            )
        try:
            raw = self._transport.request(body, timeout_seconds=self._timeout)
        except (OSError, ConnectionError, TimeoutError) as exc:
            raise RemoteCallsignTransportError(
                "authenticated naming transport is unavailable"
            ) from exc
        except Exception as exc:
            raise RemoteCallsignTransportError(
                f"authenticated naming transport failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, (bytes, bytearray)):
            raise RemoteCallsignTransportError(
                "remote naming transport returned non-byte evidence"
            )
        if len(raw) > MAX_REPLY_BYTES:
            raise RemoteCallsignTransportError(
                "remote naming reply exceeds its size bound"
            )
        try:
            reply = json.loads(bytes(raw).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteCallsignTransportError(
                "remote naming reply is not valid JSON"
            ) from exc
        if type(reply) is not dict:
            raise RemoteCallsignTransportError(
                "remote naming reply must be an object"
            )
        return reply

    def __call__(self, request: Mapping[str, str]) -> Mapping[str, object]:
        return self.exchange(request)

    def display(self) -> dict[str, object]:
        """Return VERIFIED, CACHED or UNCONFIRMED naming evidence truthfully."""
        return self._client.display()


__all__ = [
    "AuthenticatedRequestTransport",
    "MAX_REPLY_BYTES",
    "MAX_REQUEST_BYTES",
    "RemoteCallsignTransportAdapter",
    "RemoteCallsignTransportError",
]
