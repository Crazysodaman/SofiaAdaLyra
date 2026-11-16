"""Windows native read client for ONE pinned Aegis Platform management pipe.

This client neither creates credentials nor authorizes an operator. The pipe
name must be a bounded canonical ``AegisPlatform-<uuid>-<generation>`` name
derived from signed installed-service metadata, never a caller-supplied path.
The service owns Win32 token authentication; schema validity here is never an
enrollment or owner grant.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ctypes
import json
import os
import re
from time import monotonic, sleep
from uuid import uuid4

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import (
    MAX_RESPONSE_BYTES, UntrustedManagementResponse,
)

_MAX_REQUEST = 64 * 1024
_MAX_WAIT = 2.0
_MAX_PORTABLE_INT = 2**53 - 1
_SUPPORTED_READS = frozenset({"platform.status", "startup.status", "core.list"})
_PLATFORM_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_PIPE_NAME = re.compile(r"^AegisPlatform-([0-9a-f]{32})-([1-9][0-9]{0,18})$")

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_FLAG_OVERLAPPED = 0x40000000
_SECURITY_SQOS_PRESENT = 0x100000
_SECURITY_IMPERSONATION = 0x10000
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_PIPE_BUSY = 231
_ERROR_IO_PENDING = 997
_ERROR_NO_DATA = 232
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", ctypes.c_uint32),
        ("OffsetHigh", ctypes.c_uint32),
        ("hEvent", ctypes.c_void_p),
    ]


def windows_management_pipe_name(*, platform_id: str, generation: int) -> str:
    """Derive the exact reviewed pipe name; no alternate path is accepted."""
    if not isinstance(platform_id, str) or _PLATFORM_ID.fullmatch(platform_id) is None:
        raise ValueError("canonical Platform UUID required for pipe name")
    if (type(generation) is not int
            or not 1 <= generation <= _MAX_PORTABLE_INT):
        raise ValueError("positive portable Platform generation required")
    return "AegisPlatform-" + platform_id.replace("-", "") + "-" + str(generation)


def _kernel32():
    if os.name != "nt":
        raise PermissionError("Windows native named-pipe client unavailable")
    import ctypes.wintypes as wt
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    H, D, P = wt.HANDLE, wt.DWORD, ctypes.c_void_p
    k.CreateFileW.argtypes = [wt.LPCWSTR, D, D, P, D, D, H]
    k.CreateFileW.restype = H
    k.WriteFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
    k.WriteFile.restype = wt.BOOL
    k.ReadFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
    k.ReadFile.restype = wt.BOOL
    k.CreateEventW.argtypes = [P, wt.BOOL, wt.BOOL, P]
    k.CreateEventW.restype = H
    k.WaitForSingleObject.argtypes = [H, D]
    k.WaitForSingleObject.restype = D
    k.GetOverlappedResult.argtypes = [
        H, ctypes.POINTER(_Overlapped), ctypes.POINTER(D), wt.BOOL,
    ]
    k.GetOverlappedResult.restype = wt.BOOL
    k.CancelIoEx.argtypes = [H, ctypes.POINTER(_Overlapped)]
    k.CancelIoEx.restype = wt.BOOL
    k.ResetEvent.argtypes = [H]
    k.ResetEvent.restype = wt.BOOL
    k.CloseHandle.argtypes = [H]
    k.CloseHandle.restype = wt.BOOL
    return k


def _overlapped_call(k, handle, event, call, *, deadline: float) -> int:
    k.ResetEvent(event)
    overlapped = _Overlapped()
    overlapped.hEvent = event
    count = ctypes.c_uint32()
    if call(ctypes.byref(overlapped), ctypes.byref(count)):
        return count.value
    error = ctypes.get_last_error()
    if error == _ERROR_NO_DATA:
        return -1
    if error != _ERROR_IO_PENDING:
        raise PermissionError("Windows Platform management pipe I/O refused")
    remaining = deadline - monotonic()
    if remaining <= 0:
        k.CancelIoEx(handle, ctypes.byref(overlapped))
        raise TimeoutError("Windows Platform management pipe deadline exceeded")
    wait = k.WaitForSingleObject(event, max(1, int(remaining * 1000)))
    if wait == _WAIT_TIMEOUT:
        k.CancelIoEx(handle, ctypes.byref(overlapped))
        raise TimeoutError("Windows Platform management pipe deadline exceeded")
    if wait != _WAIT_OBJECT_0:
        raise PermissionError("Windows Platform management pipe wait failed")
    if not k.GetOverlappedResult(
        handle, ctypes.byref(overlapped), ctypes.byref(count), False,
    ):
        raise PermissionError("Windows Platform management pipe I/O failed")
    return count.value


def _read_reply(k, handle, event, *, deadline: float) -> bytes:
    raw = bytearray()
    while True:
        if monotonic() >= deadline:
            raise TimeoutError("Windows Platform management response deadline exceeded")
        buffer = ctypes.create_string_buffer(
            min(4096, MAX_RESPONSE_BYTES + 1 - len(raw))
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
            raise PermissionError("Windows Platform management pipe closed")
        raw.extend(buffer.raw[:count])
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("oversized Windows management response")
        if b"\n" in raw:
            if raw.count(b"\n") != 1 or raw[-1:] != b"\n":
                raise ValueError("pipelined or trailing management response refused")
            return bytes(raw[:-1])


def _write_request(k, handle, event, payload: bytes, *, deadline: float) -> None:
    wire = payload + b"\n"
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
            raise PermissionError("Windows Platform management request write refused")
        sent += count


def read_windows_management(
    *,
    pipe_name: str,
    expected_platform_id: str,
    expected_generation: int,
    operation: str,
    wait_seconds: float = _MAX_WAIT,
) -> UntrustedManagementResponse:
    """One bounded native read against the exact pinned existing pipe.

    Peer authentication remains the service's responsibility. A missing,
    substituted or mismatched pipe name fails closed before any request bytes
    are sent.
    """
    if os.name != "nt":
        raise PermissionError("Windows native named-pipe client unavailable")
    if not isinstance(pipe_name, str) or _PIPE_NAME.fullmatch(pipe_name) is None:
        raise ValueError("bounded canonical Aegis Platform pipe name required")
    expected_name = windows_management_pipe_name(
        platform_id=expected_platform_id, generation=expected_generation,
    )
    if pipe_name != expected_name:
        raise PermissionError("pinned Windows management pipe name mismatch")
    if not isinstance(operation, str) or operation not in _SUPPORTED_READS:
        raise ValueError("unsupported Platform management read operation")
    if (type(wait_seconds) not in (int, float)
            or not 0 < wait_seconds <= 30):
        raise ValueError("bounded Windows management wait required")

    now = datetime.now(timezone.utc)
    request = UntrustedManagementRead.from_payload({
        "schema": "aegis.platform.management.read.v1",
        "protocol": "1.0",
        "request_id": "req:" + uuid4().hex,
        "target_platform_id": expected_platform_id,
        "expected_generation": expected_generation,
        "operation": operation,
        "created_at": now.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "deadline": (now + timedelta(seconds=5)).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
    }, now=now)
    payload = json.dumps(
        request.to_payload(), separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    if len(payload) > _MAX_REQUEST:
        raise ValueError("unbounded management request")

    k = _kernel32()
    full_name = "\\\\.\\pipe\\" + pipe_name
    deadline = monotonic() + wait_seconds
    handle = None
    while True:
        handle = k.CreateFileW(
            full_name,
            _GENERIC_READ | _GENERIC_WRITE,
            0,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OVERLAPPED | _SECURITY_SQOS_PRESENT | _SECURITY_IMPERSONATION,
            None,
        )
        if handle not in (None, _INVALID_HANDLE_VALUE):
            break
        error = ctypes.get_last_error()
        if (error in {_ERROR_PIPE_BUSY, _ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND}
                and monotonic() < deadline):
            sleep(0.02)
            continue
        raise PermissionError("Windows Platform management pipe unavailable")
    event = k.CreateEventW(None, False, False, None)
    if event in (None, _INVALID_HANDLE_VALUE):
        k.CloseHandle(handle)
        raise PermissionError("Windows Platform management pipe event unavailable")
    try:
        deadline = monotonic() + wait_seconds
        _write_request(
            k, handle, event, payload, deadline=deadline,
        )
        raw = _read_reply(k, handle, event, deadline=deadline)
    finally:
        k.CloseHandle(event)
        k.CloseHandle(handle)
    return UntrustedManagementResponse.parse(
        raw, expected=request, now=datetime.now(timezone.utc),
    )


def read_windows_platform_status(
    *, pipe_name: str, expected_platform_id: str, expected_generation: int,
    wait_seconds: float = _MAX_WAIT,
) -> UntrustedManagementResponse:
    """Request only the reviewed platform.status projection."""
    return read_windows_management(
        pipe_name=pipe_name, expected_platform_id=expected_platform_id,
        expected_generation=expected_generation, operation="platform.status",
        wait_seconds=wait_seconds,
    )


def read_windows_platform_startup(
    *, pipe_name: str, expected_platform_id: str, expected_generation: int,
    wait_seconds: float = _MAX_WAIT,
) -> UntrustedManagementResponse:
    """Request only the reviewed startup.status projection."""
    return read_windows_management(
        pipe_name=pipe_name, expected_platform_id=expected_platform_id,
        expected_generation=expected_generation, operation="startup.status",
        wait_seconds=wait_seconds,
    )


def read_windows_core_inventory(
    *, pipe_name: str, expected_platform_id: str, expected_generation: int,
    wait_seconds: float = _MAX_WAIT,
) -> UntrustedManagementResponse:
    """Request only the reviewed core.list projection."""
    return read_windows_management(
        pipe_name=pipe_name, expected_platform_id=expected_platform_id,
        expected_generation=expected_generation, operation="core.list",
        wait_seconds=wait_seconds,
    )
