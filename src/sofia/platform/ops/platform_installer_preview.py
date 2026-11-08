"""Signed Platform installer plan preview with no authority or filesystem writes.

Install/repair/rollback execution belongs to PlatformInstallationStore and
the owner-approved OS service executor. This function is a non-executable,
revalidated preflight preview for CLI/TUI/GUI. Do not treat it as a grant.
"""
from __future__ import annotations

from pathlib import Path

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
    verify_staged_release_candidate,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.platform_release import PlatformReleaseTarget


def preview_signed_platform_install(*, staging_path, destination, store,
                                    verifier, expected_target) -> dict[str, object]:
    """Inspect exact signed release, target, revision floor and destination.

    Return an advisory *read-only* plan, never an activation permit. The
    executor must independently reverify the signature, bytes, checkpoint,
    current owner authorization and OS service state at execution time.
    """
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("existing Platform installation receipt store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("configured signed release verifier required")
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("typed exact operating-system target required")
    destination = Path(destination).absolute()
    assert_no_redirected_components(destination, include_leaf=True)
    if destination.exists() or store.receipt_for_destination(destination) is not None:
        raise FileExistsError("installation preview refuses occupied target")
    floor = max(1, store.revision_floor())
    candidate = verify_staged_release_candidate(
        staging_path, verifier=verifier, minimum_revision=floor,
    )
    if candidate.manifest.target != expected_target:
        raise PlatformInstallationDenied("signed Platform target does not match reviewed host")
    checkpoint = store.checkpoint()
    return {
        "schema": "aegis.platform.installer-plan.v1",
        "status": "SIGNED_CANDIDATE_REVIEW_ONLY",
        "release_id": candidate.release_id,
        "revision": candidate.revision,
        "manifest_sha256": candidate.manifest_sha256,
        "source_sha": candidate.source_sha,
        "target": expected_target.value,
        "destination": str(destination),
        "checkpoint_generation": 0 if checkpoint is None else checkpoint.generation,
        "minimum_accepted_revision": floor,
        "intended_steps": [
            "independently-reverify-staged-release",
            "publish-verified-release",
            "register-reviewed-native-os-service",
            "activate-with-fresh-owner-permission",
            "verify-installed-host-receipts",
        ],
        "core_required": False,
        "executed": False,
        "owner_approved": False,
        "os_service_registered": False,
        "production_authorized": False,
    }
