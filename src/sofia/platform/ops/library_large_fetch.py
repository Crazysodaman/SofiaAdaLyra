"""D028-05 large object fetch with independently publisher-signed chunk layout.

Runs strictly inside the installed service, with existing SAFE/STOP, mTLS
enrollment and quota authority. No new LAN listener, signer, owner approval,
direct filesystem cache publication, Core activation or model loading.

The signed parent binds each bounded chunk SHA and final whole-object SHA.
Receiver.finalize separately verifies the final digest after all chunks; bytes
remain quarantine-only until independently verified B1/D recipient admission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ssl
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_large_parent import (
    VerifiedLargeParent, verify_signed_large_parent,
)
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks


def fetch_signed_parent_chunks(
    *,
    signed_parent_bytes: bytes,
    transfer: PinnedChunkTransfer,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    publisher_key_current: Callable[[str], bool],
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    current_host_admit: Callable[[PinnedChunkTransfer], bool],
    clock: Callable[[], datetime],
    receiver: ChunkedArtifactReceiver,
    open_enrolled_tls: Callable[[], ssl.SSLSocket],
    expected_peer_certificate_sha256: str,
    authorize_peer: Callable,
    start_offset: int = 0,
    max_chunks: int = 128,
) -> dict[str, object]:
    """Fetch bounded signed chunks, returning unverified quarantine progress.

    Use an independently pinned SHA over the *entire signed parent bytes*
    in transfer.manifest_sha256. For cancellation, stop calling; for resume
    pass an authenticated local offset and repeat independent verification
    of publisher root + parent bytes. Offset must remain signed aligned.
    """
    if not callable(clock):
        raise ChunkTransferRejected("canonical current service clock required")
    if not callable(current_host_admit) or not callable(publisher_current):
        raise ChunkTransferRejected("current enrolled SAFE and publisher gates required")

    def now() -> datetime:
        observed = clock()
        if not isinstance(observed, datetime) or observed.utcoffset() is None:
            raise ChunkTransferRejected("trusted aware service clock required")
        return observed.astimezone(timezone.utc)

    parent: VerifiedLargeParent = verify_signed_large_parent(
        signed_parent_bytes,
        transfer=transfer,
        trusted_publisher_public_key=trusted_publisher_public_key,
        expected_publisher_key_sha256=expected_publisher_key_sha256,
        publisher_key_current=publisher_key_current, now=now(),
    )
    if not parent.matches_transfer(transfer):
        raise ChunkTransferRejected("verified parent does not bind chosen signed transfer")
    if type(start_offset) is not int or start_offset < 0 or start_offset >= transfer.size_bytes:
        raise ChunkTransferRejected("signed parent requires bounded resume cursor")
    if start_offset % parent.chunk_bytes != 0:
        raise ChunkTransferRejected("signed parent prohibits partial chunk resume")

    def current(t: PinnedChunkTransfer) -> bool:
        return (t == transfer and now() < parent.expires_at
                and publisher_key_current(parent.publisher_key_sha256) is True
                and publisher_current(t) is True
                and current_host_admit(t) is True)

    if current(transfer) is not True:
        raise ChunkTransferRejected("publisher, signed parent or enrolled host revoked")

    def digest_for_chunk(offset: int, length: int) -> str:
        if current(transfer) is not True:
            raise ChunkTransferRejected("signed parent revoked between chunks")
        return parent.expected_chunk_sha256(offset, length)

    received = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver,
        open_enrolled_tls=open_enrolled_tls,
        expected_peer_certificate_sha256=expected_peer_certificate_sha256,
        authorize_peer=authorize_peer, publisher_current=current,
        start_offset=start_offset, chunk_bytes=parent.chunk_bytes,
        max_chunks=max_chunks, signed_chunk_sha256=digest_for_chunk,
    )
    if current(transfer) is not True:
        raise ChunkTransferRejected("signed parent revoked before progress receipt")

    # This is a transferred-byte observation only. The signed parent SHA
    # and chunk hashes do not prove publisher policy, installed origin or
    # activation. The canonical receiver's finalize independently checks
    # the complete SHA; B1/D must separately verify signer and trust.
    return {
        "schema": "aegis.library.signed-parent-receipt.v1",
        "source_platform_id": transfer.source_platform_id,
        "target_platform_id": transfer.target_platform_id,
        "manifest_sha256": parent.signed_manifest_sha256,
        "content_sha256": parent.content_sha256,
        "catalog_revision": transfer.catalog_revision,
        "generation": transfer.generation,
        "total_bytes": transfer.size_bytes,
        "received_bytes": received,
        "verified_bytes": 0,
        "parent_chunks": len(parent.chunk_sha256s),
        "large_artifact": parent.is_large,
        "cache_state": "RECEIVING" if received < transfer.size_bytes else "VERIFYING",
        "installed": None,
        "active": None,
        "install_executed": False,
    }
