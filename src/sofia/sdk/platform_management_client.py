"""Linux native client for ONE current, SAFE-enrolled Platform status read.

This client neither creates credentials nor authorizes an operator. Its pins
must come from B's trusted installed-service metadata, not Hub JSON or a
command-line 'approved' flag. SO_PEERCRED authenticates the connected local
service uid/gid and optionally PID, not publisher signature or SAFE grant.
Only the existing Platform service can decide whether to disclose a response.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
from time import monotonic
from uuid import uuid4

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import UntrustedManagementResponse

_MAX_CONTROL = 32 * 1024
_MAX_REQUEST = 64 * 1024
_MAX_SOCK_PATH = 100
_MAX_WAIT = 2.0


def _no_redirects(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink():
            raise PermissionError("Platform IPC path redirection denied")


def _native_socket_pin(
    path: Path, *, expected_uid: int, expected_gid: int,
) -> tuple[int, int]:
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("Linux OS peer credentials required")
    if not isinstance(path, Path) or not path.is_absolute():
        raise PermissionError("signed installed absolute socket Path required")
    if len(os.fsencode(str(path))) > _MAX_SOCK_PATH:
        raise PermissionError("overlong management socket path")
    if (type(expected_uid) is not int or expected_uid < 0
            or type(expected_gid) is not int or expected_gid < 0):
        raise ValueError("signed service UID/GID pin required")
    _no_redirects(path)
    parent = os.lstat(path.parent)
    leaf = os.lstat(path)
    if (not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != expected_uid
            or parent.st_gid != expected_gid
            or stat.S_IMODE(parent.st_mode) not in {0o700, 0o750}):
        raise PermissionError("untrusted Platform IPC runtime directory")
    mode = 0o600 if stat.S_IMODE(parent.st_mode) == 0o700 else 0o660
    if (not stat.S_ISSOCK(leaf.st_mode)
            or leaf.st_uid != expected_uid
            or leaf.st_gid != expected_gid
            or stat.S_IMODE(leaf.st_mode) != mode):
        raise PermissionError("untrusted Platform IPC socket inode, owner or mode")
    return (leaf.st_dev, leaf.st_ino)


def _read_one_reply(connection: socket.socket, *, deadline: float) -> bytes:
    raw = bytearray()
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Platform management response deadline exceeded")
        connection.settimeout(remaining)
        try:
            piece = connection.recv(min(4096, _MAX_CONTROL + 2 - len(raw)))
        except socket.timeout as exc:
            raise TimeoutError("Platform management response deadline exceeded") from exc
        if not piece:
            # EOF is normal for an unenrolled or revoked peer. Do not claim
            # a typed denial from an unauthenticated or closed channel.
            raise PermissionError("Platform service refused or unavailable")
        raw.extend(piece)
        if len(raw) > _MAX_CONTROL + 1:
            raise ValueError("oversized Platform management response")
        if b"\n" in piece:
            if raw[-1:] != b"\n" or raw.count(b"\n") != 1:
                raise ValueError("pipelined or trailing management response refused")
            return bytes(raw[:-1])


def read_linux_platform_status(
    *,
    socket_path: Path,
    expected_platform_id: str,
    expected_generation: int,
    installed_service_uid: int,
    installed_service_gid: int,
    installed_service_pid: int | None = None,
) -> UntrustedManagementResponse:
    """One native authenticated read; NO discovery, enrollment or mutation.

    The caller supplies signed installer-derived exact pins and current RUN
    generation, not values obtained from untrusted peer JSON. The service
    independently checks current owner SAFE/STOP and may close without reply.
    """
    if installed_service_pid is not None and (
        type(installed_service_pid) is not int or installed_service_pid <= 0
    ):
        raise ValueError("invalid optional installed service PID pin")
    inode = _native_socket_pin(
        socket_path, expected_uid=installed_service_uid,
        expected_gid=installed_service_gid,
    )
    now = datetime.now(timezone.utc)
    # No client-provided owner SID, UID, secret, approval or arbitrary operation.
    request = UntrustedManagementRead.from_payload({
        "schema": "aegis.platform.management.read.v1",
        "protocol": "1.0",
        "request_id": "req:" + uuid4().hex,
        "target_platform_id": expected_platform_id,
        "expected_generation": expected_generation,
        "operation": "platform.status",
        "created_at": now.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "deadline": (now + timedelta(seconds=5)).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
    }, now=now)
    payload = json.dumps(
        request.to_payload(), separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if len(payload) > _MAX_REQUEST:
        raise ValueError("unbounded management request")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(_MAX_WAIT)
        connection.connect(str(socket_path))
        encoded = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
        pid, uid, gid = struct.unpack("3i", encoded)
        if (pid <= 0 or uid != installed_service_uid
                or gid != installed_service_gid
                or (installed_service_pid is not None
                    and pid != installed_service_pid)):
            raise PermissionError("connected Platform service OS identity mismatch")
        if _native_socket_pin(
            socket_path, expected_uid=installed_service_uid,
            expected_gid=installed_service_gid,
        ) != inode:
            raise PermissionError("management socket replaced during connect")
        try:
            connection.sendall(payload + b"\n")
            raw = _read_one_reply(connection, deadline=monotonic() + _MAX_WAIT)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            raise PermissionError("Platform service refused or unavailable") from exc
        if _native_socket_pin(
            socket_path, expected_uid=installed_service_uid,
            expected_gid=installed_service_gid,
        ) != inode:
            raise PermissionError("management socket replaced during read")
    return UntrustedManagementResponse.parse(
        raw, expected=request, now=datetime.now(timezone.utc),
    )
