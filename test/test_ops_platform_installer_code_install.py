"""B1 signed code publication must consume current canonical SAFE approval."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops.platform_installation import PlatformInstallationDenied, PlatformInstallationStore
from sofia.platform.ops.platform_installer_code_install import (
    CODE_PUBLISH_CAPABILITY, publish_owner_approved_code,
    signed_code_publication_request,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
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
