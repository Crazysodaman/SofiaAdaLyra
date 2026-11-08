"""D028 Hub: private binding, explicit owner role and disposable real mTLS read."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import socket
import ssl
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import (
    _tls_peer_fingerprint, receive_one_chunk,
)
from sofia.platform.ops.library_tls_hub import ApprovedLibraryHub, _private_bind
from test.test_core_link_conversation import tls_material


@pytest.mark.parametrize("bind", [
    "0.0.0.0", "::", "8.8.8.8", "1.1.1.1", "169.254.1.2",
    "example.com", "", "255.255.255.255",
])
def test_reject_public_unspecified_or_ambiguous_hub_bind(bind):
    with pytest.raises(ChunkTransferRejected):
        _private_bind(bind)


@pytest.mark.parametrize("bind", ["127.0.0.1", "192.168.17.5", "10.2.3.4", "::1", "fd00::4"])
def test_accept_only_explicit_local_or_private_lan_bind(bind):
    family, value = _private_bind(bind)
    assert family in (socket.AF_INET, socket.AF_INET6)
    assert value == bind


def _tls_contexts(tmp_path):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = server.maximum_version = ssl.TLSVersion.TLSv1_3
    server.verify_mode = ssl.CERT_REQUIRED
    server.load_verify_locations(cafile=str(ca))
    server.load_cert_chain(str(server_cert), str(server_key))
    client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    client.minimum_version = client.maximum_version = ssl.TLSVersion.TLSv1_3
    client.load_cert_chain(str(client_cert), str(client_key))
    return server, client


def _transfer(data):
    return PinnedChunkTransfer(
        "library-primary", "enrolled-recipient", sha256(data).hexdigest(),
        len(data), 3, "a" * 64, 9, "module", "permitted", "public",
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX CAS private mode semantics")
def test_explicit_hub_localhost_mutual_tls_verified_byte_exchange(tmp_path):
    source = b"public-signed-content-" * 150
    pin = _transfer(source)
    origin = tmp_path / "canonical_verified_cache"
    origin.write_bytes(source)
    origin.chmod(0o600)
    receiver = ChunkedArtifactReceiver(tmp_path / "receiver", max_bytes=65536)
    server_ctx, client_ctx = _tls_contexts(tmp_path)
    calls = []

    def grant(sock, fingerprint, transfer, offset, length):
        assert fingerprint == _tls_peer_fingerprint(sock)
        assert transfer == pin
        assert offset == 0 and length == len(source)
        calls.append(fingerprint)
        return True

    hub = ApprovedLibraryHub(
        bind_host="127.0.0.1", port=0, tls_context=server_ctx,
        owner_enabled=lambda: True,
        lookup_transfer=lambda digest: pin if digest == pin.content_sha256 else None,
        authorize_peer=grant, publisher_current=lambda _: True,
        resolve_verified_cache=lambda _: origin,
    )
    endpoint = hub.open()
    failures = []

    def run_hub():
        try:
            assert hub.serve_once() == len(source)
        except Exception as exc:
            failures.append(exc)

    thread = Thread(target=run_hub)
    thread.start()
    try:
        with socket.create_connection(endpoint, timeout=5) as raw:
            with client_ctx.wrap_socket(raw, server_hostname="localhost") as tls:
                tls.settimeout(5)
                assert receive_one_chunk(
                    tls, transfer=pin, offset=0, length=len(source),
                    receiver=receiver, authorize_peer=grant,
                    publisher_current=lambda _: True,
                ) == len(source)
    finally:
        thread.join(timeout=8)
        hub.close()
    assert not thread.is_alive()
    assert not failures
    assert len(calls) >= 4
    assert receiver.finalize(pin, authorize=lambda _: True).read_bytes() == source


def test_hub_denies_role_revoked_before_bind(tmp_path):
    server, _client = _tls_contexts(tmp_path)
    decisions = iter((True, False))
    hub = ApprovedLibraryHub(
        bind_host="127.0.0.1", port=0, tls_context=server,
        owner_enabled=lambda: next(decisions),
        lookup_transfer=lambda _: None, authorize_peer=lambda *_: False,
        publisher_current=lambda _: False, resolve_verified_cache=lambda _: None,
    )
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        hub.open()


def test_bounded_hub_loop_rechecks_owner_role_between_sessions():
    # No listener is opened or network used in this control-loop regression.
    hub = object.__new__(ApprovedLibraryHub)
    hub._listener = object()
    calls = []
    decisions = iter((True, True, False))
    hub._owner_enabled = lambda: next(decisions)
    def serve():
        calls.append(True)
        return 123
    hub.serve_once = serve
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        hub.serve_bounded(max_connections=3)
    assert len(calls) == 2


def test_bounded_hub_loop_rejects_invalid_budget():
    hub = object.__new__(ApprovedLibraryHub)
    for count in (0, -1, True, 10001):
        with pytest.raises(ChunkTransferRejected, match="budget"):
            hub.serve_bounded(max_connections=count)
