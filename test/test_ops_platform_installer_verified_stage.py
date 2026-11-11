"""Executable signed-capsule -> private stage -> canonical B1 review seam.

Only disposable software-publisher signing keys are used. No Core installation,
SAFE approval, OS service, Fleet enrollment or production acceptance.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from sofia.platform.ops.platform_installer_offline_capsule import (
    build_reviewed_offline_capsule, offline_capsule_publisher_seal_message,
)
from sofia.platform.ops.platform_installer_verified_stage import (
    review_staged_publisher_signed_capsule,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from test.test_ops_platform_installer_bundle import reviewed
from test.test_ops_platform_installer_capsule import capsule_args

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.pkg_ops,
    pytest.mark.skipif(
        os.name == "nt" or shutil.which("openssl") is None
        or shutil.which("unzip") is None,
        reason="stock Debian Bash ZIP and Ed25519 shell staging fixtures",
    ),
]


@pytest.fixture
def sealed_stage(reviewed, tmp_path):
    builder, _source, manifest, pinned = reviewed
    capsule = tmp_path / "disposable-signed.zip"
    receipt = build_reviewed_offline_capsule(
        **capsule_args(reviewed, capsule),
    )
    detached = tmp_path / "disposable-signature.raw64"
    detached.write_bytes(builder._key.sign(
        offline_capsule_publisher_seal_message(
            capsule_sha256=receipt["capsule_sha256"],
            signer_key_id=pinned["trusted_signer_key_id"],
        ),
    ))
    tmp_path.chmod(0o700)
    staged = tmp_path / "private-staged-release"
    command = [
        "bash", str(PROJECT_ROOT / "packaging/installers/install-aegis.sh"),
        "--stage-capsule", str(capsule),
        "--capsule-signature", str(detached),
        "--publisher-key", str(pinned["trusted_public_key"]),
        "--publisher-sha256", pinned["trusted_key_sha256"],
        "--publisher-signer", pinned["trusted_signer_key_id"],
        "--staging-destination", str(staged),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[:500]
    assert json.loads(result.stdout)["result"] == "SIGNED_MEDIA_STAGED_NOT_INSTALLED"
    args = dict(
        capsule=capsule,
        capsule_signature=detached,
        staged_directory=staged,
        **pinned,
    )
    return args, staged, capsule, manifest, tmp_path


def test_outer_seal_and_inner_b1_verifier_agree_without_any_install(sealed_stage):
    args, staged, capsule, manifest, host = sealed_stage
    review = review_staged_publisher_signed_capsule(**args)
    assert review["result"] == "OUTER_AND_INNER_SIGNED_BYTES_VERIFIED_ONLY"
    assert review["capsule_sha256"] == sha256(capsule.read_bytes()).hexdigest()
    assert review["outer_publisher_signature_verified"] is True
    assert review["inner_release"]["manifest_sha256"] == manifest.digest
    assert review["inner_release"]["result"] == "VERIFIED_RELEASE_BYTES_ONLY"
    assert review["publisher_revocation_current_verified"] is False
    assert review["owner_approved"] is False
    assert review["install_executed"] is False
    assert review["native_service_registered"] is False
    assert review["service_health"] == "UNKNOWN"
    assert review["core_activated"] is False
    assert not (host / "sofia.db").exists()


@pytest.mark.parametrize("corruption", (
    "launcher", "delivery-index", "extra-file", "nonprivate-file",
    "invalid-signature", "wrong-source", "wrong-key",
))
def test_double_signed_stage_rejects_tamper_or_untrusted_scope(
        sealed_stage, corruption):
    args, staged, capsule, manifest, host = sealed_stage
    params = dict(args)
    if corruption == "launcher":
        target = staged / "aegis/install-aegis.sh"
        target.write_bytes(target.read_bytes() + b"forged")
    elif corruption == "delivery-index":
        target = staged / "aegis/delivery-index.v1"
        target.write_bytes(target.read_bytes() + b"forged")
    elif corruption == "extra-file":
        (staged / "aegis/foreign-extra.bin").write_bytes(b"unapproved")
    elif corruption == "nonprivate-file":
        (staged / "aegis/install-aegis.sh").chmod(0o644)
    elif corruption == "invalid-signature":
        args["capsule_signature"].write_bytes(b"x" * 64)
    elif corruption == "wrong-source":
        params["expected_source_sha"] = "a" * 40
    elif corruption == "wrong-key":
        params["trusted_key_sha256"] = "0" * 64
    with pytest.raises((PlatformReleaseRejected, PermissionError, ValueError)):
        review_staged_publisher_signed_capsule(**params)
    assert not (host / "sofia.db").exists()
