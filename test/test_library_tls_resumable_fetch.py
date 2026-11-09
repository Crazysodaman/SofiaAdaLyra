"""D028 disposable mTLS resume orchestration, not installed-host certification."""
from __future__ import annotations

from hashlib import sha256
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
    enrolled_server_sha256 = sha256(ssl.PEM_cert_to_DER_cert(server_cert.read_text())).hexdigest()

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
        expected_peer_certificate_sha256=enrolled_server_sha256,
        authorize_peer=grant, publisher_current=lambda _: True,
        chunk_bytes=16384, max_chunks=2,
    )
    assert partial == 32768
    assert receiver.received_bytes(transfer, authorize=lambda _: True) == partial

    # A second call uses durable bytes, never rewinds or trusts Hub offsets.
    final = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver, open_enrolled_tls=open_tls,
        expected_peer_certificate_sha256=enrolled_server_sha256,
        authorize_peer=grant, publisher_current=lambda _: True,
        chunk_bytes=16384, max_chunks=20, start_offset=partial,
    )
    assert final == len(payload)
    for worker in workers:
        worker.join(timeout=8)
        assert not worker.is_alive()
    assert not failures
    assert len(authorizations) > 4
    assert all(length > 0 for _, length in authorizations)
    assert not any(offset == 0 and length == 0 for offset, length in authorizations)
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
            expected_peer_certificate_sha256="a" * 64,
            authorize_peer=lambda *_: True, publisher_current=lambda _: False,
            chunk_bytes=1024,
        )
    assert opened == []


def test_reject_missing_canonical_tls_source(tmp_path):
    transfer = _transfer(b"valid")
    with pytest.raises(ChunkTransferRejected, match="canonical quarantine receiver"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=object(),
            open_enrolled_tls=lambda: None,
            expected_peer_certificate_sha256="a" * 64,
            authorize_peer=lambda *_: True,
            publisher_current=lambda _: True,
        )


def test_reject_invalid_resume_cursor_without_network(tmp_path):
    transfer = _transfer(b"known-bytes")
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    opened = []
    def must_not_dial():
        opened.append(True)
        raise AssertionError("invalid resume must not start network")
    for bad_offset in (-1, transfer.size_bytes, transfer.size_bytes + 1, True):
        with pytest.raises(ChunkTransferRejected, match="resume cursor"):
            fetch_resumable_chunks(
                transfer=transfer, receiver=receiver,
                open_enrolled_tls=must_not_dial,
                expected_peer_certificate_sha256="a" * 64,
                authorize_peer=lambda *_: True,
                publisher_current=lambda _: True,
                start_offset=bad_offset,
            )
    assert not opened


@pytest.mark.skipif(os.name == "nt", reason="POSIX private CAS mode verification")
def test_wrong_enrolled_peer_certificate_denied_before_transfer(tmp_path):
    payload = b"wrong-peer" * 100
    transfer = _transfer(payload)
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = server_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.verify_mode = ssl.CERT_REQUIRED
    server_ctx.load_verify_locations(cafile=str(ca))
    server_ctx.load_cert_chain(str(server_cert), str(server_key))
    client_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    client_ctx.minimum_version = client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.load_cert_chain(str(client_cert), str(client_key))
    worker_threads = []
    def open_tls():
        left, right = socket.socketpair()
        server = server_ctx.wrap_socket(left, server_side=True, do_handshake_on_connect=False)
        client = client_ctx.wrap_socket(
            right, server_hostname="localhost", do_handshake_on_connect=False,
        )
        server.settimeout(5)
        client.settimeout(5)
        def handshake():
            try:
                server.do_handshake()
            finally:
                server.close()
        thread = Thread(target=handshake)
        thread.start()
        worker_threads.append(thread)
        client.do_handshake()
        return client

    with pytest.raises(ChunkTransferRejected, match="owner-enrolled certificate"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=receiver,
            open_enrolled_tls=open_tls,
            expected_peer_certificate_sha256="0" * 64,
            authorize_peer=lambda *_: True,
            publisher_current=lambda _: True,
            chunk_bytes=1000,
        )
    for worker in worker_threads:
        worker.join(timeout=8)
        assert not worker.is_alive()
    assert receiver.received_bytes(transfer, authorize=lambda _: True) == 0


def test_missing_enrolled_cert_pin_denied_before_network(tmp_path):
    transfer = _transfer(b"some content")
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    calls = []
    def do_not_dial():
        calls.append("dial")
        raise AssertionError("untrusted peer must not dial")
    with pytest.raises(ChunkTransferRejected, match="certificate pin"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=receiver, open_enrolled_tls=do_not_dial,
            expected_peer_certificate_sha256="untrusted",
            authorize_peer=lambda *_: True, publisher_current=lambda _: True,
        )
    assert calls == []
