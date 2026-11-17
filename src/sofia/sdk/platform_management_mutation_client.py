"""Bounded client for owner-approved Core autostart management mutations.

The client only frames an exact ``aegis.platform.management_mutation.v1``
request, authenticates the already-pinned local OS transport, sends exactly
one bounded request and parses one correlated receipt. It never mints,
consumes or stores a SAFE approval, never opens the canonical SQLite file and
never retries after request bytes may have reached the Platform service.

An ambiguous transport or response is reported as ``ManagementMutationAmbiguous``
because the caller cannot prove whether an effect occurred. A typed
``OUTCOME_UNKNOWN`` receipt is returned unchanged and is likewise never
retried automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ctypes
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys
from time import monotonic, sleep
from uuid import uuid4

from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    MAX_MUTATION_REQUEST_BYTES, MAX_MUTATION_RESPONSE_BYTES,
    UntrustedManagementMutation, UntrustedManagementMutationResponse,
)
from sofia.sdk.platform_management_windows_client import (
    _kernel32, _overlapped_call, windows_management_pipe_name,
)

CORE_AUTOSTART_ENABLE_OPERATION = "core.autostart.enable"
CORE_AUTOSTART_DISABLE_OPERATION = "core.autostart.disable"
CORE_AUTOSTART_SCOPE = "operator"
SUPPORTED_CORE_AUTOSTART_OPERATIONS = frozenset({
    CORE_AUTOSTART_ENABLE_OPERATION,
    CORE_AUTOSTART_DISABLE_OPERATION,
})

MAX_MUTATION_WAIT = 2.0
_MAX_PORTABLE_INT = 2**53 - 1
_MAX_MUTATION_DEADLINE_SECONDS = 5
_MAX_SOCKET_PATH = 100
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_CORE_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_FLAG_OVERLAPPED = 0x40000000
_SECURITY_SQOS_PRESENT = 0x100000
_SECURITY_IMPERSONATION = 0x10000
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_PIPE_BUSY = 231
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class ManagementMutationAmbiguous(RuntimeError):
    """Request bytes may have reached the service; the effect is unknown."""


@dataclass(frozen=True, slots=True)
class CoreAutostartMutationRequest:
    """One typed Core autostart mutation plus its exact bounded wire bytes."""

    request: UntrustedManagementMutation
    wire: bytes

    @property
    def payload(self) -> dict[str, object]:
        return dict(self.request.payload)


def _bounded_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    if value.upper() in {"OWNER", "ANY"}:
        raise ValueError(f"{label} cannot be a wildcard identity")
    return value


def _canonical_core(value: object) -> str:
    if not isinstance(value, str) or _CORE_UUID.fullmatch(value) is None:
        raise ValueError("core_id must be a lowercase canonical UUID")
    if str(value) != value:
        raise ValueError("core_id must be a lowercase canonical UUID")
    return value


def _portable_int(value: object, label: str, *, minimum: int) -> int:
    if (
        type(value) is not int
        or not minimum <= value <= _MAX_PORTABLE_INT
    ):
        raise ValueError(f"{label} is outside the portable integer range")
    return value


def _aware_moment(value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("authoritative current time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _derived_idempotency_key(
    *,
    platform_id: str,
    generation: int,
    operation: str,
    expected_revision: int,
    payload: dict[str, object],
) -> str:
    document = {
        "target_platform_id": platform_id,
        "operation": operation,
        "operation_scope": CORE_AUTOSTART_SCOPE,
        "expected_generation": generation,
        "expected_revision": expected_revision,
        "payload": payload,
    }
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "idempotency:" + sha256(encoded).hexdigest()


def build_core_autostart_mutation(
    *,
    platform_id: str,
    generation: int,
    operation: str,
    core_id: str,
    expected_policy_revision: int,
    enabled: bool,
    approval_id: str,
    expected_mutation_revision: int,
    now: datetime | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> CoreAutostartMutationRequest:
    """Build one exact Core autostart mutation for an existing pinned channel.

    ``expected_policy_revision`` is the next Core autostart policy revision.
    ``expected_mutation_revision`` is the dispatcher's current management
    mutation revision. ``approval_id`` is a caller-supplied one-use SAFE
    approval reference and is never generated here.
    """
    if (
        not isinstance(operation, str)
        or operation not in SUPPORTED_CORE_AUTOSTART_OPERATIONS
    ):
        raise ValueError("unsupported Core autostart management operation")
    if type(enabled) is not bool:
        raise TypeError("enabled must be bool")
    if enabled is not (operation == CORE_AUTOSTART_ENABLE_OPERATION):
        raise ValueError("operation and enabled target disagree")
    target = _bounded_identifier(platform_id, "target_platform_id")
    platform_generation = _portable_int(
        generation, "expected_generation", minimum=1,
    )
    mutation_revision = _portable_int(
        expected_mutation_revision, "expected_mutation_revision", minimum=0,
    )
    policy_revision = _portable_int(
        expected_policy_revision, "expected_policy_revision", minimum=1,
    )
    core = _canonical_core(core_id)
    approval = _bounded_identifier(approval_id, "approval_id")
    moment = _aware_moment(
        datetime.now(timezone.utc) if now is None else now
    )
    identifier = request_id or ("request:" + uuid4().hex)
    correlation = correlation_id or ("correlation:" + uuid4().hex)
    _bounded_identifier(identifier, "request_id")
    _bounded_identifier(correlation, "correlation_id")
    payload: dict[str, object] = {
        "core_id": core,
        "expected_revision": policy_revision,
        "enabled": enabled,
    }
    key = idempotency_key or _derived_idempotency_key(
        platform_id=target,
        generation=platform_generation,
        operation=operation,
        expected_revision=mutation_revision,
        payload=payload,
    )
    _bounded_identifier(key, "idempotency_key")
    document = {
        "schema": MANAGEMENT_MUTATION_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": identifier,
        "correlation_id": correlation,
        "idempotency_key": key,
        "target_platform_id": target,
        "operation": operation,
        "operation_scope": CORE_AUTOSTART_SCOPE,
        "expected_generation": platform_generation,
        "expected_revision": mutation_revision,
        "deadline": _rfc3339(
            moment + timedelta(seconds=_MAX_MUTATION_DEADLINE_SECONDS)
        ),
        "approval_id": approval,
        "payload": payload,
    }
    request = UntrustedManagementMutation.from_payload(document, now=moment)
    wire = json.dumps(
        request.to_payload(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if len(wire) > MAX_MUTATION_REQUEST_BYTES:
        raise ValueError("bounded management mutation request size exceeded")
    return CoreAutostartMutationRequest(request=request, wire=wire)


def _bounded_wait(value: object) -> float:
    if (
        type(value) not in (int, float)
        or type(value) is bool
        or not 0 < float(value) <= 30
    ):
        raise ValueError("bounded management mutation wait required")
    return float(value)


def _parse_reply(
    raw: bytes, *, request: UntrustedManagementMutation,
) -> UntrustedManagementMutationResponse:
    try:
        return UntrustedManagementMutationResponse.parse(
            raw, expected=request, now=datetime.now(timezone.utc),
        )
    except (ValueError, PermissionError, TypeError) as error:
        raise ManagementMutationAmbiguous(
            "management mutation response was not safely correlated"
        ) from error


def _write_windows_request(
    k, handle, event, wire: bytes, *, deadline: float,
) -> None:
    buffer = ctypes.create_string_buffer(wire)
    sent = 0
    while sent < len(wire):
        chunk = ctypes.byref(buffer, sent)
        remaining = len(wire) - sent
        count = _overlapped_call(
            k, handle, event,
            lambda overlapped, written: k.WriteFile(
                handle, chunk, remaining, written, overlapped,
            ),
            deadline=deadline,
        )
        if count <= 0:
            raise PermissionError(
                "Windows management mutation request write refused"
            )
        sent += count


def _read_windows_reply(k, handle, event, *, deadline: float) -> bytes:
    raw = bytearray()
    while True:
        if monotonic() >= deadline:
            raise TimeoutError(
                "Windows management mutation response deadline exceeded"
            )
        buffer = ctypes.create_string_buffer(
            min(4096, MAX_MUTATION_RESPONSE_BYTES + 1 - len(raw))
        )
        count = _overlapped_call(
            k, handle, event,
            lambda overlapped, read: k.ReadFile(
                handle, buffer, len(buffer), read, overlapped,
            ),
            deadline=deadline,
        )
        if count < 0:
            sleep(0.001)
            continue
        if count == 0:
            raise PermissionError("Windows management mutation pipe closed")
        raw.extend(buffer.raw[:count])
        if len(raw) > MAX_MUTATION_RESPONSE_BYTES:
            raise ValueError("oversized Windows management mutation response")
        if b"\n" in raw:
            if raw.count(b"\n") != 1 or raw[-1:] != b"\n":
                raise ValueError(
                    "pipelined or trailing management mutation response refused"
                )
            return bytes(raw[:-1])


def mutate_windows_management(
    *,
    pipe_name: str,
    expected_platform_id: str,
    expected_generation: int,
    operation: str,
    core_id: str,
    expected_policy_revision: int,
    enabled: bool,
    approval_id: str,
    expected_mutation_revision: int,
    wait_seconds: float = MAX_MUTATION_WAIT,
    now: datetime | None = None,
) -> UntrustedManagementMutationResponse:
    """Send exactly one mutation over the exact pinned existing Windows pipe."""
    if os.name != "nt":
        raise PermissionError("Windows native named-pipe client unavailable")
    if not isinstance(pipe_name, str):
        raise ValueError("bounded canonical Aegis Platform pipe name required")
    try:
        expected_name = windows_management_pipe_name(
            platform_id=expected_platform_id,
            generation=expected_generation,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "canonical Platform UUID and generation required for pipe name"
        ) from error
    if pipe_name != expected_name:
        raise PermissionError("pinned Windows management pipe name mismatch")
    wait = _bounded_wait(wait_seconds)
    built = build_core_autostart_mutation(
        platform_id=expected_platform_id,
        generation=expected_generation,
        operation=operation,
        core_id=core_id,
        expected_policy_revision=expected_policy_revision,
        enabled=enabled,
        approval_id=approval_id,
        expected_mutation_revision=expected_mutation_revision,
        now=now,
    )
    k = _kernel32()
    full_name = "\\\\.\\pipe\\" + pipe_name
    deadline = monotonic() + wait
    handle = None
    while True:
        handle = k.CreateFileW(
            full_name,
            _GENERIC_READ | _GENERIC_WRITE,
            0,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OVERLAPPED
            | _SECURITY_SQOS_PRESENT
            | _SECURITY_IMPERSONATION,
            None,
        )
        if handle not in (None, _INVALID_HANDLE_VALUE):
            break
        error = ctypes.get_last_error()
        if (
            error in {
                _ERROR_PIPE_BUSY, _ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND,
            }
            and monotonic() < deadline
        ):
            sleep(0.02)
            continue
        raise PermissionError("Windows Platform management pipe unavailable")
    event = k.CreateEventW(None, False, False, None)
    if event in (None, _INVALID_HANDLE_VALUE):
        k.CloseHandle(handle)
        raise PermissionError("Windows Platform management pipe event unavailable")
    try:
        deadline = monotonic() + wait
        try:
            _write_windows_request(
                k, handle, event, built.wire + b"\n", deadline=deadline,
            )
            raw = _read_windows_reply(k, handle, event, deadline=deadline)
        except (PermissionError, TimeoutError, ValueError, OSError) as error:
            raise ManagementMutationAmbiguous(
                "Windows management mutation transport outcome is unknown"
            ) from error
    finally:
        k.CloseHandle(event)
        k.CloseHandle(handle)
    return _parse_reply(raw, request=built.request)


def mutate_linux_management(
    *,
    socket_path: Path,
    expected_platform_id: str,
    expected_generation: int,
    operation: str,
    core_id: str,
    expected_policy_revision: int,
    enabled: bool,
    approval_id: str,
    expected_mutation_revision: int,
    installed_service_uid: int,
    installed_service_gid: int,
    installed_service_pid: int | None = None,
    installed_socket_group_gid: int | None = None,
    wait_seconds: float = MAX_MUTATION_WAIT,
    now: datetime | None = None,
) -> UntrustedManagementMutationResponse:
    """Send exactly one mutation over the pinned existing Linux Unix socket."""
    from sofia.sdk.platform_management_client import (
        _native_socket_pin, _read_one_reply,
    )
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("Linux OS peer credentials required")
    if not isinstance(socket_path, Path) or not socket_path.is_absolute():
        raise PermissionError("signed installed absolute socket Path required")
    if len(os.fsencode(str(socket_path))) > _MAX_SOCKET_PATH:
        raise PermissionError("overlong management socket path")
    if (
        type(installed_service_uid) is not int
        or installed_service_uid < 0
        or type(installed_service_gid) is not int
        or installed_service_gid < 0
    ):
        raise ValueError("signed service UID/GID pin required")
    if installed_service_pid is not None and (
        type(installed_service_pid) is not int or installed_service_pid <= 0
    ):
        raise ValueError("invalid optional installed service PID pin")
    if installed_socket_group_gid is not None and installed_service_pid is None:
        raise PermissionError(
            "external management requires verified live service PID pin"
        )
    wait = _bounded_wait(wait_seconds)
    inode = _native_socket_pin(
        socket_path,
        expected_uid=installed_service_uid,
        expected_gid=installed_service_gid,
        expected_socket_group_gid=installed_socket_group_gid,
    )
    built = build_core_autostart_mutation(
        platform_id=expected_platform_id,
        generation=expected_generation,
        operation=operation,
        core_id=core_id,
        expected_policy_revision=expected_policy_revision,
        enabled=enabled,
        approval_id=approval_id,
        expected_mutation_revision=expected_mutation_revision,
        now=now,
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(wait)
        connection.connect(str(socket_path))
        encoded = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
        pid, uid, gid = struct.unpack("3i", encoded)
        if (
            pid <= 0
            or uid != installed_service_uid
            or gid != installed_service_gid
            or (
                installed_service_pid is not None
                and pid != installed_service_pid
            )
        ):
            raise PermissionError("connected Platform service OS identity mismatch")
        if _native_socket_pin(
            socket_path,
            expected_uid=installed_service_uid,
            expected_gid=installed_service_gid,
            expected_socket_group_gid=installed_socket_group_gid,
        ) != inode:
            raise PermissionError("management socket replaced during connect")
        try:
            connection.sendall(built.wire + b"\n")
            raw = _read_one_reply(
                connection, deadline=monotonic() + wait,
            )
        except (
            BrokenPipeError, ConnectionResetError, ConnectionAbortedError,
            socket.timeout, TimeoutError, OSError,
        ) as error:
            raise ManagementMutationAmbiguous(
                "Linux management mutation transport outcome is unknown"
            ) from error
        if _native_socket_pin(
            socket_path,
            expected_uid=installed_service_uid,
            expected_gid=installed_service_gid,
            expected_socket_group_gid=installed_socket_group_gid,
        ) != inode:
            raise ManagementMutationAmbiguous(
                "management socket replaced during mutation"
            )
    return _parse_reply(raw, request=built.request)
