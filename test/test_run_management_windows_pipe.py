"""Native Windows named-pipe client identity must come from token impersonation."""
from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import os
from threading import Event, Thread
from time import sleep
from uuid import uuid4

import pytest

from sofia.platform.run.management_windows_pipe import (
    ManagementWindowsPipeListener, require_windows_pipe_peer,
)

WINDOWS = os.name == "nt"
pytestmark = pytest.mark.skipif(not WINDOWS, reason="Win32 security-token API")


def test_no_client_supplied_sid_is_authority():
    with pytest.raises(PermissionError):
        require_windows_pipe_peer(1234)


def test_native_client_token_sid_and_protected_pipe_round_trip():
    from sofia.platform.run.management_windows_pipe import _api
    import ctypes.wintypes as wt

    observed = []
    def dispatch(raw, *, authenticated_peer, now):
        observed.append((raw, authenticated_peer, now))
        return {"outcome": "OK", "data": {"observed": True}}

    name = "AegisTest-" + uuid4().hex
    stop = Event()
    with ManagementWindowsPipeListener(name, dispatch=dispatch) as server:
        worker = Thread(target=server.serve_until, args=(stop,), daemon=True)
        worker.start()
        k, _ = _api()
        k.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                 wt.DWORD, wt.DWORD, wt.HANDLE]
        k.CreateFileW.restype = wt.HANDLE
        # Client explicitly enables impersonation quality on its token;
        # server never trusts a claimed name, PID or SID in request JSON.
        handle = None
        for _ in range(60):
            value = k.CreateFileW(server.name, 0xC0000000, 0, None, 3, 0x120000, None)
            if value not in (None, ctypes.c_void_p(-1).value):
                handle = value
                break
            sleep(0.03)
        assert handle is not None
        try:
            wire = b'{"sid":"S-1-5-999999"}\n'
            buf = ctypes.create_string_buffer(wire)
            count = wt.DWORD()
            assert k.WriteFile(handle, buf, len(wire), ctypes.byref(count), None)
            assert count.value == len(wire)
            reply = ctypes.create_string_buffer(4096)
            got = wt.DWORD()
            for _ in range(80):
                if k.ReadFile(handle, reply, 4096, ctypes.byref(got), None):
                    break
                sleep(0.02)
            assert got.value > 0
            assert b'"observed":true' in reply.raw[:got.value]
        finally:
            k.CloseHandle(handle)
            stop.set()
            worker.join(timeout=4)
        assert not worker.is_alive()
    assert observed
    assert observed[0][0] == b'{"sid":"S-1-5-999999"}'
    assert observed[0][1].startswith("windows:sid:S-1-5-")
    assert observed[0][1] != "windows:sid:S-1-5-999999"
    assert isinstance(observed[0][2], datetime)
    assert observed[0][2].tzinfo == timezone.utc


def test_bad_pipe_names_rejected_without_os_activation():
    for bad in ("", "..\\other", "x" * 150, "name/name"):
        with pytest.raises(ValueError):
            ManagementWindowsPipeListener(bad, dispatch=lambda *_a, **_k: {})
