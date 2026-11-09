"""D028 signed offline capsule must not allocate whole release assets in RAM.

This exercises the actual deterministic STORED-ZIP helper on a bounded sparse
64MiB file and verifies that publisher-index SHA and file identity are not
changed during copying. It is not independently signed production host media.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tracemalloc
import zipfile

import pytest

from sofia.platform.ops.platform_installer_offline_capsule import (
    _archive_file_member, _verify_zip_member_stream,
    _verified_stream_source,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected


def _fixture(tmp_path, size=64 * 1024 * 1024):
    source = tmp_path / "signed-runtime.bin"
    with source.open("wb") as writer:
        writer.truncate(size)
    digest = sha256()
    with source.open("rb") as reader:
        while chunk := reader.read(65536):
            digest.update(chunk)
    return source, digest.hexdigest(), size


@pytest.mark.slow
def test_large_sparse_signed_asset_streams_with_bounded_builder_memory(tmp_path):
    source, digest, size = _fixture(tmp_path)
    archive = tmp_path / "capsule.zip"
    tracemalloc.start()
    try:
        _verified_stream_source(
            source, expected_sha256=digest, expected_size=size,
        )
        with zipfile.ZipFile(archive, "w", allowZip64=True) as zipper:
            _archive_file_member(
                zipper, "aegis/assets/runtime.bin", source,
                expected_sha256=digest, expected_size=size,
            )
        with zipfile.ZipFile(archive) as zipper:
            _verify_zip_member_stream(
                zipper, name="aegis/assets/runtime.bin",
                expected_sha256=digest, expected_size=size,
            )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 12 * 1024**2
    assert archive.stat().st_size >= size
    with zipfile.ZipFile(archive) as zipper:
        assert zipper.getinfo("aegis/assets/runtime.bin").file_size == size


def test_streaming_capsule_rejects_tampered_signed_file_before_zip(tmp_path):
    source, digest, size = _fixture(tmp_path, size=256 * 1024)
    with source.open("r+b") as handle:
        handle.seek(0)
        handle.write(b"tampered")
    with pytest.raises(PlatformReleaseRejected, match="bytes|inode"):
        _verified_stream_source(
            source, expected_sha256=digest, expected_size=size,
        )
    with zipfile.ZipFile(tmp_path / "output.zip", "w") as zipper:
        with pytest.raises(PlatformReleaseRejected, match="bytes|inode"):
            _archive_file_member(
                zipper, "aegis/assets/runtime.bin", source,
                expected_sha256=digest, expected_size=size,
            )


@pytest.mark.skipif(os.name == "nt", reason="POSIX inode/hardlink review")
def test_streaming_capsule_denies_hardlinked_or_redirected_signed_asset(tmp_path):
    source, digest, size = _fixture(tmp_path, size=64 * 1024)
    extra = tmp_path / "foreign-hardlink"
    os.link(source, extra)
    with pytest.raises(PlatformReleaseRejected, match="inode"):
        _verified_stream_source(source, expected_sha256=digest, expected_size=size)
    extra.unlink()
    redir = tmp_path / "redirect"
    redir.symlink_to(source)
    with pytest.raises(PermissionError):
        _verified_stream_source(redir, expected_sha256=digest, expected_size=size)


def test_zip_stream_check_fails_if_archive_member_is_corrupt(tmp_path):
    source, digest, size = _fixture(tmp_path, size=8192)
    destination = tmp_path / "archive.zip"
    with zipfile.ZipFile(destination, "w") as zipper:
        zipper.writestr("aegis/assets/runtime.bin", b"X" * size)
    with zipfile.ZipFile(destination) as zipper:
        with pytest.raises(PlatformReleaseRejected, match="bytes differ"):
            _verify_zip_member_stream(
                zipper, name="aegis/assets/runtime.bin",
                expected_sha256=digest, expected_size=size,
            )
