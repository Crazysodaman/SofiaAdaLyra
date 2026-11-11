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
import json
import subprocess
import zipfile

import pytest

from sofia.platform.ops.platform_installer_offline_capsule import (
    build_reviewed_offline_capsule, offline_capsule_publisher_seal_message,
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
    assert report["verified_release_asset_count"] == len(manifest.assets)
    assert report["offline_delivery_member_count"] == len(manifest.assets) + 2 + 8 + 1
    assert len(report["offline_delivery_index_sha256"]) == 64
    assert {item["sha256"] for item in report["signed_release_assets"]} == {
        asset.reference.sha256 for asset in manifest.assets
    }
    assert {item["path"] for item in report["signed_release_assets"]} == {
        asset.reference.path for asset in manifest.assets
    }
    assert len(report["unsigned_delivery_assets"]) == 9
    assert all(item["publisher_signature_verified"] is False
               for item in report["unsigned_delivery_assets"])
    assert report["publisher_revocation_fresh"] is False
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
        assert "aegis/debian12-offline-prerequisites.sh" in names
        assert "aegis/verify-aegis-capsule.sh" in names
        assert "aegis/inspect-aegis-capsule-members.sh" in names
        assert "aegis/stage-aegis-capsule.sh" in names
        assert "aegis/observe-debian12-service.sh" in names
        assert "aegis/delivery-index.v1" in names
        assert "aegis/contracts/ui/aegis-theme-v1.json" in names
        assert archive.read("aegis/release-manifest.json") == manifest.canonical_bytes
        for asset in manifest.assets:
            relative = "aegis/assets/" + asset.reference.path
            assert sha256(archive.read(relative)).hexdigest() == asset.reference.sha256
        for item in report["unsigned_delivery_assets"]:
            assert sha256(archive.read(item["path"])).hexdigest() == item["sha256"]
        forbidden = ("sofia/core/", "sofia/modules/", "owner-secret", "identity.json",
                     "personality.json", "memory.db")
        assert not any(part in path.lower() for path in names for part in forbidden)
    assert not (tmp_path / "sofia.db").exists()
    # Optional CI evidence is explicitly test-only and traceable to one
    # exact runner attempt. Never present this disposable signer as a
    # production publisher trust root or installed-host receipt.
    output_dir = os.environ.get("AEGIS_B004_TEST_CAPSULE_OUT")
    if output_dir:
        directory = Path(output_dir)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        (directory / "aegis-disposable-core-free-capsule.zip").write_bytes(one.read_bytes())
        (directory / "disposable-test-publisher.pem").write_bytes(
            Path(params["trusted_public_key"]).read_bytes()
        )
        fixture = {**report,
            "source_kind": "SYNTHETIC_TEST_ONLY",
            "production_publisher_root": False,
            "publisher_trust_independently_provisioned": False,
            "installed_host_evidence": False,
            "do_not_deploy": True,
        }
        (directory / "test-only-capsule-evidence.json").write_text(
            json.dumps(fixture, sort_keys=True, indent=2), encoding="utf-8",
        )


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


@pytest.mark.parametrize("asset_kind", (
    "sdk", "platform", "service", "python-runtime",
    "dependency-lock", "sbom", "provenance",
))
def test_capsule_refuses_tamper_to_each_mandatory_signed_asset(
        reviewed, tmp_path, asset_kind):
    builder, staging, manifest, params = reviewed
    target = next(item.reference for item in manifest.assets if item.kind == asset_kind)
    member = staging / "assets" / target.path
    with member.open("ab") as output:
        output.write(b"tampered-after-signature")
    capsule = tmp_path / "unsigned-drift.zip"
    with pytest.raises((PlatformReleaseRejected, ValueError)):
        build_reviewed_offline_capsule(**capsule_args(reviewed, capsule))
    assert not capsule.exists()


@pytest.mark.skipif(os.name == "nt" or shutil.which("openssl") is None,
                    reason="stock Linux OpenSSL Ed25519 capsule verification")
def test_same_release_publisher_seals_entire_core_free_capsule_with_stock_shell(
        reviewed, tmp_path):
    builder, stage, manifest, pins = reviewed
    capsule = tmp_path / "fully-sealed-test-only.zip"
    receipt = build_reviewed_offline_capsule(**capsule_args(reviewed, capsule))
    message = offline_capsule_publisher_seal_message(
        capsule_sha256=receipt["capsule_sha256"],
        signer_key_id=pins["trusted_signer_key_id"],
    )
    assert sha256(message).hexdigest() == receipt["publisher_capsule_seal_message_sha256"]
    # Test software signer is the SAME as the canonical signed release,
    # not an independent Hub key or a second installation signer.
    signature_path = tmp_path / "delivery-signature.raw"
    signature_path.write_bytes(builder._key.sign(message))
    verifier = PROJECT_ROOT / "packaging/installers/verify-aegis-capsule.sh"
    argv = [
        "bash", str(verifier),
        "--capsule", str(capsule),
        "--signature", str(signature_path),
        "--publisher-key", str(pins["trusted_public_key"]),
        "--publisher-sha256", pins["trusted_key_sha256"],
        "--publisher-signer", pins["trusted_signer_key_id"],
    ]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    witness = json.loads(result.stdout)
    assert witness["result"] == "SIGNED_CAPSULE_BYTES_ONLY"
    assert witness["capsule_sha256"] == receipt["capsule_sha256"]
    assert witness["publisher_delivery_verified"] is True
    assert witness["owner_approved"] is False
    assert witness["release_assets_verified"] is False
    assert witness["publisher_revocation_current"] is False
    assert receipt["launcher_publisher_signature_verified"] is False
    with capsule.open("ab") as output:
        output.write(b"capsule-byte-tampered-after-publisher-signing")
    tampered = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    assert tampered.returncode == 3
    assert "SIGNED_CAPSULE_BYTES_ONLY" not in tampered.stdout


@pytest.mark.parametrize("sha,signer", [
    ("not-a-sha256", "existing-publisher"),
    ("0" * 64, "invalid owner:publisher"),
])
def test_capsule_seal_message_rejects_invalid_signing_input(sha, signer):
    with pytest.raises(ValueError):
        offline_capsule_publisher_seal_message(
            capsule_sha256=sha, signer_key_id=signer,
        )

@pytest.mark.skipif(
    os.name == "nt" or shutil.which("openssl") is None or shutil.which("unzip") is None,
    reason="requires stock Linux Ed25519/ZIP staging tools",
)
def test_signed_offline_capsule_stages_inert_private_bytes_only(reviewed, tmp_path):
    builder, _stage, manifest, pins = reviewed
    capsule = tmp_path / "sealed-disposable.zip"
    receipt = build_reviewed_offline_capsule(**capsule_args(reviewed, capsule))
    signature = tmp_path / "sealed-disposable.raw64"
    signature.write_bytes(builder._key.sign(
        offline_capsule_publisher_seal_message(
            capsule_sha256=receipt["capsule_sha256"],
            signer_key_id=pins["trusted_signer_key_id"],
        ),
    ))
    # The owner explicitly selects a new PRIVATE staging directory.
    tmp_path.chmod(0o700)
    destination = tmp_path / "verified-staging"
    command = [
        "bash", str(PROJECT_ROOT / "packaging/installers/install-aegis.sh"),
        "--stage-capsule", str(capsule),
        "--capsule-signature", str(signature),
        "--publisher-key", str(pins["trusted_public_key"]),
        "--publisher-sha256", pins["trusted_key_sha256"],
        "--publisher-signer", pins["trusted_signer_key_id"],
        "--staging-destination", str(destination),
    ]
    outcome = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert outcome.returncode == 0, outcome.stderr[:500]
    observed = json.loads(outcome.stdout)
    assert observed["result"] == "SIGNED_MEDIA_STAGED_NOT_INSTALLED"
    assert observed["capsule_sha256"] == receipt["capsule_sha256"]
    assert observed["publisher_delivery_verified"] is True
    assert observed["inner_release_assets_verified_by_stager"] is False
    assert observed["owner_approved"] is False
    assert observed["native_service_registered"] is False
    assert observed["core_activated"] is False
    assert not (tmp_path / "sofia.db").exists()
    with zipfile.ZipFile(capsule) as archive:
        names = archive.namelist()
        assert len(names) == observed["member_count"] + 1
        for filename in names:
            staged = destination / filename
            assert staged.is_file()
            assert not staged.is_symlink()
            assert staged.stat().st_mode & 0o077 == 0
            assert sha256(staged.read_bytes()).hexdigest() == sha256(
                archive.read(filename),
            ).hexdigest()
    assert destination.stat().st_mode & 0o077 == 0
    assert (destination / "aegis/stage-aegis-capsule.sh").exists()
    assert (destination / "aegis/release-manifest.json").read_bytes() == manifest.canonical_bytes

    # A second run cannot silently adopt or overwrite existing output.
    denied = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert denied.returncode != 0
    assert sha256((destination / "aegis/release-manifest.json").read_bytes()).hexdigest() == sha256(
        manifest.canonical_bytes,
    ).hexdigest()

    # Mutating a previously publisher-sealed ZIP must be rejected before
    # creating a fresh staging directory.
    with capsule.open("ab") as changed:
        changed.write(b"changed-after-seal")
    command[-1] = str(tmp_path / "tampered-stage")
    tampered = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert tampered.returncode != 0
    assert not (tmp_path / "tampered-stage").exists()


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("openssl") is None or shutil.which("unzip") is None,
    reason="requires stock Linux Ed25519/ZIP staging tools",
)
def test_offline_stager_does_not_follow_untrusted_parent_or_accept_wrong_signer(
        reviewed, tmp_path):
    builder, _stage, _manifest, pins = reviewed
    capsule = tmp_path / "signed.zip"
    receipt = build_reviewed_offline_capsule(**capsule_args(reviewed, capsule))
    signature = tmp_path / "signed.raw64"
    signature.write_bytes(builder._key.sign(
        offline_capsule_publisher_seal_message(
            capsule_sha256=receipt["capsule_sha256"],
            signer_key_id=pins["trusted_signer_key_id"],
        ),
    ))
    tmp_path.chmod(0o700)
    alias = tmp_path / "redirected-parent"
    owner_private = tmp_path / "owner-private"
    owner_private.mkdir(mode=0o700)
    alias.symlink_to(owner_private, target_is_directory=True)
    args = [
        "bash", str(PROJECT_ROOT / "packaging/installers/install-aegis.sh"),
        "--stage-capsule", str(capsule), "--capsule-signature", str(signature),
        "--publisher-key", str(pins["trusted_public_key"]),
        "--publisher-sha256", pins["trusted_key_sha256"],
        "--publisher-signer", "wrong-signer",
        "--staging-destination", str(owner_private / "new-stage"),
    ]
    denied_signer = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert denied_signer.returncode != 0
    assert not (owner_private / "new-stage").exists()
    args[args.index("wrong-signer")] = pins["trusted_signer_key_id"]
    args[-1] = str(alias / "new-stage")
    denied_alias = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert denied_alias.returncode != 0
    assert not (owner_private / "new-stage").exists()
