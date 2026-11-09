"""D028-04 bounded, resumable mTLS artifact-byte acquisition.

The canonical Platform service supplies a freshly authenticated TLS 1.3
connection and current SAFE/STOP, enrollment and publisher decisions for every
chunk. A finished fetch is only quarantine bytes, never a verified publisher
package, installation, activation, or owner grant.

This module does not dial arbitrary addresses, create trust roots or listeners,
or infer any authorization from network reachability. Calling it after a
process restart resumes from the durable single-writer receiver offset.
"""
from __future__ import annotations

import re
import ssl
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import (
    MAX_CHUNK, _approved, _tls_peer_fingerprint, receive_one_chunk,
)


def fetch_resumable_chunks(
    *, transfer: PinnedChunkTransfer,
    receiver: ChunkedArtifactReceiver,
    open_enrolled_tls: Callable[[], ssl.SSLSocket],
    expected_peer_certificate_sha256: str,
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    chunk_bytes: int = MAX_CHUNK,
    max_chunks: int = 128,
    start_offset: int = 0,
) -> int:
    """Fetch at most max_chunks, returning the durable offset after progress.

    Each chunk gets a fresh, service-managed mTLS session. Resume is an explicit
    subsequent call with the SAME independently trusted transfer descriptor.
    The service supplies an explicit expected durable offset; receiver state
    must match it before any bytes are requested. For a resumed call, use the
    last successful offset or a separately authorized local cursor read.
    A separate, owner-enrolled certificate digest is required across restart
    boundaries; TLS CA validation alone does not prove the expected Platform.
    No network URL, disk path, grant, or publisher identity is accepted from
    the remote peer. A new certificate within one call is refused, even if its
    CA is otherwise trusted; the service must deliberately restart the plan.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("independently pinned transfer required")
    if not isinstance(receiver, ChunkedArtifactReceiver):
        raise ChunkTransferRejected("canonical quarantine receiver required")
    if (type(expected_peer_certificate_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_peer_certificate_sha256) is None):
        raise ChunkTransferRejected("exact enrolled TLS peer certificate pin required")
    if not callable(open_enrolled_tls) or not callable(authorize_peer) or not callable(publisher_current):
        raise ChunkTransferRejected("service-owned TLS and authority required")
    if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= MAX_CHUNK:
        raise ChunkTransferRejected("bounded chunk size required")
    if type(max_chunks) is not int or not 1 <= max_chunks <= 10000:
        raise ChunkTransferRejected("bounded chunk budget required")
    if (type(start_offset) is not int or start_offset < 0
            or start_offset >= transfer.size_bytes):
        raise ChunkTransferRejected("bounded expected resume cursor required")

    first_fingerprint: str | None = None
    offset = start_offset
    for _ in range(max_chunks):
        # Refuse an already revoked manifest before opening a new connection.
        # The post-handshake check below remains mandatory against races.
        if publisher_current(transfer) is not True:
            raise ChunkTransferRejected("publisher trust revoked or unavailable")
        # The service, not the Hub, chooses the enrolled destination, CA,
        # pinned installation identity, deadline and complete SSL context.
        session = open_enrolled_tls()
        if not isinstance(session, ssl.SSLSocket):
            if hasattr(session, "close"):
                session.close()
            raise ChunkTransferRejected("enrolled TLS socket factory required")
        with session:
            fingerprint = _tls_peer_fingerprint(session)
            if fingerprint != expected_peer_certificate_sha256:
                raise ChunkTransferRejected("TLS peer differs from owner-enrolled certificate")
            if first_fingerprint is not None and fingerprint != first_fingerprint:
                raise ChunkTransferRejected("enrolled peer certificate changed mid-transfer")
            first_fingerprint = fingerprint
            length = min(chunk_bytes, transfer.size_bytes - offset)

            def current(t: PinnedChunkTransfer) -> bool:
                # The grant must cover the exact intended resumed byte range.
                # A synthetic zero-length grant is not sufficient.
                return _approved(authorize_peer, session, fingerprint, t, offset, length)

            if publisher_current(transfer) is not True:
                raise ChunkTransferRejected("publisher trust revoked or unavailable")
            current(transfer)
            observed = receiver.received_bytes(transfer, authorize=current)
            if observed != offset:
                raise ChunkTransferRejected("local resume cursor differs from expected offset")
            next_offset = receive_one_chunk(
                session, transfer=transfer, offset=offset, length=length,
                receiver=receiver, authorize_peer=authorize_peer,
                publisher_current=publisher_current,
            )
            if next_offset != offset + length:
                raise ChunkTransferRejected("TLS receiver made inconsistent progress")
            offset = next_offset
            if offset == transfer.size_bytes:
                # The final chunk is present in quarantine. No extra TLS
                # session, no inferred publisher verification or install.
                return offset
    return offset
