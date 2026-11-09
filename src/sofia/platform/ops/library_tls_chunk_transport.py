"""D028-04 bounded chunk exchange on a pre-enrolled, mutual TLS 1.3 socket.

This is transport only. The canonical Platform service must supply an accepted
TLS socket, independently verified publisher/cache, live enrolled SAFE/STOP
grant and transfer plan. No listener, public endpoint, signer, install or
activation is created here. Never pass a user-supplied authorization callback.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import re
import socket
import ssl
import struct
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_chunk_sender import read_authorized_cached_chunk

SCHEMA = "aegis.library.tls.chunk.v1"
MAX_CONTROL = 4096
MAX_CHUNK = 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TRANSFER_KEYS = frozenset(PinnedChunkTransfer.__dataclass_fields__)
_REQUEST_KEYS = frozenset({"schema", "transfer", "offset", "length"})
_RESPONSE_KEYS = frozenset({"schema", "digest", "offset", "length", "chunk_sha256"})


def _tls_peer_fingerprint(channel: ssl.SSLSocket) -> str:
    if not isinstance(channel, ssl.SSLSocket):
        raise ChunkTransferRejected("OS-managed TLS socket required")
    if (channel.version() != "TLSv1.3" or channel.context.verify_mode != ssl.CERT_REQUIRED):
        raise ChunkTransferRejected("mutual verified TLS 1.3 required")
    timeout = channel.gettimeout()
    if timeout is None or not 0 < timeout <= 30:
        raise ChunkTransferRejected("bounded TLS socket deadline required")
    peer = channel.getpeercert(binary_form=True)
    if type(peer) is not bytes or not 1 <= len(peer) <= 65536:
        raise ChunkTransferRejected("verified TLS peer certificate missing")
    return sha256(peer).hexdigest()


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ChunkTransferRejected("duplicate transfer control property")
        result[name] = value
    return result


def _read_exact(channel: ssl.SSLSocket, size: int) -> bytes:
    if type(size) is not int or not 0 <= size <= MAX_CHUNK:
        raise ChunkTransferRejected("invalid bounded transport size")
    pieces = []
    remaining = size
    try:
        while remaining:
            piece = channel.recv(min(remaining, 65536))
            if not piece:
                raise ChunkTransferRejected("short or interrupted TLS transfer")
            pieces.append(piece)
            remaining -= len(piece)
    except (OSError, TimeoutError) as exc:
        raise ChunkTransferRejected("TLS transfer unavailable") from exc
    return b"".join(pieces)


def _frame(channel: ssl.SSLSocket, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")
    if not 1 <= len(data) <= MAX_CONTROL:
        raise ChunkTransferRejected("transfer control frame exceeds bound")
    try:
        channel.sendall(struct.pack("!I", len(data)) + data)
    except (OSError, TimeoutError) as exc:
        raise ChunkTransferRejected("TLS control send unavailable") from exc


def _receive_frame(channel: ssl.SSLSocket, fields: frozenset) -> dict:
    size = struct.unpack("!I", _read_exact(channel, 4))[0]
    if not 1 <= size <= MAX_CONTROL:
        raise ChunkTransferRejected("unbounded transfer control frame")
    try:
        frame = json.loads(
            _read_exact(channel, size).decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ChunkTransferRejected("nonfinite transfer control number")
            ),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ChunkTransferRejected("invalid transfer control frame") from exc
    if type(frame) is not dict or set(frame) != fields or frame.get("schema") != SCHEMA:
        raise ChunkTransferRejected("unknown transfer protocol or control properties")
    return frame


def _approved(
    checker: Callable, channel: ssl.SSLSocket, peer_fingerprint: str,
    transfer: PinnedChunkTransfer, offset: int, length: int,
) -> bool:
    # The canonical owner service must bind fingerprint, generation, both
    # platform IDs, signed manifest, current SAFE/STOP and revocation.
    if not callable(checker) or checker(
        channel, peer_fingerprint, transfer, offset, length
    ) is not True:
        raise ChunkTransferRejected("current enrolled peer grant unavailable")
    return True


def _bounds(transfer: PinnedChunkTransfer, offset: int, length: int) -> None:
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("signed pinned transfer required")
    if (type(offset) is not int or type(length) is not int or offset < 0
            or not 1 <= length <= MAX_CHUNK
            or offset > transfer.size_bytes - length):
        raise ChunkTransferRejected("chunk outside pinned signed content")


def serve_one_chunk(
    channel: ssl.SSLSocket, *,
    lookup_transfer: Callable[[str], PinnedChunkTransfer],
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    resolve_verified_cache: Callable[[PinnedChunkTransfer], object],
) -> int:
    """Serve one exact planned chunk from verified CAS. Does not create a Hub."""
    fingerprint = _tls_peer_fingerprint(channel)
    request = _receive_frame(channel, _REQUEST_KEYS)
    raw = request["transfer"]
    if type(raw) is not dict or set(raw) != _TRANSFER_KEYS:
        raise ChunkTransferRejected("transfer plan requires all signed context")
    try:
        candidate = PinnedChunkTransfer(**raw)
    except (TypeError, ValueError) as exc:
        raise ChunkTransferRejected("invalid signed transfer context") from exc
    offset, length = request["offset"], request["length"]
    _bounds(candidate, offset, length)
    if not callable(lookup_transfer):
        raise ChunkTransferRejected("service-owned signed transfer lookup required")
    trusted = lookup_transfer(candidate.content_sha256)
    if type(trusted) is not PinnedChunkTransfer or trusted != candidate:
        raise ChunkTransferRejected("peer request differs from trusted transfer plan")

    def current(t):
        return _approved(authorize_peer, channel, fingerprint, t, offset, length)

    data, digest = read_authorized_cached_chunk(
        trusted, offset=offset, length=length, authorize=current,
        publisher_current=publisher_current,
        resolve_verified_cache=resolve_verified_cache,
    )
    current(trusted)
    _frame(channel, {"schema": SCHEMA, "digest": trusted.content_sha256,
                     "offset": offset, "length": length, "chunk_sha256": digest})
    try:
        channel.sendall(data)
    except (OSError, TimeoutError) as exc:
        raise ChunkTransferRejected("TLS chunk send unavailable") from exc
    return length


def receive_one_chunk(
    channel: ssl.SSLSocket, *,
    transfer: PinnedChunkTransfer,
    offset: int,
    length: int,
    receiver: ChunkedArtifactReceiver,
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    expected_signed_chunk_sha256: str | None = None,
) -> int:
    """Fetch one bounded chunk into quarantine, NOT verification or installation.

    For large parent manifests the independently verified signed chunk digest
    is mandatory and checked before any bytes enter the receiver. A Hub-provided
    digest alone is never equivalent to a publisher-signed chunk digest.
    """
    _bounds(transfer, offset, length)
    if (expected_signed_chunk_sha256 is not None
            and (type(expected_signed_chunk_sha256) is not str
                 or _DIGEST.fullmatch(expected_signed_chunk_sha256) is None)):
        raise ChunkTransferRejected("independent signed chunk digest invalid")
    if not isinstance(receiver, ChunkedArtifactReceiver):
        raise ChunkTransferRejected("canonical single-writer CAS receiver required")
    fingerprint = _tls_peer_fingerprint(channel)
    def current(t):
        return _approved(authorize_peer, channel, fingerprint, t, offset, length)
    if not callable(publisher_current) or publisher_current(transfer) is not True:
        raise ChunkTransferRejected("current independently signed metadata unavailable")
    current(transfer)
    if receiver.received_bytes(transfer, authorize=current) != offset:
        raise ChunkTransferRejected("receiver resume offset is not current")
    _frame(channel, {"schema": SCHEMA, "transfer": asdict(transfer),
                     "offset": offset, "length": length})
    response = _receive_frame(channel, _RESPONSE_KEYS)
    if (response["digest"] != transfer.content_sha256
            or type(response["offset"]) is not int or response["offset"] != offset
            or type(response["length"]) is not int or response["length"] != length
            or type(response["chunk_sha256"]) is not str
            or _DIGEST.fullmatch(response["chunk_sha256"]) is None):
        raise ChunkTransferRejected("peer returned unpinned chunk metadata")
    if (expected_signed_chunk_sha256 is not None
            and response["chunk_sha256"] != expected_signed_chunk_sha256):
        raise ChunkTransferRejected("peer chunk differs from signed parent")
    data = _read_exact(channel, length)
    observed = sha256(data).hexdigest()
    if observed != response["chunk_sha256"]:
        raise ChunkTransferRejected("peer chunk digest mismatch")
    if (expected_signed_chunk_sha256 is not None
            and observed != expected_signed_chunk_sha256):
        raise ChunkTransferRejected("received bytes differ from signed parent")
    current(transfer)
    if publisher_current(transfer) is not True:
        raise ChunkTransferRejected("publisher metadata revoked during read")
    return receiver.append_chunk(
        transfer, offset=offset, chunk=data,
        chunk_sha256=response["chunk_sha256"], authorize=current,
    )
