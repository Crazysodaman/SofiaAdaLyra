"""D028 recipient pipeline: exact selected peer bytes -> signed cache admission.

Internal Platform service orchestration, not an exposed network or UI API.
The selected publisher-signed transfer, current enrolled mTLS connector,
current SAFE/STOP scopes, independent B1 release verifier and one-use owner
proof ALL originate from the canonical installed service. A Hub never supplies
any of them. Installation and activation are separate later operations.

A bounded transfer may legitimately end partially: this is reported as
RECEIVING with zero verified bytes. A caller can explicitly resume with the
returned offset and the same signed transfer and enrolled certificate pin.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ssl
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import MAX_CHUNK
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks
from sofia.platform.ops.library_verified_handoff import admit_signed_transferred_asset
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact


def acquire_selected_signed_platform_asset(
    *,
    transfer: PinnedChunkTransfer,
    receiver: ChunkedArtifactReceiver,
    cache: OfflineArtifactCache,
    open_enrolled_tls: Callable[[], ssl.SSLSocket],
    expected_peer_certificate_sha256: str,
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    current_host_admit: Callable[[PinnedChunkTransfer], bool],
    verify_independent_publisher: Callable[[PinnedChunkTransfer, Path], PlatformArtifact],
    canonical_safe_state: Path | str,
    approval_id: str,
    start_offset: int = 0,
    chunk_bytes: int = MAX_CHUNK,
    max_chunks: int = 128,
    now: datetime | None = None,
) -> dict[str, object]:
    """Run one bounded acquisition attempt, fail closed on missing authority.

    No automatic retry, hidden WAN fallback, installer call, Core startup,
    receipt fabrication, or garbage collection. Do not call this outside the
    service until owner-approved D028-00 authenticated wire contracts exist.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("selected signed transfer is required")
    if transfer.artifact_kind not in {"platform_release", "sdk"}:
        raise ChunkTransferRejected("selected artifact uses separate module/model pipeline")
    if not isinstance(receiver, ChunkedArtifactReceiver) or not isinstance(cache, OfflineArtifactCache):
        raise ChunkTransferRejected("canonical recipient stores required")
    if not callable(current_host_admit) or current_host_admit(transfer) is not True:
        raise PermissionError("current SAFE/STOP enrolled recipient denied")
    if not callable(publisher_current) or publisher_current(transfer) is not True:
        raise ChunkTransferRejected("signed publisher is not current")

    received = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver,
        open_enrolled_tls=open_enrolled_tls,
        expected_peer_certificate_sha256=expected_peer_certificate_sha256,
        authorize_peer=authorize_peer, publisher_current=publisher_current,
        chunk_bytes=chunk_bytes, max_chunks=max_chunks,
        start_offset=start_offset,
    )
    if received < transfer.size_bytes:
        # Bytes are present only in quarantine; do not claim independent
        # signed verification, B1 cache receipt, or installed state.
        return {
            "schema": "aegis.platform.library.recipient-progress.v1",
            "content_digest": transfer.content_sha256,
            "manifest_digest": transfer.manifest_sha256,
            "source_platform_id": transfer.source_platform_id,
            "target_platform_id": transfer.target_platform_id,
            "catalog_revision": transfer.catalog_revision,
            "received_bytes": received,
            "verified_bytes": 0,
            "total_bytes": transfer.size_bytes,
            "cache_state": "CACHED_UNVERIFIED",
            "install_executed": False,
            "installed": None,
            "active": None,
            "owner_proof_consumed": False,
        }
    if received != transfer.size_bytes:
        raise ChunkTransferRejected("transfer exceeded signed selected content")
    admission = admit_signed_transferred_asset(
        transfer=transfer, receiver=receiver, cache=cache,
        canonical_safe_state=canonical_safe_state, approval_id=approval_id,
        verify_independent_publisher=verify_independent_publisher,
        publisher_current=publisher_current,
        current_host_admit=current_host_admit,
        now=now,
    )
    return {
        **admission,
        "received_bytes": received,
        "verified_bytes": received,
        "total_bytes": transfer.size_bytes,
        "source_platform_id": transfer.source_platform_id,
        "catalog_revision": transfer.catalog_revision,
    }
