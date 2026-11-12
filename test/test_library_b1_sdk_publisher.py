"""D028 one-asset signed B1 SDK verification on disposable real release keys.

Reuses the original Platform release test builder and exact Ed25519 contract.
No synthetic boolean from a Hub substitutes for signed package verification.
No install, activation, network or real host enrollment occurs in this file.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.ops.library_b1_sdk_publisher import (
    InstalledB1SignedSdkVerifier, canonical_signed_b1_sdk_envelope,
)
from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_release import (
    PlatformReleaseRejected, PlatformReleaseVerifier,
)
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.test_platform_release_verifier import fixture_release, platform_wheels


@pytest.fixture
def installed_sdk(tmp_path, platform_wheels):
    manifest, signer, public, signature = fixture_release(
        tmp_path, platform_wheels,
    )
    raw = canonical_signed_b1_sdk_envelope(
        payload=manifest.to_payload(),
        signature_b64=signature,
        signer_key_id="test-release",
    )
    asset = next(item for item in manifest.assets if item.kind == "sdk")
    signed_path = tmp_path / asset.reference.path
    transfer = PinnedChunkTransfer(
        source_platform_id="owner-source-platform",
        target_platform_id="owner-recipient-platform",
        content_sha256=asset.reference.sha256,
        size_bytes=asset.reference.size_bytes,
        generation=3,
        manifest_sha256=sha256(raw).hexdigest(),
        catalog_revision=manifest.revision,
        artifact_kind="sdk", license_distribution="permitted",
        data_class="public",
    )
    store = PlatformInstallationStore(tmp_path / "B1" / "install.db")
    authority = dict(current=True)
    args = dict(
        verifier=PlatformReleaseVerifier({"test-release": public}),
        installation=store, signed_envelope=raw,
        expected_source_sha="a" * 40,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        trusted_signer_key_id="test-release",
        signer_current=lambda _: authority["current"],
    )
    return manifest, signer, signed_path, transfer, store, args, authority


def test_independently_signed_b1_sdk_can_verify_single_asset_without_all_others(
    installed_sdk, tmp_path,
):
    manifest, signer, original, pin, store, args, authority = installed_sdk
    # A recipient has a single transferred SDK, not the entire release root.
    recipient = tmp_path / "received-cas"
    recipient.write_bytes(original.read_bytes())
    verified = InstalledB1SignedSdkVerifier(**args)
    artifact = verified(pin, recipient)
    assert artifact.artifact_id == manifest.release_id
    assert artifact.version == manifest.version
    assert artifact.sha256 == pin.content_sha256
    assert artifact.signer_key_id == "test-release"
    assert artifact.signature_verified is True
    assert artifact.source == "independent-b1-signed-sdk-envelope"
    assert verified.signed_manifest_sha256 == pin.manifest_sha256
    assert artifact.platform.value == "linux"
    assert store.receipt_for_release(manifest.release_id) is None
    assert not list(tmp_path.rglob("*.active"))


@pytest.mark.parametrize("change", (
    {"manifest_sha256": "f" * 64},
    {"content_sha256": "f" * 64},
    {"generation": 0},
    {"artifact_kind": "model"},
    {"license_distribution": "restricted"},
    {"data_class": "private"},
))
def test_signed_b1_sdk_never_adopts_different_transfer_scope(
    installed_sdk, change,
):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    verifier = InstalledB1SignedSdkVerifier(**args)
    if change in (
        {"generation": 0},
        {"license_distribution": "restricted"},
        {"data_class": "private"},
    ):
        # The typed transfer itself refuses invalid/protected scope.
        with pytest.raises((ValueError, TypeError, ChunkTransferRejected)):
            replace(pin, **change)
        return
    with pytest.raises(ChunkTransferRejected, match="differs"):
        verifier(replace(pin, **change), path)


def test_b1_sdk_rejects_independent_publisher_revocation(installed_sdk):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    verifier = InstalledB1SignedSdkVerifier(**args)
    authority["current"] = False
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        verifier(pin, path)


def test_b1_sdk_rejects_wrong_signed_envelope_key_or_tampering(installed_sdk):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    with pytest.raises(ChunkTransferRejected, match="signed SDK envelope"):
        InstalledB1SignedSdkVerifier(
            **{**args, "signed_envelope": args["signed_envelope"] + b" "},
        )
    changed = canonical_signed_b1_sdk_envelope(
        payload={**manifest.to_payload(), "version": "0.9.0"},
        signature_b64=args["signed_envelope"].decode("utf-8").split(
            '"signature_b64":"', 1,
        )[1].split('"', 1)[0],
        signer_key_id="test-release",
    )
    with pytest.raises(PlatformReleaseRejected, match="manifest"):
        InstalledB1SignedSdkVerifier(
            **{**args, "signed_envelope": changed},
        )


def test_b1_sdk_rejects_tampered_received_bytes_without_cache_admission(installed_sdk, tmp_path):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    copied = tmp_path / "received-corrupt"
    data = bytearray(path.read_bytes())
    data[0] ^= 0xFF
    copied.write_bytes(data)
    verifier = InstalledB1SignedSdkVerifier(**args)
    with pytest.raises(ChunkTransferRejected, match="violates B1 package policy"):
        verifier(pin, copied)


def test_b1_sdk_deny_after_installed_revision_floor_advances(installed_sdk):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    verified = InstalledB1SignedSdkVerifier(**args)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO ops_platform_installation_checkpoint "
            "(singleton,minimum_accepted_revision,active_release_id,"
            "active_installation_id,generation) VALUES (1,2,NULL,NULL,1)",
        )
    with pytest.raises((PlatformReleaseRejected, ChunkTransferRejected)):
        verified(pin, path)


def test_b1_sdk_cannot_claim_arbitrary_manifest_parent(installed_sdk):
    manifest, signer, path, pin, store, args, authority = installed_sdk
    with pytest.raises(PlatformReleaseRejected):
        InstalledB1SignedSdkVerifier(
            **{**args, "expected_parent_manifest_sha256": "f" * 64},
        )



def _record_test_only_installed_release(store, manifest):
    """Disposable B1 receipt fixture, never an installed production claim."""
    from datetime import datetime, timezone
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO ops_platform_installation_receipt "
            "(receipt_id,release_id,operation,result,revision,"
            "manifest_sha256,staging_path,destination,installed_at,"
            "activated,checkpoint_revision) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "receipt:owner-only-b1", manifest.release_id, "install",
                "SUCCEEDED", manifest.revision, manifest.digest,
                "/disposable/staging", "/disposable/installed",
                datetime.now(timezone.utc).isoformat(), 0,
                manifest.revision,
            ),
        )


def test_personal_hub_offer_requires_real_matching_installed_b1_receipt(
    installed_sdk,
):
    from sofia.platform.ops.library_b1_sdk_publisher import (
        review_personal_b1_sdk_offer,
    )
    manifest, signer, path, pin, store, args, authority = installed_sdk
    verifier = InstalledB1SignedSdkVerifier(**args)
    with pytest.raises(ChunkTransferRejected, match="installed B1 release receipt"):
        review_personal_b1_sdk_offer(
            verifier=verifier, transfer=pin, verified_local_sdk_path=path,
            owner_private_copy_allowed=lambda _: True,
        )
    _record_test_only_installed_release(store, manifest)
    offer = review_personal_b1_sdk_offer(
        verifier=verifier, transfer=pin, verified_local_sdk_path=path,
        owner_private_copy_allowed=lambda _: True,
    )
    assert offer.artifact_id == manifest.release_id
    assert offer.manifest_digest == pin.manifest_sha256
    assert offer.content_digest == pin.content_sha256
    assert offer.signature_receipt_ref == "receipt:owner-only-b1"
    assert offer.independent_package_verified is True
    assert offer.distribution_allowed is True
    assert offer.as_catalog_item()["kind"] == "sdk"


def test_signed_b1_sdk_owner_catalog_roundtrip_rejects_peer_key_invention(
    installed_sdk,
):
    """Real local B1 signature -> receipt -> personal catalog signature -> selection."""
    from datetime import datetime, timezone
    from cryptography.hazmat.primitives import serialization
    from sofia.platform.ops.library_b1_sdk_publisher import (
        review_personal_b1_sdk_offer,
    )
    from sofia.platform.ops.library_owner_catalog_publish import (
        publish_signed_owner_catalog,
    )
    from sofia.platform.ops.library_signed_selection import (
        verify_selected_signed_transfer,
    )
    manifest, signer, path, pin, store, args, authority = installed_sdk
    _record_test_only_installed_release(store, manifest)
    verifier = InstalledB1SignedSdkVerifier(**args)
    offer = review_personal_b1_sdk_offer(
        verifier=verifier, transfer=pin, verified_local_sdk_path=path,
        owner_private_copy_allowed=lambda _: True,
    )
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    instant = datetime.now(timezone.utc)
    signed_catalog = publish_signed_owner_catalog(
        source_platform_id=pin.source_platform_id,
        target_platform_id=pin.target_platform_id,
        trusted_publisher_public_key=public,
        catalog_generation=3,
        catalog_revision=pin.catalog_revision,
        selected_assets=[offer],
        sign_external=signer.sign,
        owner_hub_current=lambda: True,
        publisher_current=lambda _: True,
        time_now=lambda: instant,
    )
    chosen = verify_selected_signed_transfer(
        raw_signed_index=signed_catalog,
        transfer=pin,
        expected_artifact_id=offer.artifact_id,
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        expected_catalog_generation=3,
        now=instant,
        publisher_key_current=lambda _: True,
    )
    assert chosen.transfer == pin
    assert chosen.signer_key_id == "test-release"
    assert chosen.signature_receipt_ref == "receipt:owner-only-b1"
    assert verifier(pin, path).sha256 == chosen.transfer.content_sha256


def test_personal_copy_license_is_independent_of_verified_b1_signature(
    installed_sdk,
):
    from sofia.platform.ops.library_b1_sdk_publisher import (
        review_personal_b1_sdk_offer,
    )
    manifest, signer, path, pin, store, args, authority = installed_sdk
    _record_test_only_installed_release(store, manifest)
    verifier = InstalledB1SignedSdkVerifier(**args)
    with pytest.raises(ChunkTransferRejected, match="copy policy forbids"):
        review_personal_b1_sdk_offer(
            verifier=verifier, transfer=pin, verified_local_sdk_path=path,
            owner_private_copy_allowed=lambda _: False,
        )
    decisions = iter([True, False])
    with pytest.raises(ChunkTransferRejected, match="changed"):
        review_personal_b1_sdk_offer(
            verifier=verifier, transfer=pin, verified_local_sdk_path=path,
            owner_private_copy_allowed=lambda _: next(decisions),
        )
    assert store.receipt_for_release(manifest.release_id) is not None
