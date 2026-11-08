"""AG-D011 version-fenced, non-executable Platform lifecycle review.

This is one presentation adapter over the canonical B1 installation store
and signed release verifier, not a new installation engine or authorization
store. Real native SCM/systemd changes must be performed by a separately
reviewed, currently authenticated Team A service executor. Nothing here may
execute protected mutations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
    verify_installed, verify_staged_release_candidate,
)
from sofia.platform.ops.platform_installer_preview import (
    preview_signed_platform_install,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.platform_release import PlatformReleaseTarget

LifecycleOperation = Literal["install", "update", "repair", "rollback", "uninstall"]


def preview_platform_lifecycle(
    *,
    operation: LifecycleOperation,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    destination: Path | str,
    identity_home: Path | str | None = None,
    staged_candidate: Path | str | None = None,
) -> dict[str, object]:
    """Read existing B1 state and exact signed code before showing any plan.

    A stale review is never a grant: execution MUST reverify signature,
    current STOP, enrollment/revocation, owner approval and generation under
    native OS service ownership. Uninstall retains protected identity/state;
    purge is intentionally not supported by this entrypoint.
    """
    if operation not in ("install", "update", "repair", "rollback", "uninstall"):
        raise PlatformInstallationDenied("unsupported or destructive lifecycle operation")
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 installation store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("trusted canonical release verifier required")
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("typed release target required")
    target = Path(destination).absolute()
    assert_no_redirected_components(target, include_leaf=True)
    checkpoint = store.checkpoint()
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled interrupted attempt; deny lifecycle")
    generation = checkpoint.generation if checkpoint is not None else 0
    floor = checkpoint.minimum_accepted_revision if checkpoint is not None else 0

    if operation == "install":
        if checkpoint is not None:
            raise PlatformInstallationDenied("an existing Platform must not be installed twice")
        if staged_candidate is None:
            raise PlatformInstallationDenied("signed staged candidate required")
        if identity_home is not None:
            home = Path(identity_home).absolute()
            assert_no_redirected_components(home, include_leaf=True)
            if home.exists():
                # Reinstall after governed removal requires existing identity to
                # be validated, never silently created or rekeyed.
                identity = InstallationIdentityStore(home).load()
                fingerprint = identity.public_key_sha256
            else:
                fingerprint = None
        else:
            fingerprint = None
        plan = preview_signed_platform_install(
            staging_path=staged_candidate, destination=target, store=store,
            verifier=verifier, expected_target=expected_target,
        )
        return {
            **plan,
            "operation": operation,
            "identity_policy": "REUSE_VERIFIED" if fingerprint else "NEW_ONLY_AFTER_AUTHORITY",
            "existing_identity_fingerprint": fingerprint,
            "expected_checkpoint_generation": generation,
            "protected_state_policy": "RETAIN",
            "service_mutation_enabled": False,
        }

    if checkpoint is None or checkpoint.active_release_id is None:
        raise PlatformInstallationDenied("existing active release required before maintenance")
    row = store.receipt_for_release(checkpoint.active_release_id)
    if row is None:
        raise PlatformInstallationDenied("active release has no canonical B1 receipt")
    if Path(row["destination"]).absolute() != target:
        raise PlatformInstallationDenied("destination does not match canonical active release")
    installed = verify_installed(target, store=store, verifier=verifier)
    if identity_home is None:
        raise PlatformInstallationDenied("existing identity home required for maintenance")
    home = Path(identity_home).absolute()
    assert_no_redirected_components(home, include_leaf=True)
    identity = InstallationIdentityStore(home).load()

    candidate_digest = None
    candidate_release_id = None
    candidate_revision = None
    if operation in ("update", "rollback"):
        if staged_candidate is None:
            raise PlatformInstallationDenied("signed candidate required for release change")
        candidate = verify_staged_release_candidate(
            staged_candidate, verifier=verifier, minimum_revision=1,
        )
        if candidate.manifest.target != expected_target:
            raise PlatformInstallationDenied("release target differs from host")
        candidate_digest = candidate.manifest_sha256
        candidate_release_id = candidate.release_id
        candidate_revision = candidate.revision
        if operation == "update":
            if candidate.revision <= floor:
                raise PlatformInstallationDenied("update must advance durable revision floor")
            if candidate.manifest.parent_manifest_sha256 != row["manifest_sha256"]:
                raise PlatformInstallationDenied("update predecessor is not active release")
        else:
            if candidate.revision >= row["revision"]:
                raise PlatformInstallationDenied("rollback must target an older release")
            # B1 rollback semantics demand exact previously attested bytes and
            # separately approved rollback. A historical release is NOT an
            # owner grant or evidence that it is currently safe.
            historical = any(
                item["release_id"] == candidate.release_id
                and item["manifest_sha256"] == candidate.manifest_sha256
                and item["result"] == "SUCCEEDED"
                for item in store.history()
            )
            if not historical:
                raise PlatformInstallationDenied("rollback candidate not in verified history")
    if operation in ("repair", "uninstall") and staged_candidate is not None:
        raise PlatformInstallationDenied("maintenance must not silently switch signed releases")

    return {
        "schema": "aegis.platform.installer-plan.v1",
        "status": "SIGNED_CANDIDATE_REVIEW_ONLY",
        "operation": operation,
        "current_release_id": row["release_id"],
        "current_manifest_sha256": row["manifest_sha256"],
        "candidate_release_id": candidate_release_id,
        "candidate_manifest_sha256": candidate_digest,
        "candidate_revision": candidate_revision,
        "minimum_accepted_revision": floor,
        "expected_checkpoint_generation": generation,
        "target": expected_target.value,
        "destination": str(target),
        "identity_policy": "RETAIN_EXACT",
        "existing_identity_fingerprint": identity.public_key_sha256,
        "protected_state_policy": "RETAIN",
        "service_mutation_enabled": False,
        "requires_fresh_owner_approval": True,
        "requires_current_stop_revocation_recheck": True,
        "native_os_service_health_verified": False,
        "executed": False,
        "owner_approved": False,
        "production_authorized": False,
    }
