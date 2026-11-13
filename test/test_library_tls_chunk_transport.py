"""D028: actual disposable mutual TLS 1.3 chunk exchange, no owner grant or install."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import socket
import ssl
import struct
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import (
    MAX_CONTROL, _receive_frame, _tls_peer_fingerprint,
    receive_one_chunk, serve_one_chunk,
)
from test.test_core_link_conversation import tls_material


def _transfer(data: bytes) -> PinnedChunkTransfer:
    return PinnedChunkTransfer(
        source_platform_id="platform-source",
        target_platform_id="platform-target",
        content_sha256=sha256(data).hexdigest(),
        size_bytes=len(data), generation=2,
        manifest_sha256="a" * 64,
        catalog_revision=4,
        artifact_kind="module", license_distribution="permitted",
        data_class="public",
    )


def _pair(tmp_path: Path):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = server_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.verify_mode = ssl.CERT_REQUIRED
    server_ctx.load_verify_locations(cafile=str(ca))
    server_ctx.load_cert_chain(str(server_cert), str(server_key))
    client_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    client_ctx.minimum_version = client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.load_cert_chain(str(client_cert), str(client_key))

    a, b = socket.socketpair()
    server = server_ctx.wrap_socket(a, server_side=True, do_handshake_on_connect=False)
    client = client_ctx.wrap_socket(
        b, server_hostname="localhost", do_handshake_on_connect=False,
    )
    server.settimeout(5)
    client.settimeout(5)
    errors = []

    def handshake():
        try:
            server.do_handshake()
        except Exception as exc:
            errors.append(exc)

    worker = Thread(target=handshake)
    worker.start()
    try:
        client.do_handshake()
    finally:
        worker.join(timeout=8)
    if errors or worker.is_alive():
        server.close()
        client.close()
        raise AssertionError("verified disposable mutual TLS handshake did not complete")
    return server, client


@pytest.mark.skipif(os.name == "nt", reason="POSIX private CAS mode verification")
def test_verified_tls_chunk_exchange_and_resume(tmp_path):
    data = (b"independently-signed-public-artifact-" * 6000)
    t = _transfer(data)
    cache = tmp_path / "verified-object"
    cache.write_bytes(data)
    cache.chmod(0o600)
    receiver = ChunkedArtifactReceiver(tmp_path / "receiver", max_bytes=len(data) + 128)
    approvals = []

    def grant(channel, fingerprint, pinned, offset, length):
        assert isinstance(channel, ssl.SSLSocket)
        assert len(fingerprint) == 64
        assert fingerprint == _tls_peer_fingerprint(channel)
        assert pinned == t
        approvals.append((offset, length))
        return True

    offset = 0
    while offset < len(data):
        length = min(65536, len(data) - offset)
        server, client = _pair(tmp_path)
        failures = []
        def send():
            try:
                assert serve_one_chunk(
                    server, lookup_transfer=lambda digest: t if digest == t.content_sha256 else None,
                    authorize_peer=grant, publisher_current=lambda _: True,
                    resolve_verified_cache=lambda _: cache,
                ) == length
            except Exception as exc:
                failures.append(exc)
            finally:
                server.close()

        thread = Thread(target=send)
        thread.start()
        try:
            next_offset = receive_one_chunk(
                client, transfer=t, offset=offset, length=length, receiver=receiver,
                authorize_peer=grant, publisher_current=lambda _: True,
            )
        finally:
            client.close()
            thread.join(timeout=8)
        assert not thread.is_alive()
        assert not failures
        assert next_offset == offset + length
        offset = next_offset

    assert approvals
    # Final content integrity is NOT an independently signed publisher/install receipt.
    complete = receiver.finalize(t, authorize=lambda _: True)
    assert complete.read_bytes() == data
    assert complete.name == t.content_sha256


def test_plaintext_cannot_be_used_as_authorized_peer():
    with socket.socketpair()[0] as ordinary:
        with pytest.raises(ChunkTransferRejected, match="TLS"):
            _tls_peer_fingerprint(ordinary)


def test_oversized_control_frame_rejected_before_payload_read():
    a, b = socket.socketpair()
    b.settimeout(5)
    try:
        a.sendall(struct.pack("!I", MAX_CONTROL + 1))
        with pytest.raises(ChunkTransferRejected, match="unbounded"):
            _receive_frame(b, frozenset({"schema"}))
    finally:
        a.close()
        b.close()


def test_duplicate_control_properties_rejected():
    a, b = socket.socketpair()
    b.settimeout(5)
    payload = b'{"schema":"aegis.library.tls.chunk.v1","schema":"aegis.library.tls.chunk.v1"}'
    try:
        a.sendall(struct.pack("!I", len(payload)) + payload)
        with pytest.raises(ChunkTransferRejected, match="duplicate"):
            _receive_frame(b, frozenset({"schema"}))
    finally:
        a.close()
        b.close()


def test_control_frame_trickle_cannot_extend_total_tls_deadline(tmp_path):
    """Progress before each idle timeout must not renew the exchange budget."""
    import json
    from threading import Event

    server, client = _pair(tmp_path)
    client.settimeout(0.16)
    stop = Event()
    payload = json.dumps({"schema": "aegis.library.tls.chunk.v1"}).encode()
    header = struct.pack("!I", len(payload))

    def trickle():
        try:
            for byte in header:
                server.sendall(bytes([byte]))
                if stop.wait(0.07):
                    return
            server.sendall(payload)
        except OSError:
            # Expiry may close the connection while the peer is still writing.
            pass

    worker = Thread(target=trickle)
    worker.start()
    try:
        with pytest.raises(ChunkTransferRejected, match="deadline"):
            _receive_frame(client, frozenset({"schema"}))
        assert client.gettimeout() == 0.16
    finally:
        stop.set()
        worker.join(timeout=2)
        server.close()
        client.close()
    assert not worker.is_alive()


def test_payload_trickle_expires_without_advancing_durable_resume(tmp_path):
    """One exchange budget also covers payload; timed-out bytes are not accepted."""
    from threading import Event
    from sofia.platform.ops.library_tls_chunk_transport import SCHEMA, _frame

    prefix, data = b"previously-verified-", b"abcde"
    transfer = _transfer(prefix + data)
    receiver = ChunkedArtifactReceiver(tmp_path / "recipient", max_bytes=1024)
    receiver.append_chunk(
        transfer, offset=0, chunk=prefix, chunk_sha256=sha256(prefix).hexdigest(),
        authorize=lambda _: True,
    )
    server, client = _pair(tmp_path)
    client.settimeout(0.16)
    stop = Event()

    def trickle():
        try:
            _frame(server, {"schema": SCHEMA, "digest": transfer.content_sha256,
                            "offset": len(prefix), "length": len(data),
                            "chunk_sha256": sha256(data).hexdigest()})
            for byte in data:
                server.sendall(bytes([byte]))
                if stop.wait(0.07):
                    return
        except OSError:
            pass

    worker = Thread(target=trickle)
    worker.start()
    try:
        with pytest.raises(ChunkTransferRejected, match="deadline"):
            receive_one_chunk(
                client, transfer=transfer, offset=len(prefix), length=len(data),
                receiver=receiver, authorize_peer=lambda *args: True,
                publisher_current=lambda _: True,
                expected_signed_chunk_sha256=sha256(data).hexdigest(),
            )
        assert client.gettimeout() == 0.16
        assert receiver.received_bytes(transfer, authorize=lambda _: True) == len(prefix)
    finally:
        stop.set()
        worker.join(timeout=2)
        server.close()
        client.close()
    assert not worker.is_alive()
