"""B-002 signed predecessor lineage and governed native update/rollback.

All signatures and SAFE grants are synthetic and disposable. OS effects use
a simulated backend. This is NOT installed-host acceptance evidence.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
)
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.platform.ops.platform_installer_native_service import DebianSystemdNativeService
from sofia.platform.ops.platform_installer_native_transaction import (
    apply_owner_approved_native_service, native_service_operation_request,
)
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision

pytestmark = pytest.mark.pkg_ops


@pytest.fixture
def signed_versions(tmp_path, platform_wheels, canonical_state_path):
    builder = SignedReleaseBuilder(tmp_path / "builder", platform_wheels)
    first_stage, first_manifest, _ = builder.stage(
        release_id="signed-v5", revision=5,
    )
    store = PlatformInstallationStore(tmp_path / "b1.db")
    first = tmp_path / "release-v5"
    install_staged_release(first_stage, first, store=store, verifier=builder.verifier)
    identity_store, _current, state = provision(tmp_path / "host")
    base = dict(
        store=store,
        verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        identity_home=identity_store.home,
        local_state=state,
        canonical_safe_state=canonical_state_path,
    )
    return builder, first_manifest, first, base, tmp_path


def _successor(builder, predecessor_digest):
    _stage, manifest, _ = builder.stage(
        release_id="signed-v6", revision=6,
    )
    signed = replace(manifest, parent_manifest_sha256=predecessor_digest)
    sig = b64encode(builder._key.sign(signed.digest.encode("ascii"))).decode("ascii")
    new_stage = builder.root / "staged-v6-with-parent"
    stage_platform_release(
        verifier=builder.verifier,
        payload=signed.to_payload(),
        signature_b64=sig,
        signer_key_id=builder.signer_key_id,
        assets_root=builder.root / "assets-signed-v6-r6",
        destination=new_stage,
        expected_source_sha=signed.source_sha,
        expected_target=signed.target,
        minimum_revision=1,
        expected_parent_manifest_sha256=predecessor_digest,
    )
    return new_stage, signed


def _grant(scope, label):
    now = datetime.now(timezone.utc)
    request = native_service_operation_request(**scope)
    approval = ExecutionApproval(
        approval_id=label, capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(scope["canonical_safe_state"]), approval,
    )
    return approval.approval_id, now


def _backend():
    driver = DebianSystemdNativeService()
    calls = []

    def result(operation, candidate):
        calls.append((operation, candidate.release_id, candidate.platform_id))
        return {
            "schema": "aegis.native-service-receipt.v1",
            "service": candidate.service_name,
            "process_state": "REMOVED" if operation == "unregister" else "RUNNING",
            "platform_id": candidate.platform_id,
            "release_manifest_sha256": candidate.manifest_sha256,
            "core_activated": False, "service_health": "UNKNOWN",
        }

    driver.register = lambda candidate: result("register", candidate)
    driver.restart_verified = lambda candidate: result("repair", candidate)
    driver.replace_verified = lambda old, candidate: result("switch", candidate)
    driver.stop_and_unregister = lambda candidate: result("unregister", candidate)
    return driver, calls


def test_b1_accepts_valid_signed_predecessor_but_not_unhistoried_one(signed_versions):
    builder, first_manifest, first, base, tmp = signed_versions
    staging, signed = _successor(builder, first_manifest.digest)
    second = tmp / "release-v6"
    install_staged_release(staging, second, store=base["store"], verifier=builder.verifier)
    assert base["store"].receipt_for_destination(second)["manifest_sha256"] == signed.digest
    assert base["store"].revision_floor() == 6


def test_native_register_update_repair_approved_rollback_and_remove(signed_versions):
    builder, first_manifest, first, base, tmp = signed_versions
    staging, signed = _successor(builder, first_manifest.digest)
    second = tmp / "release-v6"
    install_staged_release(staging, second, store=base["store"], verifier=builder.verifier)
    backend, calls = _backend()

    def execute(scope, label):
        approval_id, moment = _grant(scope, label)
        return apply_owner_approved_native_service(
            **scope, approval_id=approval_id, now=moment, backend=backend,
        )

    original = dict(base, operation="register", destination=first)
    first_result = execute(original, "approval:d028-native-initial")
    assert first_result["process_state"] == "RUNNING"

    update = dict(base, operation="update", destination=second, previous_destination=first)
    updated = execute(update, "approval:d028-native-update")
    assert updated["release_manifest_sha256"] == signed.digest

    repair = dict(base, operation="repair", destination=second)
    repaired = execute(repair, "approval:d028-native-repair")
    assert repaired["process_state"] == "RUNNING"

    rollback = dict(base, operation="rollback", destination=first, previous_destination=second)
    restored = execute(rollback, "approval:d028-native-rollback")
    assert restored["release_manifest_sha256"] == first_manifest.digest

    uninstall = dict(base, operation="unregister", destination=first)
    removed = execute(uninstall, "approval:d028-native-remove")
    assert removed["process_state"] == "REMOVED"
    assert [call[0] for call in calls] == [
        "register", "switch", "repair", "switch", "unregister",
    ]
    assert len(set(call[2] for call in calls)) == 1
    assert base["store"].revision_floor() == 6  # no rollback floor downgrade


def test_update_rejects_wrong_signed_predecessor_before_os_effect(signed_versions):
    builder, first_manifest, first, base, tmp = signed_versions
    staging, signed = _successor(builder, "f" * 64)
    with pytest.raises(PlatformInstallationDenied, match="predecessor"):
        install_staged_release(
            staging, tmp / "bad-release", store=base["store"],
            verifier=builder.verifier,
        )
    assert not (tmp / "bad-release").exists()
