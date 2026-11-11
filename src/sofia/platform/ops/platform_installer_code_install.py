"""Owner-governed code-only Platform release publication using the B1 engine.

This intentionally does not register/start services. It is NOT the OS installer.
It does not alter Team A IPC or create any second approval or receipt store:
the existing SAFE approval verifier and B1 installation store remain owners.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
    verify_staged_release_candidate,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.platform_release import PlatformReleaseTarget

# Provisional internal B1 code-publication capability. Team A must approve
# the final versioned authenticated IPC before any CLI/native service routing.
CODE_PUBLISH_CAPABILITY = "platform.install_verified_code"


def signed_code_publication_request(
    *,
    staged_candidate: Path | str,
    destination: Path | str,
    identity_home: Path | str,
    state_path: Path | str,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    outer_capsule_sha256: str | None = None,
    delivery_index_sha256: str | None = None,
) -> dict[str, object]:
    """Return a fingerprintable immutable plan, never an approval."""
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("existing B1 installation store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("trusted canonical verifier required")
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("exact typed release target required")
    if (outer_capsule_sha256 is None) != (delivery_index_sha256 is None):
        raise PlatformInstallationDenied(
            "reviewed outer capsule and delivery index must be bound together"
        )
    for value in (outer_capsule_sha256, delivery_index_sha256):
        if value is not None and (
            type(value) is not str
            or re.fullmatch(r"[0-9a-f]{64}", value) is None
        ):
            raise PlatformInstallationDenied("canonical reviewed capsule SHA-256 required")
    dest = Path(destination).absolute()
    state = Path(state_path).absolute()
    identity = Path(identity_home).absolute()
    for path in (dest, state, identity):
        assert_no_redirected_components(path, include_leaf=True)
    if dest.exists() or store.receipt_for_destination(dest) is not None:
        raise PlatformInstallationDenied("destination occupied; never adopt or overwrite")
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled publication attempt")
    checkpoint = store.checkpoint()
    if checkpoint is not None and checkpoint.active_release_id is not None:
        raise PlatformInstallationDenied("active release replacement requires separate governed update")
    if identity.exists():
        fingerprint = InstallationIdentityStore(identity).load().public_key_sha256
    else:
        fingerprint = None
    candidate = verify_staged_release_candidate(
        staged_candidate, verifier=verifier,
        minimum_revision=max(1, store.revision_floor()),
    )
    if candidate.manifest.target != expected_target:
        raise PlatformInstallationDenied("signed release target differs from request")
    parameters = {
        "release_id": candidate.release_id,
        "revision": candidate.revision,
        "manifest_sha256": candidate.manifest_sha256,
        "source_sha": candidate.source_sha,
        "target": expected_target.value,
        "staging_path": str(candidate.staging_path),
        "destination": str(dest),
        "state_path": str(state),
        "identity_home": str(identity),
        "identity_fingerprint": fingerprint,
        "checkpoint_generation": checkpoint.generation if checkpoint else 0,
        "minimum_accepted_revision": store.revision_floor(),
        "kind": "nonactivating-signed-code-only",
    }
    if outer_capsule_sha256 is not None:
        # Reviewed outer media must be approved along with inner B1 bytes.
        # These SHA values are only a scope; they are not signature proof.
        parameters["outer_capsule_sha256"] = outer_capsule_sha256
        parameters["delivery_index_sha256"] = delivery_index_sha256
    return {
        "schema": "aegis.platform.code-publication-request.v1",
        "capability": CODE_PUBLISH_CAPABILITY,
        "parameters": parameters,
        "fingerprint": execution_fingerprint(CODE_PUBLISH_CAPABILITY, parameters),
        "authorized": False,
        "executed": False,
    }


def publish_owner_approved_code(
    *,
    approval_id: str,
    staged_candidate: Path | str,
    destination: Path | str,
    identity_home: Path | str,
    state_path: Path | str,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    now: datetime | None = None,
    outer_capsule_sha256: str | None = None,
    delivery_index_sha256: str | None = None,
) -> dict[str, object]:
    """Consume one exact current owner grant, then call canonical B1 publisher.

    The supplied verifier must originate inside a trusted installed Platform,
    NOT from the downloadable bundle or a user-controlled key. Team A's IPC
    and enrollment boundary is intentionally not wired into shell launchers.
    """
    if not isinstance(approval_id, str) or not approval_id.strip():
        raise PlatformInstallationDenied("fresh scoped owner approval is mandatory")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("time must be timezone aware")
    state = Path(state_path).absolute()
    if OperatorStopStore(state).current().active:
        raise PlatformInstallationDenied("operator STOP is active")
    request = signed_code_publication_request(
        staged_candidate=staged_candidate, destination=destination,
        identity_home=identity_home, state_path=state, store=store,
        verifier=verifier, expected_target=expected_target,
        outer_capsule_sha256=outer_capsule_sha256,
        delivery_index_sha256=delivery_index_sha256,
    )
    ExecutionApprovalVerifier(state).consume(
        approval_id=approval_id,
        capability=request["capability"],
        parameters=request["parameters"],
        now=current,
    )
    # Approval consumption does not freeze filesystem bytes, STOP, revocation
    # or B1 generation; verify again after the SAFE transaction and before
    # doing any publication. A failed recheck burns the one-use approval.
    if OperatorStopStore(state).current().active:
        raise PlatformInstallationDenied("STOP changed before code publication")
    if not ExecutionApprovalVerifier(state).consumed_owner_proof_remains_current(
        approval_id=approval_id, capability=request["capability"],
        parameters=request["parameters"],
    ):
        raise PlatformInstallationDenied(
            "owner authentication revoked before code publication"
        )
    observed = signed_code_publication_request(
        staged_candidate=staged_candidate, destination=destination,
        identity_home=identity_home, state_path=state, store=store,
        verifier=verifier, expected_target=expected_target,
        outer_capsule_sha256=outer_capsule_sha256,
        delivery_index_sha256=delivery_index_sha256,
    )
    if observed["fingerprint"] != request["fingerprint"]:
        raise PlatformInstallationDenied("release or generation changed after approval")
    receipt = install_staged_release(
        staged_candidate, destination, store=store, verifier=verifier,
        minimum_revision=max(1, store.revision_floor()),
    )
    # A signed copy may finish after an attended owner revokes a credential
    # or activates STOP. Never report a clean success in that race. The B1
    # durable installation receipt remains for explicit host reconciliation.
    if (OperatorStopStore(state).current().active
            or not ExecutionApprovalVerifier(state).consumed_owner_proof_remains_current(
                approval_id=approval_id, capability=request["capability"],
                parameters=request["parameters"],
            )):
        raise PlatformInstallationDenied(
            "owner authority changed during code publication; reconcile B1 receipt"
        )
    return {
        **receipt,
        "owner_proof_consumed": True,
        "os_service_registered": False,
        "service_health_verified": False,
        "core_activated": False,
        "fleet_enrolled": False,
    }
