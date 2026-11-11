"""Signed offline delivery -> genuine canonical B1 stage receipt, without install.

The stock Bash extractor only stages inert ZIP members. It cannot create a
trusted B1 stage receipt. Use the existing stage_platform_release after
independently verifying the sealed outer capsule and inner Ed25519 release.
No SAFE permission, service action, Core or Fleet enrollment is created.
"""
from __future__ import annotations

from pathlib import Path

from sofia.platform.ops.platform_installation import PlatformInstallationDenied
from sofia.platform.ops.platform_installer_sealed_publication import _publisher_verifier
from sofia.platform.ops.platform_installer_verified_stage import (
    _private_file, review_staged_publisher_signed_capsule,
)
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget


def stage_sealed_capsule_for_b1(
    *, capsule: Path | str, capsule_signature: Path | str,
    staged_directory: Path | str, b1_staging_candidate: Path | str,
    trusted_public_key: Path | str, trusted_key_sha256: str,
    trusted_signer_key_id: str, expected_source_sha: str,
    expected_target: PlatformReleaseTarget, minimum_revision: int,
    expected_parent_manifest_sha256: str | None = None,
    require_local_host: bool = True,
) -> dict[str, object]:
    """Generate a real B1 stage receipt using only existing signed authority."""
    reviewed = review_staged_publisher_signed_capsule(
        capsule=capsule, capsule_signature=capsule_signature,
        staged_directory=staged_directory,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target, minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=require_local_host,
    )
    media = Path(staged_directory).absolute()
    candidate = Path(b1_staging_candidate).absolute()
    if candidate == media or media in candidate.parents:
        raise PlatformInstallationDenied("canonical B1 stage must be outside sealed media")
    root = media / "aegis"
    manifest = loads_strict_model_json(
        _private_file(root / "release-manifest.json", maximum=131072).decode("utf-8")
    )
    envelope = loads_strict_model_json(
        _private_file(root / "release-signature.json", maximum=16384).decode("utf-8")
    )
    if (type(envelope) is not dict
            or set(envelope) != {"signer_key_id", "signature_b64"}
            or envelope["signer_key_id"] != trusted_signer_key_id):
        raise PlatformInstallationDenied("canonical inner B1 signature envelope differs")
    verifier = _publisher_verifier(
        trusted_public_key, trusted_key_sha256, trusted_signer_key_id,
    )
    receipt = stage_platform_release(
        verifier=verifier, payload=manifest,
        signature_b64=envelope["signature_b64"],
        signer_key_id=trusted_signer_key_id,
        assets_root=root / "assets",
        destination=candidate,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
    )
    if (receipt.get("result") != "VERIFIED_PLATFORM_CODE_STAGED"
            or receipt.get("manifest_sha256") !=
            reviewed["inner_release"]["manifest_sha256"]):
        raise PlatformInstallationDenied("canonical B1 stage differs from sealed publisher media")
    return {
        "schema": "aegis.installer.sealed-media-b1-stage.v1",
        "result": "SIGNED_B1_CODE_STAGED_NOT_INSTALLED",
        "capsule_sha256": reviewed["capsule_sha256"],
        "delivery_index_sha256": reviewed["delivery_index_sha256"],
        "stage_receipt": receipt,
        "b1_staging_candidate": str(candidate),
        "owner_approved": False,
        "code_published": False,
        "native_service_registered": False,
        "core_activated": False,
        "fleet_enrolled": False,
    }
