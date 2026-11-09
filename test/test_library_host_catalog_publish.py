"""D028 Hub-pinned signed catalog renewal, without private key in Platform.

The small isolated test composes a verified prior signed selection with a
disposable external Ed25519 signing callback. It does not replace a real
owner-approved installed Hub RUN, TLS enrollment or production B1 proof.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_owner_catalog_publish import (
    OwnerPublishedAsset, publish_signed_owner_catalog,
)
from sofia.platform.ops.library_signed_index import verify_signed_library_index
from sofia.platform.ops.library_signed_selection import (
    verify_selected_signed_transfer,
)
from sofia.platform.ops.platform_install import (
    PlatformArtifact, PlatformKind,
)
from sofia.platform.run.library_host_service import HostedLibraryHub


def _signed_host():
    signing_key = Ed25519PrivateKey.generate()
    public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    now = datetime.now(timezone.utc)
    owner = {"enabled": True, "root": True, "package": True, "cache": True}
    payload = b"owner-approved-public-sdk"
    asset = OwnerPublishedAsset(
        artifact_id="sdk.release.1", kind="sdk", version="1.0",
        revision=7, manifest_digest="b" * 64,
        content_digest=sha256(payload).hexdigest(),
        size_bytes=len(payload), publisher="owner-test-release-publisher",
        signer_key_id="independent-B1-package-signer",
        signature_receipt_ref="signed-package-receipt-1",
        target_os_arch="debian12-x86_64", sdk_range=">=1.0",
        abi_range=">=1.0",
        license_distribution="permitted", data_class="public",
        distribution_allowed=True, independent_package_verified=True,
    )
    conditions = dict(
        source_platform_id="personally-enrolled-hub",
        target_platform_id="personally-enrolled-target",
        trusted_publisher_public_key=public,
        catalog_generation=3, catalog_revision=7,
        selected_assets=(asset,),
        sign_external=signing_key.sign,
        owner_hub_current=lambda: owner["enabled"],
        publisher_current=lambda _: owner["root"],
        time_now=lambda: now,
    )
    original = publish_signed_owner_catalog(**conditions)
    transfer = PinnedChunkTransfer(
        source_platform_id=conditions["source_platform_id"],
        target_platform_id=conditions["target_platform_id"],
        content_sha256=asset.content_digest, size_bytes=asset.size_bytes,
        generation=12, manifest_sha256=asset.manifest_digest,
        catalog_revision=7, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    selected = verify_selected_signed_transfer(
        raw_signed_index=original, transfer=transfer,
        expected_artifact_id=asset.artifact_id,
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        expected_catalog_generation=3, now=now,
        publisher_key_current=lambda _: True,
    )
    host = object.__new__(HostedLibraryHub)
    host._closed = False
    host._offer = selected
    host._trusted_public_key = public
    host._expected_key_sha = sha256(public).hexdigest()
    host._expected_catalog_generation = 3
    host._hub_grant = lambda: owner["enabled"]
    host._publisher_key_current = lambda _: owner["root"]
    host._package_signer_current = lambda _: owner["package"]
    host._clock = lambda: now + timedelta(seconds=15)
    host.transfer = transfer
    host.artifact = PlatformArtifact(
        artifact_id=asset.artifact_id, version=asset.version,
        platform=PlatformKind.LINUX, architecture="x86_64",
        sha256=asset.content_digest,
        signer_key_id=asset.signer_key_id, signature_verified=True,
        source="synthetic-independent-B1-verifier",
    )
    class Guard:
        def current_path(self, selected_transfer):
            if not owner["cache"] or selected_transfer != transfer:
                raise ChunkTransferRejected("verified cache changed")
            return "/verified-private-cas-digest"
    host._verified_cache = Guard()
    return host, owner, signing_key, selected


def test_hub_publishes_new_signed_index_for_same_exact_b1_and_recipient():
    host, owner, signer, initial = _signed_host()
    renewed = host.publish_current_signed_catalog(sign_external=signer.sign)
    published = verify_signed_library_index(
        renewed,
        trusted_publisher_public_key=host._trusted_public_key,
        expected_publisher_key_sha256=host._expected_key_sha,
        expected_source_platform_id=host.transfer.source_platform_id,
        expected_target_platform_id=host.transfer.target_platform_id,
        expected_catalog_generation=3, minimum_catalog_revision=7,
        now=host._clock(), publisher_key_current=lambda _: True,
    )
    assert published.catalog["source"]["source_id"] == host.transfer.source_platform_id
    assert published.catalog["target_platform_id"] == host.transfer.target_platform_id
    assert published.catalog["items"][0]["manifest_digest"] == host.transfer.manifest_sha256
    assert published.catalog["items"][0]["signer_key_id"] == host.artifact.signer_key_id
    assert published.expires_at > initial.index.expires_at


@pytest.mark.parametrize("change", ["enabled", "root", "package", "cache"])
def test_hub_cannot_publish_after_owner_or_signer_or_cas_revocation(change):
    host, owner, signer, initial = _signed_host()
    owner[change] = False
    with pytest.raises((PermissionError, ChunkTransferRejected)):
        host.publish_current_signed_catalog(sign_external=signer.sign)


def test_hub_cannot_use_untrusted_publisher_signing_key():
    host, owner, signer, initial = _signed_host()
    substitute = Ed25519PrivateKey.generate()
    with pytest.raises(PermissionError):
        host.publish_current_signed_catalog(sign_external=substitute.sign)


def test_closed_hub_never_signs_or_enrolls_new_recipient():
    host, owner, signer, initial = _signed_host()
    host._closed = True
    with pytest.raises(PermissionError, match="disabled"):
        host.publish_current_signed_catalog(sign_external=signer.sign)
