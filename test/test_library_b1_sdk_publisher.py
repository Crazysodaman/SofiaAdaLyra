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
    if change == {"generation": 0}:
        # The typed transfer itself refuses invalid generations.
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
