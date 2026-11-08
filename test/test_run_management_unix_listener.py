"""Linux management socket intake is actual OS IPC, never a grant."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import sys
from threading import Thread
from time import monotonic, sleep

import pytest

from sofia.platform.run.local_peer import read_single_bounded_request
from sofia.platform.run.management_unix_listener import ManagementUnixListener

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


def test_module_imports_without_starting_a_service():
    assert ManagementUnixListener.__name__ == "ManagementUnixListener"


@pytest.fixture
def private(tmp_path: Path) -> Path:
    path = tmp_path / "private"
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def round_trip(listener: ManagementUnixListener, raw: bytes) -> tuple[bytes, list[bool]]:
    results: list[bool] = []
    worker = Thread(target=lambda: results.append(listener.serve_once()))
    worker.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(listener.path))
            client.sendall(raw)
            result = client.recv(65537)
    finally:
        worker.join(timeout=4)
    assert not worker.is_alive()
    return result, results


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_real_private_socket_uses_kernel_peer_not_request_claim(private):
    seen = []

    def dispatch(raw, *, authenticated_peer, now):
        seen.append((raw, authenticated_peer, now))
        return {"schema": "read-response.v1", "data": {"ok": True}}

    with ManagementUnixListener(private / "a.sock", dispatch=dispatch) as listener:
        info = os.stat(listener.path)
        assert info.st_mode & 0o077 == 0
        payload, results = round_trip(
            listener, b'{"claimed_peer":"owner:forged"}\n'
        )
        assert b'"ok":true' in payload
        assert results == [True]
        assert seen[0][0] == b'{"claimed_peer":"owner:forged"}'
        assert seen[0][1] == f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        assert isinstance(seen[0][2], datetime)
        assert seen[0][2].tzinfo == timezone.utc
    assert not (private / "a.sock").exists()


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_current_authority_refusal_and_live_revocation_return_only_eof(private):
    current = {"enrolled": False, "stop": False, "revoke_midflight": False}
    observations = []

    def dispatch(raw, *, authenticated_peer, now):
        # A real composition would consult current SAFE-backed authority,
        # installation generation and STOP on BOTH sides of a provider call.
        if not current["enrolled"] or current["stop"]:
            raise PermissionError("denied before observation")
        observations.append(raw)
        if current["revoke_midflight"]:
            current["enrolled"] = False
        if not current["enrolled"] or current["stop"]:
            raise PermissionError("revoked during observation")
        return {"result": "visible"}

    with ManagementUnixListener(private / "b.sock", dispatch=dispatch) as listener:
        payload, results = round_trip(listener, b'{"request":"status"}\n')
        assert payload == b"" and results == [False]
        current["enrolled"] = True
        payload, results = round_trip(listener, b'{"request":"status"}\n')
        assert b"visible" in payload and results == [True]
        current["revoke_midflight"] = True
        payload, results = round_trip(listener, b'{"request":"status"}\n')
        assert payload == b"" and results == [False]
        assert len(observations) == 2
        current["enrolled"] = True
        current["revoke_midflight"] = False
        current["stop"] = True
        payload, results = round_trip(listener, b'{"request":"status"}\n')
        assert payload == b"" and results == [False]


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_nonprivate_directory_and_existing_endpoint_refused(private):
    existing = private / "taken.sock"
    existing.write_text("do not replace", encoding="utf-8")
    listener = ManagementUnixListener(existing, dispatch=lambda *_a, **_k: {})
    with pytest.raises(PermissionError, match="occupied"):
        listener.open()
    assert existing.read_text(encoding="utf-8") == "do not replace"

    private.chmod(0o755)
    try:
        with pytest.raises(PermissionError, match="permissions"):
            ManagementUnixListener(private / "c.sock", dispatch=lambda *_a, **_k: {}).open()
    finally:
        private.chmod(0o700)


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_second_listener_fails_and_owner_closes_only_own_socket(private):
    path = private / "s.sock"
    first = ManagementUnixListener(path, dispatch=lambda *_a, **_k: {})
    first.open()
    try:
        with pytest.raises(PermissionError, match="occupied"):
            ManagementUnixListener(path, dispatch=lambda *_a, **_k: {}).open()
    finally:
        first.close()
    assert not path.exists()


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_trickle_cannot_extend_absolute_intake_deadline(monkeypatch):
    import sofia.platform.run.local_peer as local_peer

    monkeypatch.setattr(local_peer, "_IO_TIMEOUT", 0.09)
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    def trickle():
        for _ in range(7):
            try:
                client.sendall(b"x")
            except OSError:
                return
            sleep(0.035)

    sender = Thread(target=trickle)
    sender.start()
    start = monotonic()
    try:
        with pytest.raises(TimeoutError, match="deadline"):
            read_single_bounded_request(server)
        assert monotonic() - start < 0.2
    finally:
        server.close()
        client.close()
        sender.join(timeout=2)


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_fresh_clock_sampled_after_request_complete(private):
    observed = []

    def dispatch(raw, *, authenticated_peer, now):
        observed.append(now)
        return {"ok": True}

    with ManagementUnixListener(private / "d.sock", dispatch=dispatch) as listener:
        payload, results = round_trip(listener, b"{}\n")
        assert results == [True]
        assert b"true" in payload
        assert datetime.now(timezone.utc).timestamp() - observed[0].timestamp() < 3
