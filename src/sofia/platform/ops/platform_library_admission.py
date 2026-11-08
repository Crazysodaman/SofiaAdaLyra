"""D028-02 internal signed-seed -> existing OfflineArtifactCache admission.

One cache, one canonical PlatformReleaseVerifier, one B1 installation store.
This is NOT an independently published catalog protocol (Team A's D028-00
contract is still proposed), Hub listener, peer transport or installer.

Acquisition, installed code and running service are separate authorities.
No GUI, CLI or Hub calls these methods until Team A freezes authentication
and current SAFE owner scope. Cache admission burns an exact one-use local
owner approval but NEVER grants B1 install, Core activation or model loading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import re
import stat

from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from sofia.platform.ops.platform_installation import (
    PlatformInstallationStore, verify_installed,
)
from sofia.platform.ops.platform_installer_offline_seed import (
    review_core_free_offline_seed,
)
from sofia.platform.ops.platform_installer_bundle import host_release_target
from sofia.platform.ops.platform_release import (
    PlatformReleaseRejected, PlatformReleaseVerifier,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget

# Internal candidate capability. Team A must approve the final versioned
# operation before any client, Hub or externally callable service uses it.
LIBRARY_CACHE_ADMIT = "platform.library.cache_admit_verified_seed"


def _verified_seed(bundle_root, *, trusted_public_key, trusted_key_sha256,
                   trusted_signer_key_id, expected_source_sha, expected_target,
                   minimum_revision, require_local_host):
    base = Path(bundle_root).absolute()
    assert_no_redirected_components(base, include_leaf=True)
    review = review_core_free_offline_seed(
        base, trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha, expected_target=expected_target,
        minimum_revision=minimum_revision,
        require_local_host=require_local_host,
        source_kind="offline_media",
    )
    manifest_path = base / "release-manifest.json"
    size = manifest_path.stat(follow_symlinks=False).st_size
    manifest = PlatformReleaseManifest.from_payload(
        loads_strict_model_json(read_artifact_file(
            manifest_path, size, include_data=True,
        )[1].decode("utf-8"))
    )
    if manifest.digest != review["manifest_sha256"]:
        raise PlatformReleaseRejected("signed cache candidate changed before inspection")
    return base, manifest, review


def _asset_for_digest(manifest, sha256_digest):
    if type(sha256_digest) is not str or len(sha256_digest) != 64:
        raise PlatformReleaseRejected("pinned asset digest required")
    candidates = [
        item for item in manifest.assets
        if item.reference.sha256 == sha256_digest
    ]
    if len(candidates) != 1:
        raise PlatformReleaseRejected(
            "requested digest not uniquely selected in signed release"
        )
    item = candidates[0]
    if item.kind not in (
        "sdk", "platform", "service", "python-runtime",
        "dependency-lock", "sbom", "provenance", "dependency",
    ):
        raise PlatformReleaseRejected("optional Core/model assets prohibited in seed cache")
    return item


def preview_signed_seed_cache(
    *,
    bundle_root: Path | str,
    cache: OfflineArtifactCache,
    store: PlatformInstallationStore,
    trusted_public_key: Path | str,
    trusted_key_sha256: str,
    trusted_signer_key_id: str,
    expected_source_sha: str,
    expected_target: PlatformReleaseTarget,
    minimum_revision: int,
    requested_asset_sha256: str,
    require_local_host: bool = True,
) -> dict[str, object]:
    """Fresh signed review and truthful cache/B1 state, never a Hub assertion."""
    if not isinstance(cache, OfflineArtifactCache):
        raise TypeError("existing Platform OfflineArtifactCache required")
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 store required")
    root, manifest, trusted = _verified_seed(
        bundle_root,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        require_local_host=require_local_host,
    )
    asset = _asset_for_digest(manifest, requested_asset_sha256)
    platform = (
        PlatformKind.WINDOWS if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
        else PlatformKind.LINUX
    )
    ref = asset.reference
    package = PlatformArtifact(
        artifact_id=manifest.release_id, version=manifest.version,
        platform=platform, architecture="x86_64",
        sha256=ref.sha256, signer_key_id=trusted_signer_key_id,
        signature_verified=True, source="verified-local-offline-media",
    )
    present = False
    try:
        cached_path = cache.resolve(package)
        present = cached_path.is_file()
    except FileNotFoundError:
        pass
    installed = None
    row = store.receipt_for_release(manifest.release_id)
    if row is not None and row["manifest_sha256"] == manifest.digest:
        # Never accept a Hub catalog row or a self-asserted receipt as install.
        verified = verify_installed(
            row["destination"], store=store,
            verifier=PlatformReleaseVerifier({
                trusted_signer_key_id: Path(trusted_public_key).read_bytes(),
            }),
        )
        installed = bool(verified["manifest_sha256"] == manifest.digest)
    # A durable installed/activated receipt does not prove the OS service is
    # healthy *now*. ACTIVE remains UNKNOWN without Team A's live observation.
    return {
        "schema": "aegis.platform.library.local-cache-review.v1",
        "release_id": manifest.release_id,
        "asset_kind": asset.kind,
        "artifact_digest": ref.sha256,
        "artifact_size_bytes": ref.size_bytes,
        "manifest_sha256": manifest.digest,
        "signer_key_id": trusted_signer_key_id,
        "signed_release_verified": True,
        "cache_state": "CACHED_VERIFIED" if present else "MISSING",
        "installed": installed,
        "active": None,
        "active_observation": "NOT_OBSERVED",
        "internet_enabled": False,
        "source": "OFFLINE_MEDIA",
        "current_owner_authorized": False,
        "acquisition_executed": False,
        "install_executed": False,
        "core_activated": False,
    }


def admit_signed_seed_asset_with_owner_proof(
    *, approval_id: str, canonical_safe_state: Path | str,
    bundle_root: Path | str, cache: OfflineArtifactCache,
    store: PlatformInstallationStore, trusted_public_key: Path | str,
    trusted_key_sha256: str, trusted_signer_key_id: str,
    expected_source_sha: str, expected_target: PlatformReleaseTarget,
    minimum_revision: int, requested_asset_sha256: str,
    now: datetime | None = None,
) -> dict[str, object]:
    """Internal SAFE-fenced immutable byte import; no install/activation."""
    if not isinstance(approval_id, str) or not approval_id.strip():
        raise PermissionError("current exact cache-acquisition approval is mandatory")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("timezone-aware owner proof time required")
    if host_release_target() is not expected_target:
        raise PlatformReleaseRejected("target differs from actual local host")
    safe = Path(canonical_safe_state).absolute()
    assert_no_redirected_components(safe, include_leaf=True)
    if OperatorStopStore(safe).current().active:
        raise PermissionError("STOP prohibits new artifact acquisition")
    plan = preview_signed_seed_cache(
        bundle_root=bundle_root, cache=cache, store=store,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        requested_asset_sha256=requested_asset_sha256,
        require_local_host=True,
    )
    selected = dict(
        release_id=plan["release_id"],
        manifest_sha256=plan["manifest_sha256"],
        asset_sha256=plan["artifact_digest"],
        asset_size_bytes=plan["artifact_size_bytes"],
        target=expected_target.value,
        source="OFFLINE_MEDIA",
        state=str(safe),
        cache_root=str(cache.root),
        b1_receipts=str(store.path),
    )
    ExecutionApprovalVerifier(safe).consume(
        approval_id=approval_id, capability=LIBRARY_CACHE_ADMIT,
        parameters=selected, now=current,
    )
    if OperatorStopStore(safe).current().active:
        raise PermissionError("STOP engaged after approval consumed")
    repeated = preview_signed_seed_cache(
        bundle_root=bundle_root, cache=cache, store=store,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        requested_asset_sha256=requested_asset_sha256,
    )
    if any(repeated[k] != plan[k] for k in (
        "release_id", "manifest_sha256", "artifact_digest",
        "artifact_size_bytes", "signer_key_id",
    )):
        raise PlatformReleaseRejected("signed selected artifact changed after approval")
    root, manifest, _trust = _verified_seed(
        bundle_root, trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        require_local_host=True,
    )
    asset = _asset_for_digest(manifest, requested_asset_sha256)
    ref = asset.reference
    source_file = root / "assets" / ref.path
    platform = (
        PlatformKind.WINDOWS if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
        else PlatformKind.LINUX
    )
    selected_artifact = PlatformArtifact(
        artifact_id=manifest.release_id, version=manifest.version,
        platform=platform, architecture="x86_64",
        sha256=ref.sha256, signer_key_id=trusted_signer_key_id,
        signature_verified=True, source="verified-local-offline-media",
    )
    cache.import_artifact(selected_artifact, source_file)
    if OperatorStopStore(safe).current().active:
        # Immutable bytes may have been safely imported, but the receipt must
        # not assert an authorized completed acquisition after revocation.
        raise PermissionError("STOP during acquisition: reconcile cached bytes")
    return {
        **repeated,
        "cache_state": "CACHED_VERIFIED",
        "acquisition_executed": True,
        "owner_proof_consumed": True,
        "install_executed": False,
        "active": None,
        "core_activated": False,
    }


def preview_signed_cache_retention(
    *, bundle_root: Path | str,
    cache: OfflineArtifactCache, store: PlatformInstallationStore,
    trusted_public_key: Path | str, trusted_key_sha256: str,
    trusted_signer_key_id: str, expected_source_sha: str,
    expected_target: PlatformReleaseTarget, minimum_revision: int,
    requested_asset_sha256: str, require_local_host: bool = True,
) -> dict[str, object]:
    """Read-only D028-05 storage, verified-space and conservative pin review.

    There is no safe GC without Team A's one-use retention authority AND
    Team D's full dependency/active/rollback graph. All deletion is blocked.
    Never mistake an unrecognized byte blob or leftover partial for a
    verified and unpinned CAS object.
    """
    review = preview_signed_seed_cache(
        bundle_root=bundle_root, cache=cache, store=store,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        requested_asset_sha256=requested_asset_sha256,
        require_local_host=require_local_host,
    )
    cache._check_root()
    bytes_used = 0
    count = 0
    unknown = False
    for entry in cache.root.iterdir():
        assert_no_redirected_components(entry, include_leaf=True)
        metadata = entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise PermissionError("offline cache contains non-regular object")
        if (not re.fullmatch(r"[0-9a-f]{64}", entry.name)
                or metadata.st_nlink != 1
                or metadata.st_size > 512 * 1024**2):
            unknown = True
            continue
        if cache.digest(entry) != entry.name:
            raise PlatformReleaseRejected("signed local cache contains changed object bytes")
        bytes_used += metadata.st_size
        count += 1
        if count > 4096:
            raise PermissionError("offline cache exceeds bounded object inventory")
    if bytes_used > cache.max_bytes:
        raise PermissionError("offline cache used space exceeds configured quota")
    historical = any(
        item["manifest_sha256"] == review["manifest_sha256"]
        and item["result"] == "SUCCEEDED" for item in store.history()
    )
    return {
        "schema": "aegis.platform.library.retention-review.v1",
        "source": "EXISTING_OFFLINE_ARTIFACT_CACHE",
        "max_bytes": cache.max_bytes,
        "verified_object_count": count,
        "verified_bytes_used": bytes_used,
        "quota_bytes_remaining": cache.max_bytes - bytes_used,
        "unrecognized_cache_entry": unknown,
        "asset_cached_verified": review["cache_state"] == "CACHED_VERIFIED",
        "installed": review["installed"],
        "active": None,
        "historical_signed_install_reference": historical,
        "pin_policy": (
            "PRESERVE_B1_HISTORY" if historical else "UNKNOWN_DEPENDENCY_GRAPH"
        ),
        "gc_permitted": False,
        "gc_denial": "OWNER_RETENTION_AUTHORITY_AND_PIN_GRAPH_UNFROZEN",
        "deletion_executed": False,
        "owner_approved": False,
    }
