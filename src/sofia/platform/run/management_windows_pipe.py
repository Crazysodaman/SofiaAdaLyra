"""Windows local management named pipe with OS token-authenticated clients.

No automatic activation. Native Win32 impersonation, not a client-supplied
SID/PID/JSON field, supplies identity. Security descriptor allows only the
service token SID and LOCAL SYSTEM; enrollment remains a separate SAFE gate.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
from datetime import datetime, timezone
import json
import os
import re
from threading import Event
from time import monotonic, sleep

MAX_REQUEST = 32 * 1024
MAX_RESPONSE = 32 * 1024
_TIMEOUT = 2.0
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")

PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_BYTE = 0
PIPE_READMODE_BYTE = 0
PIPE_NOWAIT = 1
PIPE_REJECT_REMOTE_CLIENTS = 8
TOKEN_QUERY = 8
TOKEN_USER = 1
ERROR_PIPE_CONNECTED = 535
ERROR_PIPE_LISTENING = 536
ERROR_NO_DATA = 232
ERROR_BROKEN_PIPE = 109
ERROR_MORE_DATA = 234


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_uint32)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("User", _SidAndAttributes)]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", ctypes.c_uint32),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", ctypes.c_int),
    ]


def _api():
    if os.name != "nt":
        raise PermissionError("Windows native named-pipe identity unavailable")
    import ctypes.wintypes as wt
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    H, D, P = wt.HANDLE, wt.DWORD, ctypes.c_void_p
    k.GetCurrentProcess.restype = H
    k.GetCurrentThread.restype = H
    k.CloseHandle.argtypes = [H]
    k.CloseHandle.restype = wt.BOOL
    k.LocalFree.argtypes = [P]
    k.LocalFree.restype = P
    k.CreateNamedPipeW.argtypes = [
        wt.LPCWSTR, D, D, D, D, D, D, ctypes.POINTER(_SecurityAttributes)
    ]
    k.CreateNamedPipeW.restype = H
    k.ConnectNamedPipe.argtypes = [H, P]
    k.ConnectNamedPipe.restype = wt.BOOL
    k.DisconnectNamedPipe.argtypes = [H]
    k.DisconnectNamedPipe.restype = wt.BOOL
    k.ReadFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
    k.ReadFile.restype = wt.BOOL
    k.WriteFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
    k.WriteFile.restype = wt.BOOL
    a.OpenProcessToken.argtypes = [H, D, ctypes.POINTER(H)]
    a.OpenProcessToken.restype = wt.BOOL
    a.OpenThreadToken.argtypes = [H, D, wt.BOOL, ctypes.POINTER(H)]
    a.OpenThreadToken.restype = wt.BOOL
    a.GetTokenInformation.argtypes = [H, D, P, D, ctypes.POINTER(D)]
    a.GetTokenInformation.restype = wt.BOOL
    a.ConvertSidToStringSidW.argtypes = [P, ctypes.POINTER(ctypes.c_wchar_p)]
    a.ConvertSidToStringSidW.restype = wt.BOOL
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wt.LPCWSTR, D, ctypes.POINTER(P), ctypes.POINTER(D)
    ]
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wt.BOOL
    a.ImpersonateNamedPipeClient.argtypes = [H]
    a.ImpersonateNamedPipeClient.restype = wt.BOOL
    a.RevertToSelf.restype = wt.BOOL
    return k, a


def _sid_from_token(k, a, token):
    import ctypes.wintypes as wt
    size = wt.DWORD()
    a.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(size))
    if not 1 <= size.value <= 16384:
        raise PermissionError("invalid Win32 token-user size")
    buffer = ctypes.create_string_buffer(size.value)
    if not a.GetTokenInformation(
        token, TOKEN_USER, buffer, size, ctypes.byref(size)
    ):
        raise PermissionError("Win32 token user cannot be read")
    sid = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents.User.Sid
    if not sid:
        raise PermissionError("empty Win32 token SID")
    text = ctypes.c_wchar_p()
    if not a.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise PermissionError("Win32 token SID conversion refused")
    try:
        value = text.value
    finally:
        k.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    if not value or not re.fullmatch(r"S-1-[0-9-]+", value):
        raise PermissionError("unsafe native Win32 SID")
    return value


def _own_sid(k, a):
    import ctypes.wintypes as wt
    token = wt.HANDLE()
    if not a.OpenProcessToken(k.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise PermissionError("Win32 service token unavailable")
    try:
        return _sid_from_token(k, a, token)
    finally:
        k.CloseHandle(token)


def require_windows_pipe_peer(handle) -> str:
    """Impersonate the *connected* client's kernel token; never trust JSON."""
    k, a = _api()
    import ctypes.wintypes as wt
    if not a.ImpersonateNamedPipeClient(handle):
        raise PermissionError("named-pipe client OS impersonation denied")
    try:
        token = wt.HANDLE()
        if not a.OpenThreadToken(k.GetCurrentThread(), TOKEN_QUERY, True, ctypes.byref(token)):
            raise PermissionError("named-pipe client token unavailable")
        try:
            sid = _sid_from_token(k, a, token)
        finally:
            k.CloseHandle(token)
    finally:
        if not a.RevertToSelf():
            raise RuntimeError("Windows service failed to revert impersonation")
    return "windows:sid:" + sid


