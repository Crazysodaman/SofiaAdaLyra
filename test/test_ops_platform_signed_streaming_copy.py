"""Canonical signed B1 staging/install copy, bounded memory and failure safety.

Test-only source digests are deliberately synthetic. Trust still comes from
the original PlatformReleaseVerifier, which both B1 callers run on every
complete signed release. These tests never enroll an owner or launch Core.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tracemalloc

import pytest

from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.ops.platform_signed_asset_copy import copy_verified_signed_asset
from sofia.platform.state.artifact_file import read_artifact_file


def _source(tmp_path, size):
    source = tmp_path / "signed-publisher-runtime"
    with source.open("wb") as writer:
        writer.truncate(size)
    digest = sha256()
    with source.open("rb") as reader:
        while block := reader.read(65536):
            digest.update(block)
    return source, digest.hexdigest(), size


def test_streamed_signed_asset_creates_exact_private_copy_without_full_ram(tmp_path):
    source, digest, size = _source(tmp_path, 2 * 1024 * 1024 + 7)
    dest = tmp_path / "private-staging" / "assets" / "python-runtime.zip"
    tracemalloc.start()
    try:
        actual = copy_verified_signed_asset(
            source, dest, expected_sha256=digest, expected_size=size,
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert actual == dest
    assert actual.stat().st_size == size
    assert read_artifact_file(actual, size)[0] == digest
    assert peak < 8 * 1024 * 1024
    if os.name != "nt":
        assert actual.stat().st_mode & 0o077 == 0
        assert dest.parent.stat().st_mode & 0o077 == 0


@pytest.mark.slow
def test_signed_stage_copy_64mib_without_large_allocation(tmp_path):
    source, digest, size = _source(tmp_path, 64 * 1024 * 1024 + 1)
    dest = tmp_path / "private-staging" / "assets" / "large-runtime.zip"
    tracemalloc.start()
    try:
        copy_verified_signed_asset(
            source, dest, expected_sha256=digest, expected_size=size,
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert dest.stat().st_size == size
    assert peak < 12 * 1024 * 1024
    assert read_artifact_file(dest, size)[0] == digest


@pytest.mark.parametrize("mutation", [
    {"expected_size": True},
    {"expected_size": 0},
    {"expected_size": 512 * 1024**2 + 1},
    {"expected_sha256": "x" * 64},
    {"expected_sha256": "F" * 64},
])
def test_signed_copy_rejects_ill_typed_or_overlarge_reference_before_creation(
    tmp_path, mutation,
):
    src, digest, size = _source(tmp_path, 4096)
    dest = tmp_path / "not-published"
    with pytest.raises(PlatformReleaseRejected):
        copy_verified_signed_asset(
            src, dest, **{
                "expected_sha256": digest, "expected_size": size,
                **mutation,
            }
        )
    assert not dest.exists()


def test_signed_copy_rejects_wrong_manifest_digest_and_cleans_new_destination(tmp_path):
    src, digest, size = _source(tmp_path, 1048576)
    dest = tmp_path / "private" / "assets" / "untrusted-package"
    with pytest.raises(PlatformReleaseRejected, match="changed"):
        copy_verified_signed_asset(
            src, dest, expected_sha256="f" * 64, expected_size=size,
        )
    assert src.stat().st_size == size
    assert not dest.exists()


def test_signed_copy_never_overwrites_existing_installed_release_asset(tmp_path):
    source, digest, size = _source(tmp_path, 4096)
    dest = tmp_path / "private" / "assets" / "installed-service"
    dest.parent.mkdir(mode=0o700, parents=True)
    dest.write_bytes(b"previous-owner-signed-release")
    with pytest.raises(FileExistsError):
        copy_verified_signed_asset(
            source, dest, expected_sha256=digest, expected_size=size,
        )
    assert dest.read_bytes() == b"previous-owner-signed-release"


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink and inode substitution")
def test_signed_copy_denies_redirected_source_before_creation(tmp_path):
    source, digest, size = _source(tmp_path, 4096)
    redirected = tmp_path / "untrusted-link"
    redirected.symlink_to(source)
    dest = tmp_path / "private" / "assets" / "signed-runtime"
    with pytest.raises(PermissionError, match="redirection"):
        copy_verified_signed_asset(
            redirected, dest, expected_sha256=digest, expected_size=size,
        )
    assert not dest.exists()


def test_signed_copy_rechecks_destination_sha_after_fsync_and_cleans_on_failure(
    tmp_path, monkeypatch,
):
    import sofia.platform.ops.platform_signed_asset_copy as module
    source, digest, size = _source(tmp_path, 8192)
    dest = tmp_path / "private" / "assets" / "runtime"
    original = module.read_artifact_file

    def corrupt_postcopy_result(path, length, *, include_data=False):
        assert Path(path) == dest
        assert length == size
        assert include_data is False
        # Simulates storage-level post-write integrity mismatch, NOT a
        # publisher or permission override.
        return "f" * 64, None

    monkeypatch.setattr(module, "read_artifact_file", corrupt_postcopy_result)
    with pytest.raises(PlatformReleaseRejected, match="destination changed"):
        module.copy_verified_signed_asset(
            source, dest, expected_sha256=digest, expected_size=size,
        )
    assert not dest.exists()
    assert original(source, size)[0] == digest


@pytest.mark.skipif(os.name == "nt", reason="POSIX concurrent source rename test")
def test_signed_copy_refuses_path_swapped_while_copying(tmp_path, monkeypatch):
    import sofia.platform.ops.platform_signed_asset_copy as module
    source, digest, size = _source(tmp_path, 1024 * 1024)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"X" * size)
    target = tmp_path / "private" / "assets" / "runtime"

    real_sha256 = sha256
    displaced = []
    class MutatingDigest:
        def __init__(self):
            self.hash = real_sha256()
        def update(self, block):
            if not displaced:
                displaced.append(True)
                os.replace(replacement, source)
            self.hash.update(block)
        def hexdigest(self):
            return self.hash.hexdigest()

    monkeypatch.setattr(module, "sha256", lambda: MutatingDigest())
    with pytest.raises(PlatformReleaseRejected, match="source changed"):
        module.copy_verified_signed_asset(
            source, target, expected_sha256=digest, expected_size=size,
        )
    assert not target.exists()
    assert source.read_bytes() == b"X" * size
