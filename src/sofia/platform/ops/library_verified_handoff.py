"""D028 recipient handoff: mTLS quarantine -> independently signed B1 CAS.

Transport NEVER asserts publisher verification or installation. The canonical
Platform service supplies a separately authenticated release verifier, current
host/enrollment authorization and its canonical SAFE state. The existing
ExecutionApprovalVerifier consumes a one-use owner proof scoped to the exact
recipient, source, manifest, digest, generation and cache root BEFORE cache
mutation. No owner grant, signing key, installer or network endpoint is created.

Only Platform-release/SDK assets supported by the existing OfflineArtifactCache
are admitted here; module/model packages must use their dedicated B/D verifier.
This is an internal executor, not an exposed RPC until D028-00 is frozen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact,
)
from sofia.platform.ops.platform_library_admission import LIBRARY_PEER_CACHE_ADMIT
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import assert_no_redirected_components


def admit_signed_transferred_asset(
    *,
    transfer: PinnedChunkTransfer,
    receiver: ChunkedArtifactReceiver,
    cache: OfflineArtifactCache,
    canonical_safe_state: Path | str,
    approval_id: str,
    verify_independent_publisher: Callable[[PinnedChunkTransfer, Path], PlatformArtifact],
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    current_host_admit: Callable[[PinnedChunkTransfer], bool],
    now: datetime | None = None,
) -> dict[str, object]:
    """Admit exactly one verified asset into existing B1 CAS, never install.

    verify_independent_publisher MUST be bound to independent configured
    publisher keys, revocation and current signed manifest bytes. Never pass
    an assertion, receipt or signer name furnished by the remote peer.

    current_host_admit MUST recheck enrolled host binding, generation, SAFE,
    STOP and revocation at each checkpoint. This function is not an alternative
    authorization channel: the canonical one-use ExecutionApprovalVerifier
    still consumes the real owner proof before cache publication.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("pinned signed transfer required")
    if transfer.artifact_kind not in {"platform_release", "sdk"}:
        raise ChunkTransferRejected("artifact class requires dedicated B1/D verifier")
    if not isinstance(receiver, ChunkedArtifactReceiver):
        raise ChunkTransferRejected("canonical quarantine receiver required")
    if not isinstance(cache, OfflineArtifactCache):
        raise ChunkTransferRejected("canonical B1 cache required")
    if (not callable(verify_independent_publisher)
            or not callable(publisher_current)
            or not callable(current_host_admit)):
        raise ChunkTransferRejected("independent signer and service authority required")
    if type(approval_id) is not str or not approval_id.strip():
        raise PermissionError("exact owner cache-admission proof required")
    moment = datetime.now(timezone.utc) if now is None else now
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ValueError("timezone-aware SAFE approval time required")
    safe = Path(canonical_safe_state).absolute()
    assert_no_redirected_components(safe, include_leaf=True)

    stop = OperatorStopStore(safe)
    def current(t: PinnedChunkTransfer) -> bool:
        if t != transfer:
            return False
        if stop.current().active:
            raise PermissionError("operator STOP prohibits Library cache admission")
        if publisher_current(t) is not True:
            raise ChunkTransferRejected("publisher revoked before admission")
        if current_host_admit(t) is not True:
            raise PermissionError("current enrolled host SAFE admission denied")
        return True

    # Check current authorization before any received-byte or cache access.
    if current(transfer) is not True:
        raise PermissionError("current recipient approval unavailable")
    observed = receiver.received_bytes(transfer, authorize=current)
    if observed == transfer.size_bytes:
        complete = receiver.finalize(transfer, authorize=current)
    elif (observed == 0
            and (receiver.incoming / (transfer.content_sha256 + ".scope")).is_file()
            and (receiver.completed / transfer.content_sha256).is_file()):
        # A crash after publishing the identical inode but before clearing
        # the private transfer scope must NOT require redownloading the asset.
        # This path rechecks the original durable signed scope, whole SHA-256,
        # current owner enrollment and STOP. Publisher + one-use B1 proof are
        # independently checked again BELOW, exactly as for a new transfer.
        complete = receiver.recover_interrupted_publication(
            transfer, authorize=current,
        )
    else:
        raise ChunkTransferRejected("incomplete transfer cannot enter B1 CAS")

    # Re-verify the exact locally received bytes and independent signed root.
    # A typed object or a boolean from the Hub itself cannot satisfy this gate.
    current(transfer)
    artifact = verify_independent_publisher(transfer, complete)
    if not isinstance(artifact, PlatformArtifact):
        raise ChunkTransferRejected("independent publisher verifier did not return B1 artifact")
    if (artifact.sha256 != transfer.content_sha256
            or artifact.signature_verified is not True
            or not artifact.signer_key_id
            or cache.digest(complete) != transfer.content_sha256):
        raise ChunkTransferRejected("publisher-verified B1 content differs from transfer")
    current(transfer)

    scope = {
        "source": "ENROLLED_PEER",
        "source_platform_id": transfer.source_platform_id,
        "target_platform_id": transfer.target_platform_id,
        "content_digest": transfer.content_sha256,
        "manifest_digest": transfer.manifest_sha256,
        "artifact_kind": transfer.artifact_kind,
        "size_bytes": transfer.size_bytes,
        "generation": transfer.generation,
        "catalog_revision": transfer.catalog_revision,
        "signer_key_id": artifact.signer_key_id,
        "safe_state": str(safe),
        "cache_root": str(cache.root),
    }
    # This is the existing canonical one-use owner proof authority. If no
    # independently authenticated owner grant matches, NO cache import occurs.
    ExecutionApprovalVerifier(safe).consume(
        approval_id=approval_id, capability=LIBRARY_PEER_CACHE_ADMIT,
        parameters=scope, now=moment,
    )
    current(transfer)
    imported = cache.import_artifact(artifact, complete)
    current(transfer)
    if imported != cache.resolve(artifact):
        raise ChunkTransferRejected("B1 CAS publication did not resolve exact signed content")
    return {
        "schema": "aegis.platform.library.enrolled-peer-cache-admission.v1",
        "source": "ENROLLED_PEER",
        "target_platform_id": transfer.target_platform_id,
        "content_digest": transfer.content_sha256,
        "manifest_digest": transfer.manifest_sha256,
        "signer_key_id": artifact.signer_key_id,
        "cache_state": "CACHED_VERIFIED",
        "owner_proof_consumed": True,
        "acquisition_executed": True,
        "install_executed": False,
        "core_activated": False,
        "installed": None,
        "active": None,
    }
