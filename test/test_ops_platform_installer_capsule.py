"""B-004 deterministic offline capsule of independently verified signed code.

The release and its signer are disposable test fixtures. The packager never
creates owner permission, executes the installed runtime or claims that the
unsignable launcher/theme resources are publisher certified.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import shutil
import zipfile

import pytest

from sofia.platform.ops.platform_installer_offline_capsule import (
    build_reviewed_offline_capsule,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from test.test_ops_platform_installer_bundle import reviewed

pytestmark = pytest.mark.pkg_ops
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def capsule_args(reviewed, output):
    _builder, staging, _manifest, params = reviewed
    return dict(
        staged_release=staging,
        project_root=PROJECT_ROOT,
        output_path=output,
        trusted_public_key=params["trusted_public_key"],
        trusted_key_sha256=params["trusted_key_sha256"],
        trusted_signer_key_id=params["trusted_signer_key_id"],
        expected_source_sha=params["expected_source_sha"],
        expected_target=params["expected_target"],
        minimum_revision=params["minimum_revision"],
    )


def test_capsule_packages_exact_signed_assets_and_stock_launchers_without_core(
        reviewed, tmp_path):
    _builder, staged, manifest, params = reviewed
    one = tmp_path / "capsule-one.zip"
    two = tmp_path / "capsule-two.zip"
    report = build_reviewed_offline_capsule(**capsule_args(reviewed, one))
    second = build_reviewed_offline_capsule(**capsule_args(reviewed, two))
    assert report["result"] == "SIGNED_RELEASE_BYTES_PACKAGED_NOT_INSTALLED"
    assert report["release_manifest_sha256"] == manifest.digest
    assert report["release_manifest_signature_verified"] is True
    assert report["release_assets_verified"] is True
    assert report["launcher_publisher_signature_verified"] is False
    assert report["owner_authorized"] is False
    assert report["self_contained_native_installer_certified"] is False
    assert report["installed"] is False
    assert report["core_activated"] is False
    assert report["capsule_sha256"] == sha256(one.read_bytes()).hexdigest()
    assert report["capsule_sha256"] == second["capsule_sha256"]
    assert one.read_bytes() == two.read_bytes()
    with zipfile.ZipFile(one) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert "aegis/install-aegis.sh" in names
        assert "aegis/Install-Aegis.ps1" in names
        assert "aegis/contracts/ui/aegis-theme-v1.json" in names
        assert archive.read("aegis/release-manifest.json") == manifest.canonical_bytes
        for asset in manifest.assets:
            relative = "aegis/assets/" + asset.reference.path
            assert sha256(archive.read(relative)).hexdigest() == asset.reference.sha256
        forbidden = ("sofia/core/", "sofia/modules/", "owner-secret", "identity.json",
                     "personality.json", "memory.db")
        assert not any(part in path.lower() for path in names for part in forbidden)
    assert not (tmp_path / "sofia.db").exists()


def test_capsule_refuses_wrong_signer_digest_and_unsigned_mutation(
        reviewed, tmp_path):
    _builder, staged, _manifest, params = reviewed
    output = tmp_path / "capsule.zip"
    args = capsule_args(reviewed, output)
    with pytest.raises(PlatformReleaseRejected):
        build_reviewed_offline_capsule(**{**args, "trusted_key_sha256": "0" * 64})
    assert not output.exists()
    modified = staged / "release-signature.json"
    before = modified.read_bytes()
    modified.write_bytes(before + b"forged")
    with pytest.raises((PlatformReleaseRejected, ValueError)):
        build_reviewed_offline_capsule(**args)
    assert not output.exists()


def test_capsule_does_not_replace_existing_reviewed_media(reviewed, tmp_path):
    output = tmp_path / "capsule.zip"
    output.write_bytes(b"immutable owner selected media")
    with pytest.raises(PlatformReleaseRejected, match="already exists"):
        build_reviewed_offline_capsule(**capsule_args(reviewed, output))
    assert output.read_bytes() == b"immutable owner selected media"


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink elevation differs")
def test_capsule_does_not_accept_root_redirection(reviewed, tmp_path):
    _builder, staged, _manifest, params = reviewed
    alias = tmp_path / "stage-link"
    alias.symlink_to(staged, target_is_directory=True)
    with pytest.raises((PlatformReleaseRejected, PermissionError)):
        build_reviewed_offline_capsule(
            **{**capsule_args(reviewed, tmp_path / "capsule.zip"),
               "staged_release": alias},
        )
