"""Kernel-authenticated local Unix peer intake for a future Platform broker.

This is a transport primitive, NOT a listener, enrollment source, or owner
grant. The trusted Platform must accept connections from its protected runtime
socket and provide a dispatcher that checks current owner enrollment,
revocation, STOP and Platform generation both before and after observation.

Never use a request header, claimed user name or client JSON as peer identity.
Windows must use a separately verified named-pipe impersonation/token path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import socket
import struct
import sys
from time import monotonic
from typing import Callable, Mapping

MAX_REQUEST_BYTES = 65536
MAX_REPLY_BYTES = 65536
_IO_TIMEOUT = 2.0


@dataclass(frozen=True, slots=True)
class KernelUnixPeer:
    pid: int
    uid: int
    gid: int

    @property
    def principal(self) -> str:
        """Only a routing identity, NOT an owner authorization."""
        return f"unix:uid:{self.uid}:gid:{self.gid}"


def require_kernel_unix_peer(connection: socket.socket) -> KernelUnixPeer:
    """Verify local peer through Linux SO_PEERCRED, not self-asserted fields."""
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("verified Unix peer credentials unavailable")
    if not isinstance(connection, socket.socket) or connection.family != socket.AF_UNIX:
        raise PermissionError("local Unix socket required")
    try:
        # A socket with no connected peer cannot establish a caller identity.
        connection.getpeername()
        encoded = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
        pid, uid, gid = struct.unpack("3i", encoded)
    except (OSError, ValueError, struct.error) as error:
        raise PermissionError("kernel peer credentials unavailable") from error
    if pid <= 0 or uid < 0 or gid < 0:
        raise PermissionError("invalid peer credential tuple")
    return KernelUnixPeer(pid=pid, uid=uid, gid=gid)


def read_single_bounded_request(connection: socket.socket) -> bytes:
    """A single newline-terminated JSON request, no pipelining or unlimited IO."""
    if not isinstance(connection, socket.socket) or connection.family != socket.AF_UNIX:
        raise PermissionError("Unix connection required")
    deadline = monotonic() + _IO_TIMEOUT
    raw = bytearray()
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Platform management read deadline exceeded")
        connection.settimeout(remaining)
        try:
            block = connection.recv(min(4096, MAX_REQUEST_BYTES + 1 - len(raw)))
        except socket.timeout as error:
            raise TimeoutError("Platform management read deadline exceeded") from error
        if not block:
            raise ValueError("Platform management request closed before newline")
        raw.extend(block)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("oversized Platform management request")
        if b"\n" in block:
            if raw[-1:] != b"\n" or raw.count(b"\n") != 1:
                raise ValueError("pipelined or trailing Platform management requests denied")
            return bytes(raw[:-1])


def dispatch_one_kernel_peer_read(
    connection: socket.socket,
    *,
    dispatch: Callable[..., Mapping[str, object]],
    now: datetime | Callable[[], datetime],
) -> None:
    """Dispatch one bounded read, with no active listener or implicit approval.

    The provided dispatcher is service-owned and must independently validate
    current SAFE and authorized scopes. Never return an exception/repr to peers.
    Call only after the Platform creates and protects its OS socket path.
    """
    peer = require_kernel_unix_peer(connection)
    request = read_single_bounded_request(connection)
    # A callable clock is sampled AFTER intake, defeating slow-client stale time.
    observed_at = now() if callable(now) else now
    result = dispatch(request, authenticated_peer=peer.principal, now=observed_at)
    if not isinstance(result, Mapping):
        raise ValueError("non-object Platform management response")
    try:
        body = json.dumps(
            result, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("malformed Platform management response") from error
    if not body or len(body) > MAX_REPLY_BYTES:
        raise ValueError("Platform management response exceeds bound")
    connection.settimeout(_IO_TIMEOUT)
    connection.sendall(body + b"\n")
