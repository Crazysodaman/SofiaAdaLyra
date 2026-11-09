"""D028-05 signed chunk-parent contract for bounded multi-GiB Library objects.

This is ONLY independent publisher metadata verification. mTLS is peer
authentication, not publisher trust. A canonical installed Platform supplies
an independently pinned publisher key and its current revocation decision.
A verified parent never authorizes an install, Core load, model use, GC,
or copying protected/restricted data. Transfer ranges must additionally pass
the existing per-chunk SAFE/STOP enrolled-peer gate.

The on-wire encoding is a versioned internal candidate until D028-00 freezes
the A/B/C/D/E common protocol. It neither creates a new signer nor advertises
a source/endpoint to any client.
"""
from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)

SCHEMA = "aegis.library.signed-chunk-parent.v1"
_DOMAIN = b"aegis.library.signed-chunk-parent.v1\x00"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_CHUNK_BYTES = 1024 * 1024
MAX_CHUNKS = 8192
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_BYTES = MAX_CHUNK_BYTES * MAX_CHUNKS
# The signed parent is immutable package metadata, unlike the short-lived
# signed catalog observation. Current publisher revocation and host grants are
# checked on EVERY chunk, so a transfer may safely resume over slow LAN.
MAX_TTL = timedelta(hours=24)
_FIELDS = frozenset({
    "schema", "publisher_key_sha256", "source_platform_id",
    "target_platform_id", "generation", "catalog_revision",
    "artifact_kind", "license_distribution", "data_class",
    "content_sha256", "size_bytes", "chunk_bytes", "chunk_sha256s",
    "issued_at", "expires_at", "signature_b64",
})


