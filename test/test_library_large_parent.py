"""D028 signed parent verification and bounded multi-GiB layout regressions.

All keys are synthetic test-only. A >512 MiB logical manifest is exercised
without allocating a >512 MiB payload or operating an installed host.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_large_parent import (
    SCHEMA, _DOMAIN, MAX_CHUNK_BYTES, MAX_CHUNKS,
    verify_signed_large_parent,
)


def _signed_parent(
    *, huge: bool = False, data: bytes = b"public-tiny-test-package",
):
    now = datetime.now(timezone.utc)
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    if huge:
        size = 512 * 1024 * 1024 + 1
        hashes = [sha256(b"test-byte-chunk").hexdigest()] * 513
        # The following digest is synthetic metadata, NOT a claim that a real
        # parent object exists or that its stated hashes pass final verification.
        whole = "a" * 64
    else:
        size = len(data)
        hashes = [
            sha256(data[i:i + MAX_CHUNK_BYTES]).hexdigest()
            for i in range(0, size, MAX_CHUNK_BYTES)
        ]
        whole = sha256(data).hexdigest()
    doc = {
        "schema": SCHEMA,
        "publisher_key_sha256": sha256(public).hexdigest(),
        "source_platform_id": "primary-library",
        "target_platform_id": "enrolled-recipient",
        "generation": 7,
        "catalog_revision": 10,
        "artifact_kind": "asset",
        "license_distribution": "permitted",
        "data_class": "public",
        "content_sha256": whole,
        "size_bytes": size,
        "chunk_bytes": MAX_CHUNK_BYTES,
        "chunk_sha256s": hashes,
        "issued_at": (now - timedelta(seconds=5)).isoformat(),
        "expires_at": (now + timedelta(minutes=2)).isoformat(),
    }
    def sign(payload):
        canonical = json.dumps(
            payload, separators=(",", ":"), sort_keys=True,
            allow_nan=False, ensure_ascii=False,
        ).encode("utf-8")
        signature = signer.sign(_DOMAIN + canonical)
        return json.dumps(
            {**payload, "signature_b64": b64encode(signature).decode("ascii")},
            separators=(",", ":"), sort_keys=True, allow_nan=False,
            ensure_ascii=False,
        ).encode("utf-8")
    raw = sign(doc)
    transfer = PinnedChunkTransfer(
        source_platform_id=doc["source_platform_id"],
        target_platform_id=doc["target_platform_id"],
        content_sha256=whole, size_bytes=size, generation=7,
        manifest_sha256=sha256(raw).hexdigest(),
        catalog_revision=10, artifact_kind="asset",
        license_distribution="permitted", data_class="public",
    )
    kwargs = dict(
        transfer=transfer,
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        publisher_key_current=lambda _: True,
        now=now,
    )
    return doc, raw, transfer, kwargs, sign


def test_signed_logical_over_512_mib_parent_has_bounded_chunk_map():
    doc, raw, transfer, kwargs, sign = _signed_parent(huge=True)
    parent = verify_signed_large_parent(raw, **kwargs)
    assert parent.is_large is True
    assert len(parent.chunk_sha256s) == 513
    assert parent.size_bytes == 512 * 1024 * 1024 + 1
    assert parent.matches_transfer(transfer)
    assert parent.expected_chunk_sha256(512 * 1024 * 1024, 1) == doc["chunk_sha256s"][-1]
    with pytest.raises(ChunkTransferRejected, match="aligned"):
        parent.expected_chunk_sha256(2, 1)
    with pytest.raises(ChunkTransferRejected, match="length"):
        parent.expected_chunk_sha256(0, 1)
    with pytest.raises(ChunkTransferRejected, match="aligned"):
        parent.expected_chunk_sha256(-1, 1)


def test_signed_parent_rejects_tampered_chunk_hash_even_after_manifest_sha_update():
    doc, raw, transfer, kwargs, sign = _signed_parent()
    doc["chunk_sha256s"][0] = "f" * 64
    altered = json.loads(raw)
    altered["chunk_sha256s"][0] = "f" * 64
    candidate = json.dumps(
        altered, separators=(",", ":"), sort_keys=True,
    ).encode()
    changed_transfer = replace(transfer, manifest_sha256=sha256(candidate).hexdigest())
    with pytest.raises(ChunkTransferRejected, match="signature"):
        verify_signed_large_parent(candidate, **{**kwargs, "transfer": changed_transfer})


def test_signed_parent_rejects_changed_recipient_generation_and_catalog():
    doc, raw, transfer, kwargs, sign = _signed_parent()
    for field, changed in (
        ("target_platform_id", "other-recipient"),
        ("generation", 999),
        ("catalog_revision", 999),
        ("content_sha256", "e" * 64),
        ("license_distribution", "restricted"),
        ("data_class", "private"),
    ):
        altered = {**doc, field: changed}
        candidate = sign(altered)
        t = replace(transfer, manifest_sha256=sha256(candidate).hexdigest())
        with pytest.raises(ChunkTransferRejected, match="differs"):
            verify_signed_large_parent(candidate, **{**kwargs, "transfer": t})


def test_signed_parent_rejects_revocation_and_expiry():
    doc, raw, transfer, kwargs, sign = _signed_parent()
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        verify_signed_large_parent(
            raw, **{**kwargs, "publisher_key_current": lambda _: False},
        )
    with pytest.raises(ChunkTransferRejected, match="expired"):
        verify_signed_large_parent(
            raw, **{**kwargs, "now": kwargs["now"] + timedelta(minutes=3)},
        )


def test_signed_parent_rejects_unbounded_chunk_map():
    doc, raw, transfer, kwargs, sign = _signed_parent()
    altered = {**doc, "chunk_sha256s": ["b" * 64] * (MAX_CHUNKS + 1)}
    candidate = sign(altered)
    t = replace(transfer, manifest_sha256=sha256(candidate).hexdigest())
    with pytest.raises(ChunkTransferRejected, match="chunk count"):
        verify_signed_large_parent(candidate, **{**kwargs, "transfer": t})


def test_signed_parent_rejects_bad_alignment_length_and_noninteger_fields():
    doc, raw, transfer, kwargs, sign = _signed_parent()
    for field, bad in (("size_bytes", True), ("chunk_bytes", False), ("generation", 7.0)):
        altered = {**doc, field: bad}
        candidate = sign(altered)
        t = replace(transfer, manifest_sha256=sha256(candidate).hexdigest())
        with pytest.raises(ChunkTransferRejected):
            verify_signed_large_parent(candidate, **{**kwargs, "transfer": t})
