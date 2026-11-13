"""B1 signed code publication must consume current canonical SAFE approval."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.platform.ops.platform_installation import PlatformInstallationDenied, PlatformInstallationStore
from sofia.platform.ops.platform_installer_code_install import (
    CODE_PUBLISH_CAPABILITY, publish_owner_approved_code,
    signed_code_publication_request,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels

pytestmark = pytest.mark.pkg_ops


@pytest.fixture
def scope(tmp_path, platform_wheels, canonical_state_path):
    builder = SignedReleaseBuilder(tmp_path / "signed-build", platform_wheels)
    stage, manifest, _signature = builder.stage(revision=4)
    return dict(
        staged_candidate=stage,
        destination=tmp_path / "release-v4",
        identity_home=tmp_path / "identity",
        state_path=canonical_state_path,
        store=PlatformInstallationStore(tmp_path / "b1-receipts.db"),
        verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
    )


def test_code_publication_request_is_pure_preview_with_scoped_exact_hash(scope):
    args = dict(scope)
    before = args["store"].history()
    plan = signed_code_publication_request(**args)
    assert plan["capability"] == CODE_PUBLISH_CAPABILITY
    assert plan["parameters"]["kind"] == "nonactivating-signed-code-only"
    assert plan["parameters"]["checkpoint_generation"] == 0
    assert plan["authorized"] is False
    assert plan["executed"] is False
    assert not args["destination"].exists()
    assert args["store"].history() == before


def test_capsule_bound_code_publication_approval_cannot_replace_outer_media(scope):
    params = dict(scope)
    plain = signed_code_publication_request(**params)
    sealed = signed_code_publication_request(
        **params, outer_capsule_sha256="a" * 64,
        delivery_index_sha256="b" * 64,
    )
    assert sealed["fingerprint"] != plain["fingerprint"]
    assert sealed["parameters"]["outer_capsule_sha256"] == "a" * 64
    assert sealed["parameters"]["delivery_index_sha256"] == "b" * 64
    modified_media = signed_code_publication_request(
        **params, outer_capsule_sha256="c" * 64,
        delivery_index_sha256="b" * 64,
    )
    modified_inventory = signed_code_publication_request(
        **params, outer_capsule_sha256="a" * 64,
        delivery_index_sha256="c" * 64,
    )
    assert modified_media["fingerprint"] != sealed["fingerprint"]
    assert modified_inventory["fingerprint"] != sealed["fingerprint"]
    with pytest.raises(PlatformInstallationDenied):
        signed_code_publication_request(
            **params, outer_capsule_sha256="a" * 64,
        )
    with pytest.raises(PlatformInstallationDenied):
        signed_code_publication_request(
            **params, outer_capsule_sha256="BAD",
            delivery_index_sha256="b" * 64,
        )
    assert not params["destination"].exists()
    assert params["store"].history() == []


@pytest.mark.parametrize("approval_id", ("", "bogus-unapproved-id"))
def test_code_mutation_refused_without_current_owner_proof(scope, approval_id):
    args = dict(scope)
    with pytest.raises((PermissionError, PlatformInstallationDenied)):
        publish_owner_approved_code(approval_id=approval_id, **args)
    assert not args["destination"].exists()
    assert args["store"].history() == []


def test_one_use_exact_owner_grant_publishes_only_signed_code_without_service(scope):
    args = dict(scope)
    request = signed_code_publication_request(**args)
    now = datetime.now(timezone.utc)
    approvals = ExecutionApprovalVerifier(args["state_path"])
    approval = ExecutionApproval(
        approval_id="approval:installer-code-v4-disposable",
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(approvals, approval)
    result = publish_owner_approved_code(
        approval_id=approval.approval_id, now=now, **args,
    )
    assert result["result"] == "PLATFORM_RELEASE_INSTALLED"
    assert result["owner_proof_consumed"] is True
    assert result["os_service_registered"] is False
    assert result["core_activated"] is False
    assert result["fleet_enrolled"] is False
    assert args["destination"].exists()
    assert args["store"].checkpoint().active_release_id is None
    # The same approval cannot publish a second release or replace installed data.
    with pytest.raises((PermissionError, PlatformInstallationDenied)):
        publish_owner_approved_code(
            approval_id=approval.approval_id, now=now + timedelta(seconds=2), **args,
        )



def test_code_publication_rejects_owner_revocation_during_B1_copy(
        scope, monkeypatch):
    import sofia.platform.ops.platform_installer_code_install as code

    args = dict(scope)
    now = datetime.now(timezone.utc)
    plan = signed_code_publication_request(**args)
    approval = ExecutionApproval(
        approval_id="approval:code-copy-revoked-after-effect",
        capability=plan["capability"],
        request_fingerprint=plan["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(args["state_path"]), approval,
    )
    copied = code.install_staged_release

    def copy_then_revoke(*positional, **kwargs):
        receipt = copied(*positional, **kwargs)
        with sqlite3.connect(args["state_path"]) as db:
            db.execute(
                "UPDATE safe_owner_credential SET revoked_at=? "
                "WHERE revoked_at IS NULL",
                (now.isoformat(),),
            )
        return receipt

    monkeypatch.setattr(code, "install_staged_release", copy_then_revoke)
    with pytest.raises(PlatformInstallationDenied, match="reconcile B1 receipt"):
        publish_owner_approved_code(
            approval_id=approval.approval_id, now=now, **args,
        )
    # The OS service never starts. B1 may already have published code;
    # a revoked owner proof forbids a *successful* wrapper outcome. The
    # operator must read the durable B1 receipt before any retry.
    assert args["destination"].exists()
    assert args["store"].history()
    assert not (args["destination"] / "core").exists()


def _approve_code_request(state_path, request, approval_id, now):
    approval = ExecutionApproval(
        approval_id=approval_id,
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(state_path), approval)
    return approval


def test_signed_direct_successor_requires_exact_previous_bytes_and_new_owner_approval(
        scope, platform_wheels):
    args = dict(scope)
    builder = SignedReleaseBuilder(args["destination"].parent / "successor-build", platform_wheels)
    first_stage, _, _ = builder.stage(release_id="disposable-vm-base", revision=4)
    args["staged_candidate"] = first_stage
    args["verifier"] = builder.verifier
    now = datetime.now(timezone.utc)
    InstallationIdentityStore(args["identity_home"]).initialize()
    first_request = signed_code_publication_request(**args)
    first_approval = _approve_code_request(
        args["state_path"], first_request, "approval:initial-code", now,
    )
    first = publish_owner_approved_code(
        approval_id=first_approval.approval_id, now=now, **args,
    )

    next_stage, next_manifest, _ = builder.stage(
        release_id="disposable-vm-successor", revision=5,
        parent_manifest_sha256=first["manifest_sha256"],
    )
    successor = {
        **args,
        "staged_candidate": next_stage,
        "destination": args["destination"].parent / "release-v5",
        "verifier": builder.verifier,
        "previous_destination": args["destination"],
    }
    request = signed_code_publication_request(**successor)
    assert request["parameters"]["kind"] == "nonactivating-signed-code-update"
    assert request["parameters"]["previous_release_id"] == first["release_id"]
    assert request["parameters"]["previous_manifest_sha256"] == first["manifest_sha256"]
    assert request["parameters"]["identity_fingerprint"] is not None
    approval = _approve_code_request(
        args["state_path"], request, "approval:successor-code", now + timedelta(seconds=2),
    )
    receipt = publish_owner_approved_code(
        approval_id=approval.approval_id, now=now + timedelta(seconds=2), **successor,
    )
    assert receipt["release_id"] == next_manifest.release_id
    assert receipt["revision"] == 5
    assert receipt["os_service_registered"] is False
    assert args["destination"].is_dir()
    assert successor["destination"].is_dir()


def test_update_preview_rejects_non_successor_parent(scope, platform_wheels):
    args = dict(scope)
    builder = SignedReleaseBuilder(args["destination"].parent / "wrong-parent", platform_wheels)
    first_stage, _, _ = builder.stage(release_id="disposable-base", revision=4)
    args["staged_candidate"] = first_stage
    args["verifier"] = builder.verifier
    now = datetime.now(timezone.utc)
    InstallationIdentityStore(args["identity_home"]).initialize()
    request = signed_code_publication_request(**args)
    approval = _approve_code_request(args["state_path"], request, "approval:base-code", now)
    publish_owner_approved_code(approval_id=approval.approval_id, now=now, **args)

    next_stage, _, _ = builder.stage(
        release_id="disposable-wrong-parent", revision=5,
        parent_manifest_sha256="0" * 64,
    )
    rejected = {
        **args,
        "staged_candidate": next_stage,
        "destination": args["destination"].parent / "rejected-v5",
        "verifier": builder.verifier,
        "previous_destination": args["destination"],
    }
    with pytest.raises(PlatformInstallationDenied, match="direct successor"):
        signed_code_publication_request(**rejected)
