"""D028 sender/receiver tests use only disposable files and inert grants."""
from hashlib import sha256
import os

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    PinnedChunkTransfer, ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.library_chunk_sender import read_authorized_cached_chunk

pytestmark = [
    pytest.mark.pkg_ops, pytest.mark.pkg_safe,
    pytest.mark.skipif(os.name != "posix", reason="Unix private file-mode fixture"),
]


def _source(tmp_path):
    data = b"published-signed-test-fixture" * 15
    path = tmp_path / "signed-cache"
    path.write_bytes(data)
    pin = PinnedChunkTransfer(
        "origin-1", "target-1", sha256(data).hexdigest(), len(data), 1,
        sha256(b"manifest").hexdigest(), 1, "module", "permitted", "public",
    )
    args = {
        "authorize": lambda _pin: True,
        "publisher_current": lambda _pin: True,
        "resolve_verified_cache": lambda _pin: path,
    }
    return data, pin, args


def test_bounded_sender_receiver_roundtrip(tmp_path):
    data, pin, args = _source(tmp_path)
    receiver = ChunkedArtifactReceiver(tmp_path / "recv", max_bytes=1024 * 1024)
    for offset in range(0, len(data), 31):
        chunk, digest = read_authorized_cached_chunk(
            pin, offset=offset, length=min(31, len(data) - offset), **args,
        )
        receiver.append_chunk(
            pin, offset=offset, chunk=chunk, chunk_sha256=digest,
            authorize=lambda _: True,
        )
    assert receiver.finalize(pin, authorize=lambda _: True).read_bytes() == data


def test_sender_denies_revoked_grant(tmp_path):
    _data, pin, args = _source(tmp_path)
    args["authorize"] = lambda _: False
    with pytest.raises(ChunkTransferRejected):
        read_authorized_cached_chunk(pin, offset=0, length=10, **args)


def test_sender_rejects_bad_offset_and_unavailable_cache(tmp_path):
    data, pin, args = _source(tmp_path)
    with pytest.raises(ChunkTransferRejected):
        read_authorized_cached_chunk(pin, offset=len(data), length=1, **args)
    args["resolve_verified_cache"] = lambda _: tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        read_authorized_cached_chunk(pin, offset=0, length=1, **args)


def test_sender_rejects_hardlinked_object(tmp_path):
    _data, pin, args = _source(tmp_path)
    path = args["resolve_verified_cache"](pin)
    (tmp_path / "second").hardlink_to(path)
    with pytest.raises(ChunkTransferRejected):
        read_authorized_cached_chunk(pin, offset=0, length=20, **args)
