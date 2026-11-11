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
from sofia.platform.ops.platform_installer_capsule_b1_stage import (
    stage_sealed_capsule_for_b1,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from test.owner_auth_fixture import record_verified_owner_approval
from datetime import datetime, timedelta, timezone

from sofia.platform.ops.platform_release import PlatformReleaseRejected, PlatformReleaseVerifier
from test.test_ops_platform_installer_bundle import reviewed
from test.test_ops_platform_installer_capsule import capsule_args
from sofia.platform.ops.platform_installer_native_transaction import (
    apply_owner_approved_native_service, native_service_operation_request,
)
from sofia.platform.ops.platform_installer_native_service import DebianSystemdNativeService
from test.test_platform_service_session import provision

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


def _stage_original_signed_capsule_as_B1_candidate(args, home):
    candidate = home / "canonical-b1-stage"
    receipt = stage_sealed_capsule_for_b1(
        **args, b1_staging_candidate=candidate,
    )
    assert receipt["result"] == "SIGNED_B1_CODE_STAGED_NOT_INSTALLED"
    assert receipt["stage_receipt"]["result"] == "VERIFIED_PLATFORM_CODE_STAGED"
    assert receipt["owner_approved"] is False
    assert receipt["native_service_registered"] is False
    assert (candidate / "stage-receipt.json").is_file()
    return candidate


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


def test_inert_capsule_media_never_forges_canonical_B1_stage_receipt(
        sealed_stage, canonical_state_path):
    args, staged, _capsule, _manifest, home = sealed_stage
    store = PlatformInstallationStore(home / "b1-stage-refusal.db")
    with pytest.raises((PlatformReleaseRejected, PermissionError)):
        signed_capsule_code_publication_request(
            **args,
            b1_staging_candidate=staged / "aegis",
            destination=home / "must-remain-unpublished",
            identity_home=home / "protected-identity",
            state_path=canonical_state_path, store=store,
        )
    assert not (staged / "aegis/stage-receipt.json").exists()
    assert store.history() == []
    with pytest.raises((PlatformReleaseRejected, PermissionError)):
        stage_sealed_capsule_for_b1(
            **args, b1_staging_candidate=staged / "unsafe-nested-stage",
        )
    assert not (staged / "unsafe-nested-stage").exists()


def test_sealed_media_to_B1_code_publication_requires_distinct_owner_approval(
        sealed_stage, canonical_state_path):
    args, staged, capsule, manifest, host = sealed_stage
    now = datetime.now(timezone.utc)
    store = PlatformInstallationStore(host / "b1-code-store.db")
    installed = host / "published-code"
    params = dict(
        **args,
        b1_staging_candidate=_stage_original_signed_capsule_as_B1_candidate(args, host),
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
        **args,
        b1_staging_candidate=_stage_original_signed_capsule_as_B1_candidate(args, host),
        destination=installed,
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


def test_sealed_capsule_publishes_B1_then_registers_only_with_second_owner_proof(
        sealed_stage, canonical_state_path):
    args, staged, _capsule, manifest, home = sealed_stage
    now = datetime.now(timezone.utc)
    identity_store, installed_identity, local_state = provision(home / "host")
    b1 = PlatformInstallationStore(home / "b1-two-authorities.db")
    release = home / "private-installed-code"
    code = dict(
        **args,
        b1_staging_candidate=_stage_original_signed_capsule_as_B1_candidate(args, home),
        destination=release,
        identity_home=identity_store.home, state_path=canonical_state_path,
        store=b1,
    )

    def approve(plan, identifier):
        grant = ExecutionApproval(
            approval_id=identifier,
            capability=plan["capability"],
            request_fingerprint=plan["fingerprint"],
            approved_by="person:sparks",
            approved_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=5),
        )
        record_verified_owner_approval(
            ExecutionApprovalVerifier(canonical_state_path), grant,
        )
        return identifier

    preview = signed_capsule_code_publication_request(**code)
    code_request = preview["code_publication"]
    first = approve(
        code_request, "approval:sealed-media-code-publish-only",
    )
    published = publish_owner_approved_sealed_capsule_code(
        **code, approval_id=first, now=now,
    )
    assert published["result"] == "PLATFORM_RELEASE_INSTALLED"
    assert published["native_service_registered"] is False
    assert published["reviewed_inner_manifest_sha256"] == manifest.digest

    native = dict(
        operation="register",
        store=b1, verifier=PlatformReleaseVerifier({
            args["trusted_signer_key_id"]:
                Path(args["trusted_public_key"]).read_bytes(),
        }),
        expected_target=args["expected_target"],
        destination=release,
        identity_home=identity_store.home,
        local_state=local_state,
        canonical_safe_state=canonical_state_path,
    )
    backend = DebianSystemdNativeService()
    effects = []

    def observed_native(spec):
        effects.append((spec.platform_id, spec.manifest_sha256))
        return dict(
            schema="aegis.native-service-receipt.v1",
            service=spec.service_name, process_state="RUNNING",
            platform_id=spec.platform_id,
            release_manifest_sha256=spec.manifest_sha256,
            service_health="UNKNOWN", core_activated=False,
        )

    backend.register = observed_native
    # The previous one-use code publication proof CANNOT register the service.
    with pytest.raises((PermissionError, PlatformReleaseRejected)):
        apply_owner_approved_native_service(
            **native, backend=backend, approval_id=first, now=now,
        )
    assert effects == []
    second_plan = native_service_operation_request(**native)
    assert second_plan["fingerprint"] != code_request["fingerprint"]
    second = approve(
        second_plan, "approval:sealed-media-native-register-separate",
    )
    observed = apply_owner_approved_native_service(
        **native, backend=backend, approval_id=second, now=now,
    )
    assert observed["process_state"] == "RUNNING"
    assert observed["service_health"] == "UNKNOWN"
    assert observed["full_health_certified"] is False
    assert observed["core_activated"] is False
    assert effects == [(installed_identity.identity.canonical_uuid, manifest.digest)]
    assert b1.checkpoint().active_release_id is None
    assert len(effects) == 1
