"""Kernel OS peer credentials are not a JSON owner grant."""
from datetime import datetime, timezone
import json
import os
import socket
import sys

import pytest

from sofia.platform.run.local_peer import (
    KernelUnixPeer, dispatch_one_kernel_peer_read,
    read_single_bounded_request, require_kernel_unix_peer,
)

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")
pytestmark = pytest.mark.skipif(not LINUX, reason="Linux SO_PEERCRED contract")


def pair():
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    return left, right


def test_peer_comes_from_linux_kernel_not_client_claims():
    server, client = pair()
    try:
        actor = require_kernel_unix_peer(server)
        assert isinstance(actor, KernelUnixPeer)
        assert actor.pid == os.getpid()
        assert actor.uid == os.getuid()
        assert actor.gid == os.getgid()
        assert actor.principal == f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        assert "owner" not in actor.principal
    finally:
        server.close()
        client.close()


def test_unconnected_socket_and_tcp_cannot_claim_kernel_unix_peer():
    unconnected = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PermissionError):
            require_kernel_unix_peer(unconnected)
        with pytest.raises(PermissionError):
            require_kernel_unix_peer(tcp)
    finally:
        unconnected.close()
        tcp.close()


def test_one_request_receives_real_kernel_identity_and_bounded_reply():
    server, client = pair()
    observed = []
    current = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)

    def service_dispatch(raw, *, authenticated_peer, now):
        observed.append((raw, authenticated_peer, now))
        return {
            "schema": "aegis.platform.management.read-response.v1",
            "source": "PLATFORM_SESSION", "result": "UNTRUSTED_WIRE_ONLY",
        }

    try:
        client.sendall(b'{"operation":"platform.status"}\n')
        dispatch_one_kernel_peer_read(
            server, dispatch=service_dispatch, now=current
        )
        result = json.loads(client.recv(4096))
        assert result["source"] == "PLATFORM_SESSION"
        assert observed == [(
            b'{"operation":"platform.status"}',
            f"unix:uid:{os.getuid()}:gid:{os.getgid()}", current,
        )]
    finally:
        server.close()
        client.close()


def test_socket_cannot_smuggle_a_second_message_or_extra_bytes():
    server, client = pair()
    try:
        client.sendall(b'{"a":1}\n{"a":2}\n')
        with pytest.raises(ValueError, match="pipelined"):
            read_single_bounded_request(server)
    finally:
        server.close()
        client.close()


def test_oversize_and_eof_fail_before_dispatch():
    server, client = pair()
    try:
        client.sendall(b"x" * 65536 + b"\n")
        with pytest.raises(ValueError, match="oversized"):
            read_single_bounded_request(server)
    finally:
        server.close()
        client.close()

    server, client = pair()
    try:
        client.shutdown(socket.SHUT_WR)
        with pytest.raises(ValueError, match="closed"):
            read_single_bounded_request(server)
    finally:
        server.close()
        client.close()


def test_timeout_does_not_wait_forever(monkeypatch):
    import sofia.platform.run.local_peer as local_peer
    monkeypatch.setattr(local_peer, "_IO_TIMEOUT", 0.01)
    server, client = pair()
    try:
        with pytest.raises(TimeoutError, match="deadline"):
            read_single_bounded_request(server)
    finally:
        server.close()
        client.close()


def test_dispatch_denial_never_sends_partial_error_or_exception():
    server, client = pair()

    def refuse(raw, **kwargs):
        raise PermissionError("owner authorization unavailable")

    try:
        client.sendall(b'{"operation":"platform.status","owner_grant":"fake"}\n')
        with pytest.raises(PermissionError, match="authorization"):
            dispatch_one_kernel_peer_read(
                server, dispatch=refuse,
                now=datetime.now(timezone.utc),
            )
        client.settimeout(0.01)
        with pytest.raises(socket.timeout):
            client.recv(16)
    finally:
        server.close()
        client.close()