class ManagementWindowsPipeListener:
    """One protected native named-pipe instance, one bounded read per client."""

    def __init__(
        self, name: str, *, dispatch: Callable[..., Mapping[str, object]],
        enrolled_operator_sid: str | None = None,
    ) -> None:
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise ValueError("bounded Aegis pipe name required")
        if not callable(dispatch):
            raise TypeError("service-owned dispatcher required")
        if enrolled_operator_sid is not None and re.fullmatch(
            r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", enrolled_operator_sid
        ) is None:
            raise PermissionError("operator DACL requires individually enrolled user SID")
        self.name = "\\\\.\\pipe\\" + name
        self._dispatch = dispatch
        self._enrolled_operator_sid = enrolled_operator_sid
        self._handle = None

    def open(self):
        k, a = _api()
        import ctypes.wintypes as wt
        sid = _own_sid(k, a)
        sddl = "D:P(A;;GA;;;SY)(A;;GA;;;" + sid + ")"
        if self._enrolled_operator_sid is not None and self._enrolled_operator_sid != sid:
            # GRGW (read/write) only, no generic-all ACL for an external
            # operator, and NEVER a group/Everyone/Administrators SID.
            sddl += "(A;;GRGW;;;" + self._enrolled_operator_sid + ")"
        sd = ctypes.c_void_p()
        if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(sd), None
        ):
            raise PermissionError("failed to create private pipe DACL")
        try:
            attr = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), sd, 0)
            handle = k.CreateNamedPipeW(
                self.name, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_NOWAIT | PIPE_REJECT_REMOTE_CLIENTS,
                1, MAX_RESPONSE + 1, MAX_REQUEST + 1, 0, ctypes.byref(attr)
            )
            if handle in (None, ctypes.c_void_p(-1).value):
                raise PermissionError("Windows pipe path occupied or cannot be secured")
            self._handle = handle
            return self
        finally:
            k.LocalFree(sd)

    def serve_once(self) -> bool:
        k, _ = _api()
        if self._handle is None:
            raise RuntimeError("Windows management pipe not open")
        connected = k.ConnectNamedPipe(self._handle, None)
        if not connected:
            error = ctypes.get_last_error()
            if error == ERROR_PIPE_LISTENING:
                return False
            if error == ERROR_NO_DATA:
                k.DisconnectNamedPipe(self._handle)
                return False
            if error != ERROR_PIPE_CONNECTED:
                raise PermissionError("Windows pipe connection unavailable")
        try:
            deadline = monotonic() + _TIMEOUT
            raw = bytearray()
            while True:
                if monotonic() >= deadline:
                    raise TimeoutError("Windows pipe request exceeded deadline")
                block = ctypes.create_string_buffer(4096)
                count = ctypes.c_uint32()
                success = k.ReadFile(
                    self._handle, block,
                    min(4096, MAX_REQUEST + 1 - len(raw)),
                    ctypes.byref(count), None
                )
                if not success:
                    error = ctypes.get_last_error()
                    if error in {ERROR_NO_DATA, ERROR_PIPE_LISTENING}:
                        sleep(0.01)
                        continue
                    raise PermissionError("Windows pipe request read refused")
                if count.value == 0:
                    sleep(0.01)
                    continue
                raw.extend(block.raw[:count.value])
                if len(raw) > MAX_REQUEST:
                    raise ValueError("Windows pipe request exceeds bound")
                if b"\n" in raw:
                    if raw.count(b"\n") != 1 or raw[-1:] != b"\n":
                        raise ValueError("Windows pipe pipelining rejected")
                    break
            peer = require_windows_pipe_peer(self._handle)
            response = self._dispatch(
                bytes(raw[:-1]), authenticated_peer=peer,
                now=datetime.now(timezone.utc),
            )
            if not isinstance(response, Mapping):
                raise ValueError("invalid Windows management response type")
            body = json.dumps(
                response, ensure_ascii=False, allow_nan=False,
                separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            if not body or len(body) > MAX_RESPONSE:
                raise ValueError("Windows management response exceeds bound")
            written = ctypes.c_uint32()
            buffer = ctypes.create_string_buffer(body + b"\n")
            if not k.WriteFile(
                self._handle, buffer, len(body) + 1, ctypes.byref(written), None
            ) or written.value != len(body) + 1:
                raise OSError("Windows management response transport unavailable")
            return True
        except (PermissionError, ValueError, TimeoutError, OSError):
            return False
        finally:
            k.DisconnectNamedPipe(self._handle)

    def serve_until(self, stopped: Event) -> None:
        if not isinstance(stopped, Event):
            raise TypeError("threading.Event required")
        while not stopped.is_set():
            if self._handle is None:
                raise RuntimeError("Windows management pipe closed")
            self.serve_once()
            if not stopped.is_set():
                stopped.wait(0.02)

    def close(self) -> None:
        if self._handle is not None:
            k, _ = _api()
            k.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *_):
        self.close()
