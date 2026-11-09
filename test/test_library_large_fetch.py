"""D028 large-parent service orchestration, current authority and state truth.

The stubbed coordinator tests intentionally do not claim physical transfer or
installed-host acceptance; the TLS test exercises actual disposable mTLS bytes.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import os
from pathlib import Path
import ssl
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.library_large_parent import verify_signed_large_parent
from sofia.platform.ops.library_large_fetch import fetch_signed_parent_chunks
from sofia.platform.ops.library_tls_chunk_transport import (
    receive_one_chunk, serve_one_chunk,
)
from test.test_library_large_parent import _signed_parent
from test.test_library_tls_chunk_transport import _pair


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-private quarantine test")
def test_large_parent_transfer_never_reports_publisher_verified_until_b1(
    tmp_path, monkeypatch,
):
    import sofia.platform.ops.library_large_fetch as service
    doc, raw, transfer, kwargs, sign = _signed_parent(huge=True)
    receiver = ChunkedArtifactReceiver(
        tmp_path / "quarantine", max_bytes=transfer.size_bytes + 1024,
    )
    network_calls = []
    def fake_fetch(**options):
        network_calls.append(options)
        # A valid signed parent is necessary, but only the first logical
        # 1-MiB chunk is claimed here. No large object is allocated.
        expected = options["signed_chunk_sha256"](
            0, options["chunk_bytes"],
        )
        assert expected == doc["chunk_sha256s"][0]
        assert options["publisher_current"](transfer) is True
        return options["chunk_bytes"]
    monkeypatch.setattr(service, "fetch_resumable_chunks", fake_fetch)
    result = fetch_signed_parent_chunks(
        signed_parent_bytes=raw, transfer=transfer,
        trusted_publisher_public_key=kwargs["trusted_publisher_public_key"],
        expected_publisher_key_sha256=kwargs["expected_publisher_key_sha256"],
        publisher_key_current=lambda _: True,
        publisher_current=lambda _: True, current_host_admit=lambda _: True,
        clock=lambda: kwargs["now"], receiver=receiver,
        open_enrolled_tls=lambda: None,
        expected_peer_certificate_sha256="a" * 64,
        authorize_peer=lambda *_: True,
        max_chunks=1,
    )
    assert result["large_artifact"] is True
    assert result["parent_chunks"] == 513
    assert result["received_bytes"] == 1024 * 1024
    assert result["verified_bytes"] == 0
    assert result["cache_state"] == "RECEIVING"
    assert result["install_executed"] is False
    assert result["installed"] is None and result["active"] is None
    assert len(network_calls) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-private quarantine test")
def test_signed_parent_revocation_blocks_network_before_dial(
    tmp_path, monkeypatch,
):
    import sofia.platform.ops.library_large_fetch as service
    doc, raw, transfer, kwargs, sign = _signed_parent()
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    invoked = []
    monkeypatch.setattr(
        service, "fetch_resumable_chunks",
        lambda **_: invoked.append("network"),
    )
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        fetch_signed_parent_chunks(
            signed_parent_bytes=raw, transfer=transfer,
            trusted_publisher_public_key=kwargs["trusted_publisher_public_key"],
            expected_publisher_key_sha256=kwargs["expected_publisher_key_sha256"],
            publisher_key_current=lambda _: True,
            publisher_current=lambda _: False,
            current_host_admit=lambda _: True,
            clock=lambda: kwargs["now"], receiver=receiver,
            open_enrolled_tls=lambda: None,
            expected_peer_certificate_sha256="a" * 64,
            authorize_peer=lambda *_: True,
        )
    assert invoked == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-private quarantine test")
def test_signed_parent_partial_resume_refuses_nonparent_boundary(tmp_path):
    doc, raw, transfer, kwargs, sign = _signed_parent(huge=True)
    receiver = ChunkedArtifactReceiver(
        tmp_path / "quarantine", max_bytes=transfer.size_bytes + 1024,
    )
    with pytest.raises(ChunkTransferRejected, match="partial chunk"):
        fetch_signed_parent_chunks(
            signed_parent_bytes=raw, transfer=transfer,
            trusted_publisher_public_key=kwargs["trusted_publisher_public_key"],
            expected_publisher_key_sha256=kwargs["expected_publisher_key_sha256"],
            publisher_key_current=lambda _: True,
            publisher_current=lambda _: True,
            current_host_admit=lambda _: True,
            clock=lambda: kwargs["now"], receiver=receiver,
            open_enrolled_tls=lambda: None,
            expected_peer_certificate_sha256="a" * 64,
            authorize_peer=lambda *_: True, start_offset=2,
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX private store and mTLS test")
def test_live_disposable_tls_chunk_matches_independent_signed_parent(tmp_path):
    doc, raw, transfer, kwargs, sign = _signed_parent()
    verified = verify_signed_large_parent(raw, **kwargs)
    source = tmp_path / "verified-cache"
    data = b"public-tiny-test-package"
    source.write_bytes(data)
    source.chmod(0o600)
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    server, client = _pair(tmp_path)
    errors = []
    def serve():
        try:
            serve_one_chunk(
                server,
                lookup_transfer=lambda digest: (
                    transfer if digest == transfer.content_sha256 else None
                ),
                authorize_peer=lambda *_: True,
                publisher_current=lambda _: True,
                resolve_verified_cache=lambda _: source,
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            server.close()
    thread = Thread(target=serve)
    thread.start()
    try:
        result = receive_one_chunk(
            client, transfer=transfer, offset=0, length=len(data),
            receiver=receiver,
            authorize_peer=lambda *_: True,
            publisher_current=lambda _: True,
            expected_signed_chunk_sha256=verified.expected_chunk_sha256(
                0, len(data),
            ),
        )
    finally:
        client.close()
        thread.join(timeout=8)
    assert not thread.is_alive()
    assert not errors
    assert result == len(data)
    assert receiver.finalize(
        transfer, authorize=lambda _: True,
    ).read_bytes() == data


@pytest.mark.skipif(os.name == "nt", reason="POSIX private store and mTLS test")
def test_tls_receiver_denies_chunk_disagreeing_with_publisher_parent(tmp_path):
    doc, raw, transfer, kwargs, sign = _signed_parent()
    source = tmp_path / "verified-cache"
    data = b"public-tiny-test-package"
    source.write_bytes(data)
    source.chmod(0o600)
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=65536)
    server, client = _pair(tmp_path)
    errors = []
    def serve():
        try:
            serve_one_chunk(
                server,
                lookup_transfer=lambda digest: (
                    transfer if digest == transfer.content_sha256 else None
                ),
                authorize_peer=lambda *_: True,
                publisher_current=lambda _: True,
                resolve_verified_cache=lambda _: source,
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            server.close()
    thread = Thread(target=serve)
    thread.start()
    try:
        with pytest.raises(ChunkTransferRejected, match="signed parent"):
            receive_one_chunk(
                client, transfer=transfer, offset=0, length=len(data),
                receiver=receiver,
                authorize_peer=lambda *_: True,
                publisher_current=lambda _: True,
                expected_signed_chunk_sha256="f" * 64,
            )
    finally:
        client.close()
        thread.join(timeout=8)
    assert not thread.is_alive()
    assert receiver.received_bytes(
        transfer, authorize=lambda _: True,
    ) == 0
