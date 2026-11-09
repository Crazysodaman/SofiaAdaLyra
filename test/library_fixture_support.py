"""Pure disposable D028 signing fixtures, never publisher or owner production keys.

Keep fixture factories independent of Pytest fixture import/discovery order.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.library_chunk_receiver import PinnedChunkTransfer
from sofia.platform.ops.library_signed_index import SCHEMA, _DOMAIN


def make_signed_catalog_fixture():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    now = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)
    envelope = {
        "schema": SCHEMA,
        "publisher_key_sha256": sha256(public).hexdigest(),
        "source_platform_id": "primary-library",
        "target_platform_id": "enrolled-recipient",
        "catalog_revision": 7,
        "catalog_generation": 3,
        "issued_at": (now - timedelta(seconds=5)).isoformat(),
        "expires_at": (now + timedelta(minutes=1)).isoformat(),
        "catalog": {
            "catalog_revision": 7, "catalog_generation": 3,
            "catalog_fresh_until": (now + timedelta(seconds=30)).isoformat(),
            "target_platform_id": "enrolled-recipient",
            "source": {
                "kind": "OWNER_SELECTED_HUB", "source_id": "primary-library",
                "last_observed_at": now.isoformat(), "status": "CURRENT",
            },
            "page": {"limit": 32, "next_cursor": None, "cursor_state": "CURRENT"},
            "items": [],
        },
    }
    def sign(candidate=None):
        body = envelope if candidate is None else candidate
        payload = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        sig = private.sign(_DOMAIN + payload)
        signed = {**body, "signature_b64": b64encode(sig).decode("ascii")}
        return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    kwargs = dict(
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        expected_source_platform_id="primary-library",
        expected_target_platform_id="enrolled-recipient",
        expected_catalog_generation=3,
        minimum_catalog_revision=7, now=now,
        publisher_key_current=lambda _: True,
    )
    return envelope, sign, kwargs



def make_signed_offer_fixture():
    signed_catalog_fixture = make_signed_catalog_fixture()
    env, sign, kwargs = signed_catalog_fixture
    data = b"independent-verified-sdk-asset" * 12
    transfer = PinnedChunkTransfer(
        source_platform_id="primary-library",
        target_platform_id="enrolled-recipient",
        content_sha256=sha256(data).hexdigest(),
        size_bytes=len(data), generation=8,
        manifest_sha256="b" * 64,
        catalog_revision=7, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    row = dict(
        artifact_id="sdk.release.1", kind="sdk", version="1.0",
        revision=7, manifest_digest=transfer.manifest_sha256,
        content_digest=transfer.content_sha256, size_bytes=transfer.size_bytes,
        publisher="official-owner-approved-publisher",
        signer_key_id="independently-trusted-release-key",
        signature_scheme="ed25519", signature_receipt_ref="signed-receipt-123",
        target_os_arch="debian12-x86_64", sdk_range=">=1.0",
        abi_range=">=1.0", license_distribution="permitted",
        data_class="public", distribution_allowed=True,
    )
    env["catalog"]["items"] = [row]
    args = dict(
        raw_signed_index=sign(), transfer=transfer,
        expected_artifact_id=row["artifact_id"],
        trusted_publisher_public_key=kwargs["trusted_publisher_public_key"],
        expected_publisher_key_sha256=kwargs["expected_publisher_key_sha256"],
        expected_catalog_generation=3, now=kwargs["now"],
        publisher_key_current=lambda _: True,
    )
    return env, sign, args

