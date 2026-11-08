"""D028 disposable mTLS resume orchestration, not installed-host certification."""
from __future__ import annotations

import os
import socket
import ssl
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.library_tls_chunk_transport import serve_one_chunk
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks
from test.test_library_tls_chunk_transport import _transfer
from test.test_core_link_conversation import tls_material


@pytest.mark.skipif(os.name == "nt", reason="POSIX private CAS mode verification")
def test_authenticated_reconnect_resumes_durable_receiver(tmp_path):
    payload = b"public-artifact-for-d028-" * 9000
    transfer = _transfer(payload)
    source = tmp_path / "verified-cache"
    source.write_bytes(payload)
    source.chmod(0o600)
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=len(payload) + 128)
    workers = []
    failures = []
    authorizations = []

    # A real enrollment retains the same certificate across reconnects.
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = server_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.verify_mode = ssl.CERT_REQUIRED
    server_ctx.load_verify_locations(cafile=str(ca))
    server_ctx.load_cert_chain(str(server_cert), str(server_key))
    client_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    client_ctx.minimum_version = client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.load_cert_chain(str(client_cert), str(client_key))

    def tls_pair():
        a, b = socket.socketpair()
        server = server_ctx.wrap_socket(a, server_side=True, do_handshake_on_connect=False)
        client = client_ctx.wrap_socket(
            b, server_hostname="localhost", do_handshake_on_connect=False,
        )
        server.settimeout(5)
        client.settimeout(5)
        handshake_errors = []
        def handshake():
            try:
                server.do_handshake()
            except Exception as exc:
                handshake_errors.append(exc)
        thread = Thread(target=handshake)
        thread.start()
        try:
            client.do_handshake()
        finally:
            thread.join(timeout=8)
        if handshake_errors or thread.is_alive():
            server.close()
            client.close()
            raise AssertionError("re-enrolled mTLS handshake failed")
        return server, client

    def grant(sock, fingerprint, pinned, offset, length):
        assert len(fingerprint) == 64 and pinned == transfer
        authorizations.append((offset, length))
        return True

    def open_tls():
        server, client = tls_pair()
        def send():
            try:
                serve_one_chunk(
                    server,
                    lookup_transfer=lambda digest: transfer if digest == transfer.content_sha256 else None,
                    authorize_peer=grant,
                    publisher_current=lambda _: True,
                    resolve_verified_cache=lambda _: source,
                )
            except Exception as exc:
                failures.append(exc)
            finally:
                server.close()
        worker = Thread(target=send)
        worker.start()
        workers.append(worker)
        return client

    # First invocation must STOP after its declared chunk budget.
    partial = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver, open_enrolled_tls=open_tls,
        authorize_peer=grant, publisher_current=lambda _: True,
        chunk_bytes=16384, max_chunks=2,
    )
    assert partial == 32768
    assert receiver.received_bytes(transfer, authorize=lambda _: True) == partial

    # A second call uses durable bytes, never rewinds or trusts Hub offsets.
    final = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver, open_enrolled_tls=open_tls,
        authorize_peer=grant, publisher_current=lambda _: True,
        chunk_bytes=16384, max_chunks=20,
    )
    assert final == len(payload)
    for worker in workers:
        worker.join(timeout=8)
        assert not worker.is_alive()
    assert not failures
    assert len(authorizations) > 4
    assert receiver.finalize(transfer, authorize=lambda _: True).read_bytes() == payload


@pytest.mark.skipif(os.name == "nt", reason="POSIX private CAS mode verification")
def test_revoked_publisher_does_not_fetch_or_write(tmp_path):
    payload = b"revoked-artifact" * 100
    transfer = _transfer(payload)
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    opened = []
    def should_not_open():
        opened.append(True)
        raise AssertionError("must not dial revoked publisher")
    # Current publisher revocation is denied before outbound network access.
    with pytest.raises(ChunkTransferRejected, match="publisher trust"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=receiver, open_enrolled_tls=should_not_open,
            authorize_peer=lambda *_: True, publisher_current=lambda _: False,
            chunk_bytes=1024,
        )
    assert opened == []


def test_reject_missing_canonical_tls_source(tmp_path):
    transfer = _transfer(b"valid")
    with pytest.raises(ChunkTransferRejected, match="TLS"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=object(),
            open_enrolled_tls=lambda: None, authorize_peer=lambda *_: True,
            publisher_current=lambda _: True,
        )
