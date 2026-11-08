"""Non-executable AG-D011 lifecycle plans reuse B1 owner and release stores."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
)
from sofia.platform.ops.platform_installer_lifecycle import preview_platform_lifecycle
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.test_ops_platform_installation import SignedReleaseBuilder

pytestmark = pytest.mark.pkg_ops


@pytest.fixture
def state(tmp_path, platform_wheels):
    builder = SignedReleaseBuilder(tmp_path / "build", platform_wheels)
    staged, manifest, _ = builder.stage(revision=2)
    store = PlatformInstallationStore(tmp_path / "b1.db")
    return builder, staged, manifest, store


def test_fresh_lifecycle_plan_requires_exact_signed_candidate_and_does_not_execute(state, tmp_path):
    builder, staged, manifest, store = state
    identity_home = tmp_path / "protected-identity"
    target = tmp_path / "installed"
    plan = preview_platform_lifecycle(
        operation="install", store=store, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        destination=target, identity_home=identity_home,
        staged_candidate=staged,
    )
    assert plan["manifest_sha256"] == manifest.digest
    assert plan["identity_policy"] == "NEW_ONLY_AFTER_AUTHORITY"
    assert plan["expected_checkpoint_generation"] == 0
    assert plan["executed"] is False
    assert plan["service_mutation_enabled"] is False
    assert plan["protected_state_policy"] == "RETAIN"
    assert not target.exists() and not identity_home.exists()


def test_reinstall_preview_retains_existing_protected_identity(state, tmp_path):
    builder, staged, manifest, store = state
    home = tmp_path / "protected-identity"
    original = InstallationIdentityStore(home).initialize()
    plan = preview_platform_lifecycle(
        operation="install", store=store, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        destination=tmp_path / "reinstall", identity_home=home,
        staged_candidate=staged,
    )
    assert plan["identity_policy"] == "REUSE_VERIFIED"
    assert plan["existing_identity_fingerprint"] == original.public_key_sha256
    assert InstallationIdentityStore(home).load().public_key_sha256 == original.public_key_sha256


@pytest.mark.parametrize("operation", ("update", "repair", "rollback", "uninstall"))
def test_maintenance_requires_existing_active_canonical_release(state, tmp_path, operation):
    builder, staged, manifest, store = state
    with pytest.raises(PlatformInstallationDenied, match="active release"):
        preview_platform_lifecycle(
            operation=operation, store=store, verifier=builder.verifier,
            expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
            destination=tmp_path / "installed", identity_home=tmp_path / "identity",
            staged_candidate=staged if operation in ("update", "rollback") else None,
        )


def test_installed_but_not_activated_cannot_be_implicitly_adopted(state, tmp_path):
    builder, staged, manifest, store = state
    target = tmp_path / "installed"
    receipt = install_staged_release(staged, target, store=store, verifier=builder.verifier)
    assert receipt["activated"] is False
    assert store.checkpoint().active_release_id is None
    for operation in ("install", "uninstall"):
        with pytest.raises(PlatformInstallationDenied):
            preview_platform_lifecycle(
                operation=operation, store=store, verifier=builder.verifier,
                expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
                destination=target, identity_home=tmp_path / "identity",
                staged_candidate=staged if operation == "install" else None,
            )


def test_unreconciled_attempt_blocks_all_lifecycle_preview(state, tmp_path):
    builder, staged, manifest, store = state
    store.begin_attempt(
        manifest.release_id, manifest.digest, tmp_path / "candidate",
        "install", datetime.now(timezone.utc),
    )
    with pytest.raises(PlatformInstallationDenied, match="interrupted"):
        preview_platform_lifecycle(
            operation="install", store=store, verifier=builder.verifier,
            expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
            destination=tmp_path / "installed", staged_candidate=staged,
        )


@pytest.mark.parametrize("operation", ("purge", "activate", "configure-core", "fleet-enroll"))
def test_unapproved_scope_is_not_part_of_installer_operation_plan(state, tmp_path, operation):
    builder, staged, _manifest, store = state
    with pytest.raises(PlatformInstallationDenied, match="unsupported"):
        preview_platform_lifecycle(
            operation=operation, store=store, verifier=builder.verifier,
            expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
            destination=tmp_path / "installed", staged_candidate=staged,
        )
