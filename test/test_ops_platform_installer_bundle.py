"""AG-D011 signed installer input gate with independently pinned publisher trust.

These are disposable software keys. They are never owner or production keys.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_installer_bundle import (
    host_release_target, verify_offline_installer_bundle,
)
from sofia.platform.ops.platform_installer_preview import preview_signed_platform_install
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels

pytestmark = pytest.mark.pkg_ops


@pytest.fixture
def reviewed(tmp_path, platform_wheels):
    builder = SignedReleaseBuilder(tmp_path / "builder", platform_wheels)
    staging, manifest, signature = builder.stage(revision=3)
    key_dir = tmp_path / "out-of-band-root"
    key_dir.mkdir()
    trusted = key_dir / "publisher.pem"
    public = builder._key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    trusted.write_bytes(public)
    params = dict(
        trusted_public_key=trusted,
        trusted_key_sha256=sha256(public).hexdigest(),
        trusted_signer_key_id=builder.signer_key_id,
        expected_source_sha=manifest.source_sha,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        minimum_revision=3,
        require_local_host=False,
    )
    return builder, staging, manifest, params


def test_signed_offline_bundle_verification_is_read_only(reviewed, tmp_path):
    builder, staging, manifest, params = reviewed
    before = sorted(str(p.relative_to(staging)) for p in staging.rglob("*"))
    result = verify_offline_installer_bundle(staging, **params)
    assert result.release_id == manifest.release_id
    assert result.manifest_sha256 == manifest.digest
    assert result.revision == 3
    report = result.review()
    assert report["result"] == "VERIFIED_RELEASE_BYTES_ONLY"
    assert report["os_service_registered"] is False
    assert report["owner_approved"] is False
    assert report["core_activated"] is False
    assert not (tmp_path / "service").exists()
    assert before == sorted(str(p.relative_to(staging)) for p in staging.rglob("*"))


@pytest.mark.parametrize("defect", (
    "no-pin", "wrong-pin", "wrong-signer", "wrong-source",
    "stale-revision", "wrong-target", "wrong-parent", "trust-inside-bundle",
    "tampered-signature", "tampered-asset",
))
def test_signed_offline_bundle_refuses_untrusted_or_mismatched_input(
        reviewed, defect, tmp_path):
    builder, staging, manifest, params = reviewed
    params = dict(params)
    if defect == "no-pin":
        params["trusted_key_sha256"] = ""
    elif defect == "wrong-pin":
        params["trusted_key_sha256"] = "0" * 64
    elif defect == "wrong-signer":
        params["trusted_signer_key_id"] = "attacker"
    elif defect == "wrong-source":
        params["expected_source_sha"] = "0" * 40
    elif defect == "stale-revision":
        params["minimum_revision"] = 4
    elif defect == "wrong-target":
        params["expected_target"] = PlatformReleaseTarget.WINDOWS_X86_64
    elif defect == "wrong-parent":
        params["expected_parent_manifest_sha256"] = "f" * 64
    elif defect == "trust-inside-bundle":
        copy = staging / "self-supplied-trust.pem"
        copy.write_bytes(Path(params["trusted_public_key"]).read_bytes())
        params["trusted_public_key"] = copy
    elif defect == "tampered-signature":
        sig = staging / "release-signature.json"
        encoded = json.loads(sig.read_text())
        encoded["signature_b64"] = "A" * 88
        sig.write_text(json.dumps(encoded))
    elif defect == "tampered-asset":
        ref = manifest.assets[0].reference
        asset = staging / "assets" / ref.path
        asset.write_bytes(asset.read_bytes() + b"tampering")
    with pytest.raises((PlatformReleaseRejected, PermissionError, ValueError)):
        verify_offline_installer_bundle(staging, **params)


def test_host_mismatch_blocks_signed_release_even_when_signature_valid(reviewed, monkeypatch):
    import sofia.platform.ops.platform_installer_bundle as bridge
    _builder, staged, _manifest, params = reviewed
    params = dict(params, require_local_host=True)
    monkeypatch.setattr(bridge, "host_release_target",
                        lambda: PlatformReleaseTarget.WINDOWS_X86_64)
    with pytest.raises(PlatformReleaseRejected, match="observed host"):
        verify_offline_installer_bundle(staged, **params)


def test_signed_plan_reuses_b1_store_revision_fence_without_install(reviewed, tmp_path):
    builder, staging, manifest, params = reviewed
    store = PlatformInstallationStore(tmp_path / "installer-receipts.db")
    target = tmp_path / "install-target"
    plan = preview_signed_platform_install(
        staging_path=staging, destination=target, store=store,
        verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
    )
    assert plan["manifest_sha256"] == manifest.digest
    assert plan["checkpoint_generation"] == 0
    assert plan["minimum_accepted_revision"] == 1
    assert plan["executed"] is False
    assert plan["os_service_registered"] is False
    assert not target.exists()
    assert store.history() == []
