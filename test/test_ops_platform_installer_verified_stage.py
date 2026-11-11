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
from sofia.platform.ops.platform_installer_sealed_publication import (
    signed_capsule_code_publication_request,
    publish_owner_approved_sealed_capsule_code,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from test.owner_auth_fixture import record_verified_owner_approval
from datetime import datetime, timedelta, timezone

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


def test_sealed_media_to_B1_code_publication_requires_distinct_owner_approval(
        sealed_stage, canonical_state_path):
    args, staged, capsule, manifest, host = sealed_stage
    now = datetime.now(timezone.utc)
    store = PlatformInstallationStore(host / "b1-code-store.db")
    installed = host / "published-code"
    params = dict(
        **args,
        destination=installed,
        identity_home=host / "protected-identity",
        state_path=canonical_state_path,
        store=store,
    )
    preview = signed_capsule_code_publication_request(**params)
    assert preview["result"] == "SIGNED_CODE_APPROVAL_REQUIRED"
    assert preview["code_publication"]["authorized"] is False
    assert preview["code_publication"]["executed"] is False
    assert preview["release_manifest_sha256"] == manifest.digest
    assert preview["code_publication"]["parameters"]["outer_capsule_sha256"] == preview["capsule_sha256"]
    assert preview["code_publication"]["parameters"]["delivery_index_sha256"] == preview["delivery_index_sha256"]
    assert not installed.exists()
    assert store.history() == []

    # A valid package signature alone cannot publish B1 code or register SCM.
    with pytest.raises((PermissionError, PlatformReleaseRejected)):
        publish_owner_approved_sealed_capsule_code(
            **params, approval_id="unapproved", now=now,
        )
    assert not installed.exists()

    request = preview["code_publication"]
    approval = ExecutionApproval(
        approval_id="approval:disposable-sealed-publish",
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(canonical_state_path), approval,
    )
    result = publish_owner_approved_sealed_capsule_code(
        **params, approval_id=approval.approval_id, now=now,
    )
    assert result["result"] == "PLATFORM_RELEASE_INSTALLED"
    assert result["reviewed_inner_manifest_sha256"] == manifest.digest
    assert result["outer_capsule_sha256"] == sha256(capsule.read_bytes()).hexdigest()
    assert result["owner_proof_consumed"] is True
    assert result["code_published"] is True
    assert result["native_service_registered"] is False
    assert result["os_service_registered"] is False
    assert result["service_health"] == "UNKNOWN"
    assert result["core_activated"] is False
    assert result["fleet_enrolled"] is False
    assert (installed / "release-manifest.json").is_file()
    assert not (host / "protected-identity").exists()
    assert store.checkpoint().active_release_id is None

    with pytest.raises((PermissionError, PlatformReleaseRejected, FileExistsError)):
        publish_owner_approved_sealed_capsule_code(
            **params, approval_id=approval.approval_id,
            now=now + timedelta(seconds=1),
        )
    assert len(store.history()) == 1


def test_sealed_code_publication_refuses_changed_stage_before_safe_consumption(
        sealed_stage, canonical_state_path):
    args, staged, _capsule, _manifest, host = sealed_stage
    store = PlatformInstallationStore(host / "b1-denied-store.db")
    installed = host / "never-published"
    params = dict(
        **args, destination=installed,
        identity_home=host / "identity",
        state_path=canonical_state_path, store=store,
    )
    plan = signed_capsule_code_publication_request(**params)
    now = datetime.now(timezone.utc)
    request = plan["code_publication"]
    approval = ExecutionApproval(
        approval_id="approval:staged-bytes-replaced",
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(canonical_state_path), approval,
    )
    changed = staged / "aegis/install-aegis.sh"
    changed.write_bytes(changed.read_bytes() + b"altered-after-review")
    with pytest.raises((PlatformReleaseRejected, PermissionError)):
        publish_owner_approved_sealed_capsule_code(
            **params, approval_id=approval.approval_id, now=now,
        )
    assert not installed.exists()
    assert store.history() == []
