"""D028 disposable mTLS resume orchestration, not installed-host certification."""
from __future__ import annotations

from hashlib import sha256
import os
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.library_tls_chunk_transport import serve_one_chunk
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks
from test.test_library_tls_chunk_transport import _pair, _transfer


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

    def grant(sock, fingerprint, pinned, offset, length):
        assert len(fingerprint) == 64 and pinned == transfer
        authorizations.append((offset, length))
        return True

    def open_tls():
        server, client = _pair(tmp_path)
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
    # Invalid configuration is denied before network access.
    with pytest.raises(ChunkTransferRejected, match="bounded chunk"):
        fetch_resumable_chunks(
            transfer=transfer, receiver=receiver, open_enrolled_tls=should_not_open,
            authorize_peer=lambda *_: True, publisher_current=lambda _: False,
            chunk_bytes=0,
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