def _unique(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ChunkTransferRejected("duplicate signed parent property")
        row[key] = value
    return row


def _time(value: object) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ChunkTransferRejected("bounded signed parent timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError("timezone missing")
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ChunkTransferRejected("invalid signed parent timestamp") from exc


@dataclass(frozen=True, slots=True)
class VerifiedLargeParent:
    """Immutable parsed chunk layout; the instance alone is not a trust grant."""

    signed_manifest_sha256: str
    content_sha256: str
    publisher_key_sha256: str
    source_platform_id: str
    target_platform_id: str
    generation: int
    catalog_revision: int
    artifact_kind: str
    size_bytes: int
    chunk_bytes: int
    chunk_sha256s: tuple[str, ...]
    expires_at: datetime

    @property
    def is_large(self) -> bool:
        return self.size_bytes > 512 * 1024 * 1024

    def matches_transfer(self, transfer: PinnedChunkTransfer) -> bool:
        return (
            isinstance(transfer, PinnedChunkTransfer)
            and transfer.source_platform_id == self.source_platform_id
            and transfer.target_platform_id == self.target_platform_id
            and transfer.manifest_sha256 == self.signed_manifest_sha256
            and transfer.content_sha256 == self.content_sha256
            and transfer.generation == self.generation
            and transfer.catalog_revision == self.catalog_revision
            and transfer.artifact_kind == self.artifact_kind
            and transfer.size_bytes == self.size_bytes
            and transfer.license_distribution == "permitted"
            and transfer.data_class == "public"
        )

    def expected_chunk_sha256(self, offset: int, length: int) -> str:
        """Only complete signed parent chunk boundaries may be requested."""
        if (type(offset) is not int or type(length) is not int
                or not 0 <= offset < self.size_bytes
                or offset % self.chunk_bytes != 0):
            raise ChunkTransferRejected("chunk offset not aligned to signed parent")
        expected_length = min(self.chunk_bytes, self.size_bytes - offset)
        if length != expected_length:
            raise ChunkTransferRejected("chunk length differs from signed parent")
        index = offset // self.chunk_bytes
        if index >= len(self.chunk_sha256s):
            raise ChunkTransferRejected("signed parent chunk index out of bounds")
        return self.chunk_sha256s[index]


def verify_signed_large_parent(
    raw: bytes, *,
    transfer: PinnedChunkTransfer,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    publisher_key_current: Callable[[str], bool],
    now: datetime,
) -> VerifiedLargeParent:
    """Independently authenticate *complete signed bytes* as transfer manifest.

    Each chunk hash and the final whole-artifact hash is publisher-signed.
    An untrusted peer cannot supply its own key, manifest pin, chunk layout,
    distribution consent, RUN generation, or recipient identity.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("independently signed transfer required")
    if (type(raw) is not bytes or not 1 <= len(raw) <= MAX_MANIFEST_BYTES
            or sha256(raw).hexdigest() != transfer.manifest_sha256):
        raise ChunkTransferRejected("exact signed publisher parent manifest required")
    if (type(trusted_publisher_public_key) is not bytes
            or len(trusted_publisher_public_key) != 32
            or type(expected_publisher_key_sha256) is not str
            or SHA256.fullmatch(expected_publisher_key_sha256) is None
            or sha256(trusted_publisher_public_key).hexdigest()
            != expected_publisher_key_sha256):
        raise ChunkTransferRejected("independently pinned Ed25519 publisher root required")
    if (not callable(publisher_key_current)
            or publisher_key_current(expected_publisher_key_sha256) is not True):
        raise ChunkTransferRejected("current publisher signing root revoked")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ChunkTransferRejected("trusted aware verification clock required")
    try:
        doc = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ChunkTransferRejected("nonfinite parent manifest value")
            ),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ChunkTransferRejected("invalid signed parent manifest JSON") from exc
    if type(doc) is not dict or set(doc) != _FIELDS or doc["schema"] != SCHEMA:
        raise ChunkTransferRejected("unreviewed signed parent manifest envelope")
    if (doc["publisher_key_sha256"] != expected_publisher_key_sha256
            or doc["source_platform_id"] != transfer.source_platform_id
            or doc["target_platform_id"] != transfer.target_platform_id
            or type(doc["generation"]) is not int
            or doc["generation"] != transfer.generation
            or type(doc["catalog_revision"]) is not int
            or doc["catalog_revision"] != transfer.catalog_revision
            or doc["artifact_kind"] != transfer.artifact_kind
            or doc["license_distribution"] != "permitted"
            or doc["data_class"] != "public"
            or doc["content_sha256"] != transfer.content_sha256
            or type(doc["size_bytes"]) is not int
            or doc["size_bytes"] != transfer.size_bytes):
        raise ChunkTransferRejected("signed parent differs from selected trust and recipient")
    length = doc["chunk_bytes"]
    digests = doc["chunk_sha256s"]
    if (type(length) is not int or length != MAX_CHUNK_BYTES
            or type(digests) is not list
            or not 1 <= len(digests) <= MAX_CHUNKS
            or transfer.size_bytes > MAX_BYTES
            or len(digests) !=
            (transfer.size_bytes + MAX_CHUNK_BYTES - 1) // MAX_CHUNK_BYTES
            or any(type(digest) is not str or SHA256.fullmatch(digest) is None
                   for digest in digests)):
        raise ChunkTransferRejected("signed parent chunk count, size or digest invalid")
    issued, expires = _time(doc["issued_at"]), _time(doc["expires_at"])
    current = now.astimezone(timezone.utc)
    if (issued > current + timedelta(seconds=5)
            or expires <= current or expires <= issued
            or expires - issued > MAX_TTL):
        raise ChunkTransferRejected("signed parent expired, future or overlong")
    signature_text = doc["signature_b64"]
    if type(signature_text) is not str or len(signature_text) > 128:
        raise ChunkTransferRejected("bounded detached Ed25519 parent signature required")
    try:
        signature = b64decode(signature_text, validate=True)
    except (ValueError, Base64Error) as exc:
        raise ChunkTransferRejected("invalid parent signature encoding") from exc
    if len(signature) != 64:
        raise ChunkTransferRejected("signed parent requires 64-byte Ed25519 signature")
    unsigned = {key: value for key, value in doc.items() if key != "signature_b64"}
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    try:
        Ed25519PublicKey.from_public_bytes(trusted_publisher_public_key).verify(
            signature, _DOMAIN + canonical,
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise ChunkTransferRejected("independent signed parent signature invalid") from exc
    if publisher_key_current(expected_publisher_key_sha256) is not True:
        raise ChunkTransferRejected("publisher revoked during signed parent verification")
    return VerifiedLargeParent(
        signed_manifest_sha256=sha256(raw).hexdigest(),
        content_sha256=transfer.content_sha256,
        publisher_key_sha256=expected_publisher_key_sha256,
        source_platform_id=transfer.source_platform_id,
        target_platform_id=transfer.target_platform_id,
        generation=transfer.generation, catalog_revision=transfer.catalog_revision,
        artifact_kind=transfer.artifact_kind, size_bytes=transfer.size_bytes,
        chunk_bytes=length, chunk_sha256s=tuple(digests), expires_at=expires,
    )
