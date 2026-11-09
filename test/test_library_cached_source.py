"""D028 Host resource efficiency: one initial full B1 digest, not per chunk.

Disposable typed artifacts are not signed production releases. The actual
HostedLibraryHub checks current publisher trust, SAFE/STOP and mTLS each chunk.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os

import pytest

from sofia.platform.ops.library_cached_source import VerifiedLibraryCacheSource
from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)


def _prepare(tmp_path):
    payload = b"owner-approved-public-image" * 48_000
    source_file = tmp_path / "signed-source"
    source_file.write_bytes(payload)
    digest = sha256(payload).hexdigest()
    artifact = PlatformArtifact(
        artifact_id="sdk.public.v1", version="1.0",
        platform=PlatformKind.LINUX, architecture="x86_64",
        sha256=digest, signer_key_id="test-only",
        signature_verified=True, source="synthetic",
    )
    cache = OfflineArtifactCache(tmp_path / "B1", max_bytes=4 * 1024**2)
    path = cache.import_artifact(artifact, source_file)
    transfer = PinnedChunkTransfer(
        source_platform_id="source-installed",
        target_platform_id="target-installed",
        content_sha256=digest, size_bytes=len(payload),
        generation=27, manifest_sha256="a" * 64,
        catalog_revision=8, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    return payload, cache, artifact, path, transfer


def test_one_initial_signed_b1_digest_not_one_full_hash_per_chunk(tmp_path, monkeypatch):
    payload, cache, artifact, path, transfer = _prepare(tmp_path)
    real = cache.resolve
    observed = []
    def checked(obj):
        observed.append(True)
        return real(obj)
    monkeypatch.setattr(cache, "resolve", checked)
    snapshot = VerifiedLibraryCacheSource(cache=cache, artifact=artifact)
    for _ in range(2048):
        assert snapshot.current_path(transfer) == path
    assert len(observed) == 1
    assert snapshot.path.stat().st_size == len(payload)


@pytest.mark.skipif(os.name == "nt", reason="POSIX cached inode metadata test")
def test_post_selection_same_size_tampering_refused_before_chunk(tmp_path):
    payload, cache, artifact, path, transfer = _prepare(tmp_path)
    snapshot = VerifiedLibraryCacheSource(cache=cache, artifact=artifact)
    path.write_bytes(b"0" * len(payload))
    with pytest.raises(ChunkTransferRejected, match="changed"):
        snapshot.current_path(transfer)


@pytest.mark.skipif(os.name == "nt", reason="POSIX linked cache policy")
def test_hardlinked_cache_snapshot_cannot_be_reused(tmp_path):
    payload, cache, artifact, path, transfer = _prepare(tmp_path)
    snapshot = VerifiedLibraryCacheSource(cache=cache, artifact=artifact)
    extra = tmp_path / "unexpected-foreign-link"
    os.link(path, extra)
    with pytest.raises(ChunkTransferRejected, match="inode|changed"):
        snapshot.current_path(transfer)


def test_source_guards_wrong_content_and_size_or_unsigned_package(tmp_path):
    payload, cache, artifact, path, transfer = _prepare(tmp_path)
    snapshot = VerifiedLibraryCacheSource(cache=cache, artifact=artifact)
    with pytest.raises(ChunkTransferRejected, match="differs"):
        snapshot.current_path(replace(transfer, size_bytes=len(payload) + 1))
    with pytest.raises(ChunkTransferRejected, match="differs"):
        snapshot.current_path(replace(transfer, content_sha256="f" * 64))
    with pytest.raises(ChunkTransferRejected, match="unsigned"):
        VerifiedLibraryCacheSource(
            cache=cache, artifact=replace(artifact, signature_verified=False),
        )
