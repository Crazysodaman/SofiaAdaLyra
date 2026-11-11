"""Owner-governed sealed media -> canonical B1 CODE publication.

No new release store, publisher root, approval ledger, native OS executor,
Fleet enrollment or Core activation. A signature is NOT an approval.
The first owner proof permits inert signed code publication only; starting
the installed service still requires the separate native service transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_code_install import (
    publish_owner_approved_code, signed_code_publication_request,
)
from sofia.platform.ops.platform_installer_verified_stage import (
    _private_file, review_staged_publisher_signed_capsule,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.sdk.platform_release import PlatformReleaseTarget


def _publisher_verifier(
    public_key: Path | str, fingerprint: str, signer_id: str,
) -> PlatformReleaseVerifier:
    key = _private_file(Path(public_key).absolute(), maximum=16384)
    if sha256(key).hexdigest() != fingerprint:
        raise PlatformInstallationDenied("publisher key changed after signed media review")
    return PlatformReleaseVerifier({signer_id: key})


def signed_capsule_code_publication_request(
    *, capsule: Path | str, capsule_signature: Path | str,
    staged_directory: Path | str, b1_staging_candidate: Path | str,
    trusted_public_key: Path | str, trusted_key_sha256: str,
    trusted_signer_key_id: str, expected_source_sha: str,
    expected_target: PlatformReleaseTarget, minimum_revision: int,
    destination: Path | str, identity_home: Path | str,
    state_path: Path | str, store: PlatformInstallationStore,
    expected_parent_manifest_sha256: str | None = None,
    require_local_host: bool = True,
) -> dict[str, object]:
    """Read-only owner review: independent media + B1 + durable revision floor.

    The supplied store must be the existing canonical B1 owner. No new SAFE
    owner proof is created and no executable or OS service is started.
    """
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical installed B1 store required")
    if type(minimum_revision) is not int or minimum_revision < 1:
        raise PlatformInstallationDenied("independently reviewed revision floor required")
    if store.revision_floor() > minimum_revision:
        raise PlatformInstallationDenied("publisher minimum revision below B1 durable floor")
    review = review_staged_publisher_signed_capsule(
        capsule=capsule, capsule_signature=capsule_signature,
        staged_directory=staged_directory,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=require_local_host,
    )
    verifier = _publisher_verifier(
        trusted_public_key, trusted_key_sha256, trusted_signer_key_id,
    )
    try:
        publication = signed_code_publication_request(
            staged_candidate=Path(b1_staging_candidate).absolute(),
            destination=destination, identity_home=identity_home,
            state_path=state_path, store=store,
            verifier=verifier, expected_target=expected_target,
            outer_capsule_sha256=review["capsule_sha256"],
            delivery_index_sha256=review["delivery_index_sha256"],
        )
    except FileNotFoundError as exc:
        # A verified media directory is not a genuine B1 stage receipt.
        # The separate authority-free stage_platform_release MUST create it.
        raise PlatformInstallationDenied(
            "canonical signed B1 stage receipt is missing"
        ) from exc
    if (publication["parameters"]["manifest_sha256"] !=
            review["inner_release"]["manifest_sha256"]):
        raise PlatformInstallationDenied("signed media and B1 code review diverged")
    return {
        "schema": "aegis.installer.sealed-media-code-plan.v1",
        "result": "SIGNED_CODE_APPROVAL_REQUIRED",
        "capsule_sha256": review["capsule_sha256"],
        "delivery_index_sha256": review["delivery_index_sha256"],
        "publisher_key_sha256": trusted_key_sha256,
        "release_manifest_sha256": review["inner_release"]["manifest_sha256"],
        "release_id": review["inner_release"]["release_id"],
        "code_publication": publication,
        "owner_approved": False,
        "code_published": False,
        "native_service_registered": False,
        "core_activated": False,
        "fleet_enrolled": False,
    }


def publish_owner_approved_sealed_capsule_code(
    *, approval_id: str,
    capsule: Path | str, capsule_signature: Path | str,
    staged_directory: Path | str, b1_staging_candidate: Path | str,
    trusted_public_key: Path | str, trusted_key_sha256: str,
    trusted_signer_key_id: str, expected_source_sha: str,
    expected_target: PlatformReleaseTarget, minimum_revision: int,
    destination: Path | str, identity_home: Path | str,
    state_path: Path | str, store: PlatformInstallationStore,
    expected_parent_manifest_sha256: str | None = None,
    require_local_host: bool = True,
    now: datetime | None = None,
) -> dict[str, object]:
    """Consume exact current SAFE approval, publish code through existing B1.

    Deliberately no shell exposure, service registration or automatic
    activation. If approval or publisher changes, refuse instead of installing
    unsigned bytes, creating a Core or reusing an owner permission.
    """
    if type(approval_id) is not str or not approval_id.strip():
        raise PlatformInstallationDenied("fresh exact code-publication owner approval required")
    moment = datetime.now(timezone.utc) if now is None else now
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ValueError("timezone-aware owner approval time required")
    request = signed_capsule_code_publication_request(
        capsule=capsule, capsule_signature=capsule_signature,
        staged_directory=staged_directory,
        b1_staging_candidate=b1_staging_candidate,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha, expected_target=expected_target,
        minimum_revision=minimum_revision,
        destination=destination, identity_home=identity_home,
        state_path=state_path, store=store,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=require_local_host,
    )
    verifier = _publisher_verifier(
        trusted_public_key, trusted_key_sha256, trusted_signer_key_id,
    )
    # The standard B1 publisher rechecks its own canonical candidate and
    # exact one-use SAFE approval. The outer publisher-sealed media is a
    # separate approved identity; reverify it immediately before and after
    # publication as well. A changed ZIP or delivery index cannot silently
    # inherit a previously approved code-publication receipt.
    def current_outer_review() -> None:
        fresh = review_staged_publisher_signed_capsule(
            capsule=capsule, capsule_signature=capsule_signature,
            staged_directory=staged_directory,
            trusted_public_key=trusted_public_key,
            trusted_key_sha256=trusted_key_sha256,
            trusted_signer_key_id=trusted_signer_key_id,
            expected_source_sha=expected_source_sha,
            expected_target=expected_target,
            minimum_revision=minimum_revision,
            expected_parent_manifest_sha256=expected_parent_manifest_sha256,
            require_local_host=require_local_host,
        )
        if (fresh["capsule_sha256"] != request["capsule_sha256"]
                or fresh["delivery_index_sha256"] != request["delivery_index_sha256"]
                or fresh["inner_release"]["manifest_sha256"] !=
                request["release_manifest_sha256"]):
            raise PlatformInstallationDenied(
                "publisher-sealed media changed during approved publication"
            )

    current_outer_review()
    published = publish_owner_approved_code(
        approval_id=approval_id,
        staged_candidate=Path(b1_staging_candidate).absolute(),
        destination=destination, identity_home=identity_home,
        state_path=state_path, store=store,
        verifier=verifier, expected_target=expected_target,
        now=moment,
        outer_capsule_sha256=request["capsule_sha256"],
        delivery_index_sha256=request["delivery_index_sha256"],
    )
    try:
        current_outer_review()
    except (OSError, ValueError, PermissionError) as exc:
        # B1 may have durably copied code already. Never claim a clean
        # publish result or attempt automatic rollback/identity replacement.
        raise PlatformInstallationDenied(
            "sealed media changed during code publication; reconcile B1 receipt"
        ) from exc
    if (published.get("result") != "PLATFORM_RELEASE_INSTALLED"
            or published.get("os_service_registered") is not False
            or published.get("core_activated") is not False):
        raise PlatformInstallationDenied("canonical B1 code-only receipt differs")
    return {
        **published,
        "outer_capsule_sha256": request["capsule_sha256"],
        "reviewed_inner_manifest_sha256": request["release_manifest_sha256"],
        "owner_proof_consumed": True,
        "code_published": True,
        "service_health": "UNKNOWN",
        "native_service_registered": False,
        "fleet_enrolled": False,
    }
