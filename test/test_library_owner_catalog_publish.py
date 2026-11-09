"""D028 personal LAN signed catalog: local owner use != peer-copy license.

All signatures in these tests use disposable Ed25519 keys. No private key
is persisted, loaded from production, or accepted from a remote recipient.
The canonical B1 service must supply independently verified package receipts.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.library_owner_catalog_publish import (
    OwnerCatalogPublishDenied, OwnerPublishedAsset, publish_signed_owner_catalog,
)
from sofia.platform.ops.library_signed_index import verify_signed_library_index
from sofia.platform.ops.library_signed_selection import verify_selected_signed_transfer
from sofia.platform.ops.library_chunk_receiver import PinnedChunkTransfer


@pytest.fixture
def publisher():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    now = datetime.now(timezone.utc)
    asset = OwnerPublishedAsset(
        artifact_id="sdk.release.1", kind="sdk", version="1.0",
        revision=7, manifest_digest="b" * 64,
        content_digest=sha256(b"owned-signed-sdk-payload").hexdigest(),
        size_bytes=len(b"owned-signed-sdk-payload"),
        publisher="owner-approved-publisher",
        signer_key_id="independent-B1-package-signer",
        signature_receipt_ref="signed-receipt-1",
        target_os_arch="debian12-x86_64", sdk_range=">=1.0",
        abi_range=">=1.0",
        license_distribution="permitted",
        data_class="public", distribution_allowed=True,
        independent_package_verified=True,
    )
    controls = dict(owner=True, publisher=True, signer_calls=0)
    def external_sign(message):
        controls["signer_calls"] += 1
        return private.sign(message)
    values = {
        "source_platform_id": "private-owner-hub",
        "target_platform_id": "enrolled-personal-host",
        "trusted_publisher_public_key": public,
        "catalog_generation": 3, "catalog_revision": 7,
        "selected_assets": [asset],
        "sign_external": external_sign,
        "owner_hub_current": lambda: controls["owner"],
        "publisher_current": lambda _key: controls["publisher"],
        "time_now": lambda: now,
    }
    return asset, values, controls, now


def test_single_owner_publisher_produces_exact_recipient_verifiable_index(publisher):
    asset, values, controls, now = publisher
    raw = publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 1
    key = sha256(values["trusted_publisher_public_key"]).hexdigest()
    verified = verify_signed_library_index(
        raw, trusted_publisher_public_key=values["trusted_publisher_public_key"],
        expected_publisher_key_sha256=key,
        expected_source_platform_id=values["source_platform_id"],
        expected_target_platform_id=values["target_platform_id"],
        expected_catalog_generation=3, minimum_catalog_revision=7,
        now=now, publisher_key_current=lambda _: True,
    )
    assert verified.catalog_revision == 7
    assert verified.catalog["source"]["kind"] == "OWNER_SELECTED_HUB"
    assert len(verified.catalog["items"]) == 1
    transfer = PinnedChunkTransfer(
        source_platform_id=values["source_platform_id"],
        target_platform_id=values["target_platform_id"],
        content_sha256=asset.content_digest,
        size_bytes=asset.size_bytes,
        generation=42, manifest_sha256=asset.manifest_digest,
        catalog_revision=7, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    chosen = verify_selected_signed_transfer(
        raw_signed_index=raw, transfer=transfer,
        expected_artifact_id=asset.artifact_id,
        trusted_publisher_public_key=values["trusted_publisher_public_key"],
        expected_publisher_key_sha256=key, expected_catalog_generation=3,
        now=now, publisher_key_current=lambda _: True,
    )
    assert chosen.artifact_id == asset.artifact_id
    assert chosen.signer_key_id == asset.signer_key_id
    assert chosen.signature_receipt_ref == asset.signature_receipt_ref


@pytest.mark.parametrize("change", [
    {"license_distribution": "personal-use-no-peer-copy"},
    {"data_class": "private"},
    {"data_class": "adult"},
    {"distribution_allowed": False},
    {"independent_package_verified": False},
    {"content_digest": "not-a-sha"},
    {"manifest_digest": "F" * 64},
    {"kind": "unreviewed_model"},
])
def test_private_noncopyable_or_unsigned_artifact_never_reaches_signer(publisher, change):
    asset, values, controls, now = publisher
    values["selected_assets"] = [replace(asset, **change)]
    with pytest.raises(OwnerCatalogPublishDenied):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0


def test_personal_local_use_license_does_not_become_peer_copy_permission(publisher):
    asset, values, controls, now = publisher
    personal_only = replace(
        asset, artifact_id="my.local.voice-model", kind="model",
        license_distribution="personal-use-permitted-no-copy",
        distribution_allowed=False,
    )
    values["selected_assets"] = [asset, personal_only]
    with pytest.raises(OwnerCatalogPublishDenied):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0
    # Reject the whole candidate rather than leaking even the restricted
    # model name or content digest to the recipient's signed LAN index.
    values["selected_assets"] = [asset]
    assert publish_signed_owner_catalog(**values)


@pytest.mark.parametrize("override", [
    {"source_platform_id": "0.0.0.0"},
    {"source_platform_id": ""},
    {"target_platform_id": "private-owner-hub"},
    {"catalog_generation": 0},
    {"catalog_revision": True},
    {"lifetime_seconds": 301},
    {"lifetime_seconds": 10},
    {"selected_assets": []},
])
def test_unreviewed_hub_parameters_refused_without_signing(publisher, override):
    asset, values, controls, now = publisher
    # Source ID '0.0.0.0' has valid lexical form but isn't an IPv4 bind
    # authority; this publisher only binds signed identity, not transport.
    if override == {"source_platform_id": "0.0.0.0"}:
        override = {"source_platform_id": "*wildcard"}
    with pytest.raises(OwnerCatalogPublishDenied):
        publish_signed_owner_catalog(**{**values, **override})
    assert controls["signer_calls"] == 0


def test_signer_cannot_replace_independent_owner_pinned_key(publisher):
    asset, values, controls, now = publisher
    other = Ed25519PrivateKey.generate()
    values["sign_external"] = other.sign
    with pytest.raises(PermissionError):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0


def test_owner_revocation_prevents_any_signature_or_published_bytes(publisher):
    asset, values, controls, now = publisher
    controls["owner"] = False
    with pytest.raises(OwnerCatalogPublishDenied, match="denied"):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0
    controls["owner"] = True
    controls["publisher"] = False
    with pytest.raises(OwnerCatalogPublishDenied, match="denied"):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0


def test_revocation_during_signing_refuses_publishing_receipt(publisher):
    asset, values, controls, now = publisher
    old_sign = values["sign_external"]
    def revoke_while_signing(payload):
        signature = old_sign(payload)
        controls["owner"] = False
        return signature
    values["sign_external"] = revoke_while_signing
    with pytest.raises(OwnerCatalogPublishDenied, match="revoked"):
        publish_signed_owner_catalog(**values)


def test_duplicate_signed_release_names_never_advertised(publisher):
    asset, values, controls, now = publisher
    values["selected_assets"] = [asset, asset]
    with pytest.raises(OwnerCatalogPublishDenied, match="duplicate"):
        publish_signed_owner_catalog(**values)
    assert controls["signer_calls"] == 0
