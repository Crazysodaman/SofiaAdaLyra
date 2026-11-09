"""D028 canonical B1 CAS streaming tests: no in-memory whole-asset read.

Small tests are fast; the sparse >512MiB test is a deliberate filesystem
integration check, not synthetic network/mTLS or installed-host acceptance.
No production owner approval or signing key is created by these tests.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import tracemalloc

import pytest

from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from sofia.platform.state.artifact_file import ArtifactFileRejected, read_artifact_file


def _artifact(raw_digest: str) -> PlatformArtifact:
    return PlatformArtifact(
        artifact_id="signed-test-sdk", version="1.0",
        platform=PlatformKind.LINUX, architecture="x86_64",
        sha256=raw_digest, signer_key_id="test-only-independent-publisher",
        signature_verified=True, source="reviewed-synthetic-input",
    )


def test_small_streamed_import_preserves_existing_cache_contract(tmp_path):
    data = b"canonical signed B1 content" * 5000
    src = tmp_path / "source"
    src.write_bytes(data)
    expected = sha256(data).hexdigest()
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=len(data) + 4096)
    target = cache.import_artifact(_artifact(expected), src)
    assert target.name == expected
    assert target.read_bytes() == data
    assert cache.import_artifact(_artifact(expected), src) == target
    assert cache.resolve(_artifact(expected)) == target
    assert cache.digest(target) == expected
    assert list(cache.root.glob(".artifact-*")) == []


def test_streaming_import_does_not_call_bounded_eager_artifact_reader(tmp_path, monkeypatch):
    import sofia.platform.ops.platform_install as b1
    data = b"capped chunk import" * 300_000
    source = tmp_path / "source"
    source.write_bytes(data)
    expected = sha256(data).hexdigest()
    def never_read_all(*_args, **_kwargs):
        raise AssertionError("whole-artifact read is forbidden")
    monkeypatch.setattr(b1, "read_artifact_file", never_read_all)
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=16 * 1024**2)
    tracemalloc.start()
    try:
        target = cache.import_artifact(_artifact(expected), source)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert target.stat().st_size == len(data)
    assert peak < 8 * 1024**2


def test_streaming_import_rejects_incorrect_sha_before_publication(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"untrusted package content")
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=65536)
    with pytest.raises(ValueError, match="approved SHA-256"):
        cache.import_artifact(_artifact("b" * 64), source)
    assert not (cache.root / ("b" * 64)).exists()
    assert list(cache.root.glob(".artifact-*")) == []


def test_streaming_import_rejects_quota_and_redirected_source(tmp_path):
    source = tmp_path / "source"
    raw = b"verified test bytes" * 100
    source.write_bytes(raw)
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=len(raw) - 1)
    with pytest.raises(RuntimeError, match="resource limit"):
        cache.import_artifact(_artifact(sha256(raw).hexdigest()), source)
    link = tmp_path / "substituted"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError):
        pytest.skip("filesystem does not support symlinks")
    with pytest.raises(PermissionError):
        cache.import_artifact(_artifact(sha256(raw).hexdigest()), link)


@pytest.mark.skipif(os.name == "nt", reason="POSIX sparse-file deterministic large-stream test")
@pytest.mark.slow
def test_real_sparse_512mib_plus_one_streams_into_canonical_b1(tmp_path):
    """Exercise the real >512MiB CAS limit without allocating a 513MiB buffer."""
    size = 512 * 1024**2 + 1
    source = tmp_path / "sparse-source"
    with source.open("wb") as handle:
        handle.truncate(size)
    # For 512 MiB of zeros followed by one zero, the entire digest is still
    # computed in 64KiB blocks rather than created as a giant bytes object.
    digest = sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=size + 4 * 1024**2)
    tracemalloc.start()
    try:
        published = cache.import_artifact(_artifact(digest.hexdigest()), source)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert published.stat().st_size == size
    assert cache.resolve(_artifact(digest.hexdigest())) == published
    assert peak < 12 * 1024**2
