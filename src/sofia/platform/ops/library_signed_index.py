"""D028-00 independent signed Library catalog-index verification.

The sender's mTLS identity is transport evidence, NOT publisher authority.
The independently configured trusted Ed25519 public key is supplied by the
canonical B1/owner trust store; never accept a key or key ID from network data
as the trust root. This module does not sign, enroll, download, install,
mutate SAFE, or start an endpoint.

Wire schema is an internal candidate until D028-00 A/B/C/D/E contract freeze.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from base64 import b64decode
from binascii import Error as Base64Error
import json
import re
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "aegis.library.publisher-index.v1"
_DOMAIN = b"aegis.library.publisher-index.v1\x00"
_MAX_BYTES = 65536
_MAX_TTL = timedelta(minutes=5)
_CLOCK_SKEW = timedelta(seconds=5)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ENVELOPE = frozenset({
    "schema", "publisher_key_sha256", "source_platform_id",
    "target_platform_id", "catalog_revision", "catalog_generation",
    "issued_at", "expires_at", "catalog", "signature_b64",
})
_CATALOG = frozenset({
    "catalog_revision", "catalog_generation", "catalog_fresh_until",
    "target_platform_id", "source", "page", "items",
})


class SignedLibraryIndexRejected(PermissionError):
    """Unsigned, stale, malformed or revoked publisher index cannot be used."""


@dataclass(frozen=True, slots=True)
class VerifiedLibraryIndex:
    catalog: dict
    signed_index_sha256: str
    catalog_sha256: str
    publisher_key_sha256: str
    source_platform_id: str
    target_platform_id: str
    catalog_revision: int
    catalog_generation: int
    expires_at: datetime

    def matches(self, candidate: object) -> bool:
        """Equality assertion for a previously independently verified index."""
        if type(candidate) is not dict:
            return False
        try:
            encoded = json.dumps(
                candidate, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError):
            return False
        return sha256(encoded).hexdigest() == self.catalog_sha256


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise SignedLibraryIndexRejected("duplicate signed index property")
        out[key] = value
    return out


def _utc(value: object) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise SignedLibraryIndexRejected("bounded signed index timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SignedLibraryIndexRejected("malformed signed index timestamp") from exc
    if result.utcoffset() is None:
        raise SignedLibraryIndexRejected("timezone-aware signed index required")
    return result.astimezone(timezone.utc)


def verify_signed_library_index(
    raw: bytes, *,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    expected_source_platform_id: str,
    expected_target_platform_id: str,
    expected_catalog_generation: int,
    minimum_catalog_revision: int,
    now: datetime,
    publisher_key_current: Callable[[str], bool],
) -> VerifiedLibraryIndex:
    """Verify exact signed bytes against an independently pinned publisher key.

    This verifies publisher index signature and freshness only. The canonical
    A broker must ALSO check current host enrollment, target binding, SAFE/STOP,
    catalog licenses and source authorization before any transfer or install.
    """
    if type(raw) is not bytes or not 1 <= len(raw) <= _MAX_BYTES:
        raise SignedLibraryIndexRejected("bounded signed index bytes required")
    if type(trusted_publisher_public_key) is not bytes or len(trusted_publisher_public_key) != 32:
        raise SignedLibraryIndexRejected("independent 32-byte Ed25519 root required")
    if (type(expected_publisher_key_sha256) is not str
            or _SHA.fullmatch(expected_publisher_key_sha256) is None
            or sha256(trusted_publisher_public_key).hexdigest() != expected_publisher_key_sha256):
        raise SignedLibraryIndexRejected("independent trusted publisher root differs")
    if (type(expected_source_platform_id) is not str
            or not expected_source_platform_id or len(expected_source_platform_id) > 160
            or type(expected_target_platform_id) is not str
            or not expected_target_platform_id or len(expected_target_platform_id) > 160):
        raise SignedLibraryIndexRejected("explicit enrolled source and recipient required")
    for number in (expected_catalog_generation, minimum_catalog_revision):
        if type(number) is not int or not 1 <= number <= 2**53 - 1:
            raise SignedLibraryIndexRejected("current bounded catalog epoch required")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise SignedLibraryIndexRejected("trusted current clock required")
    if not callable(publisher_key_current) or publisher_key_current(expected_publisher_key_sha256) is not True:
        raise SignedLibraryIndexRejected("publisher root revoked or unavailable")
    try:
        envelope = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                SignedLibraryIndexRejected("nonfinite signed index number")
            ),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SignedLibraryIndexRejected("malformed signed catalog bytes") from exc
    if (type(envelope) is not dict or set(envelope) != _ENVELOPE
            or envelope["schema"] != SCHEMA):
        raise SignedLibraryIndexRejected("unknown signed catalog envelope")
    if (envelope["publisher_key_sha256"] != expected_publisher_key_sha256
            or envelope["source_platform_id"] != expected_source_platform_id
            or envelope["target_platform_id"] != expected_target_platform_id
            or type(envelope["catalog_revision"]) is not int
            or envelope["catalog_revision"] < minimum_catalog_revision
            or type(envelope["catalog_generation"]) is not int
            or envelope["catalog_generation"] != expected_catalog_generation):
        raise SignedLibraryIndexRejected("publisher, source, recipient or catalog epoch mismatch")
    issued, expires = _utc(envelope["issued_at"]), _utc(envelope["expires_at"])
    moment = now.astimezone(timezone.utc)
    if (issued > moment + _CLOCK_SKEW or expires <= moment
            or expires <= issued or expires - issued > _MAX_TTL):
        raise SignedLibraryIndexRejected("stale, future or unbounded signed index")
    catalog = envelope["catalog"]
    if (type(catalog) is not dict or set(catalog) != _CATALOG
            or type(catalog["catalog_revision"]) is not int
            or catalog["catalog_revision"] != envelope["catalog_revision"]
            or type(catalog["catalog_generation"]) is not int
            or catalog["catalog_generation"] != envelope["catalog_generation"]
            or catalog["target_platform_id"] != envelope["target_platform_id"]
            or _utc(catalog["catalog_fresh_until"]) > expires):
        raise SignedLibraryIndexRejected("catalog content differs from signed scope")
    if (type(catalog["items"]) is not list or len(catalog["items"]) > 128
            or type(catalog["source"]) is not dict or type(catalog["page"]) is not dict):
        raise SignedLibraryIndexRejected("unbounded signed catalog projection")

    signature_text = envelope["signature_b64"]
    if type(signature_text) is not str or len(signature_text) > 128:
        raise SignedLibraryIndexRejected("bounded detached publisher signature required")
    try:
        signature = b64decode(signature_text, validate=True)
    except (ValueError, Base64Error) as exc:
        raise SignedLibraryIndexRejected("invalid detached publisher signature") from exc
    if len(signature) != 64:
        raise SignedLibraryIndexRejected("Ed25519 detached signature length invalid")
    signed = {key: value for key, value in envelope.items() if key != "signature_b64"}
    canonical = json.dumps(
        signed, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    try:
        Ed25519PublicKey.from_public_bytes(trusted_publisher_public_key).verify(
            signature, _DOMAIN + canonical,
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SignedLibraryIndexRejected("independent publisher signature verification failed") from exc
    if publisher_key_current(expected_publisher_key_sha256) is not True:
        raise SignedLibraryIndexRejected("publisher revoked during signature verification")
    return VerifiedLibraryIndex(
        catalog=catalog, signed_index_sha256=sha256(raw).hexdigest(),
        catalog_sha256=sha256(json.dumps(
            catalog, sort_keys=True, separators=(\",\", \":\"),
            ensure_ascii=False, allow_nan=False,
        ).encode(\"utf-8\")).hexdigest(),
        publisher_key_sha256=expected_publisher_key_sha256,
        source_platform_id=expected_source_platform_id,
        target_platform_id=expected_target_platform_id,
        catalog_revision=envelope["catalog_revision"],
        catalog_generation=envelope["catalog_generation"],
        expires_at=expires,
    )
