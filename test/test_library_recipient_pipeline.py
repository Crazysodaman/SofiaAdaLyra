"""D028 state-separation integration contract, isolated from real host effects."""
from __future__ import annotations

from hashlib import sha256

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_recipient_pipeline import acquire_selected_signed_platform_asset
from sofia.platform.ops.platform_install import OfflineArtifactCache
from test.test_library_tls_chunk_transport import _transfer


@pytest.fixture
def environment(tmp_path, monkeypatch):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    data = b"signed-public-sdk" * 1200
    original = _transfer(data)
    transfer = PinnedChunkTransfer(
        source_platform_id=original.source_platform_id,
        target_platform_id=original.target_platform_id,
        content_sha256=original.content_sha256,
        size_bytes=len(data), generation=original.generation,
        manifest_sha256=original.manifest_sha256,
        catalog_revision=original.catalog_revision, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=100000)
    cache = OfflineArtifactCache(tmp_path / "B1-cache", max_bytes=100000)
    calls = []
    def simulated_fetch(**kwargs):
        calls.append(("fetch", kwargs["start_offset"]))
        return kwargs["start_offset"] + min(kwargs["chunk_bytes"] * kwargs["max_chunks"], len(data) - kwargs["start_offset"])
    def simulated_admit(**kwargs):
        calls.append(("admit", kwargs["transfer"].content_sha256))
        return dict(cache_state="CACHED_VERIFIED", owner_proof_consumed=True,
                    install_executed=False, installed=None, active=None)
    monkeypatch.setattr(pipeline, "fetch_resumable_chunks", simulated_fetch)
    monkeypatch.setattr(pipeline, "admit_signed_transferred_asset", simulated_admit)
    args = dict(
        transfer=transfer, receiver=receiver, cache=cache,
        open_enrolled_tls=lambda: None,
        expected_peer_certificate_sha256="1" * 64,
        authorize_peer=lambda *_: True,
        publisher_current=lambda _: True,
        current_host_admit=lambda _: True,
        verify_independent_publisher=lambda *_: None,
        canonical_safe_state=tmp_path / "canonical-safe.db",
        approval_id="current-owner-proof",
        start_offset=0, chunk_bytes=2048, max_chunks=1,
    )
    return args, calls, data


def test_partial_recipient_fetch_does_not_claim_install_or_signature(environment):
    args, calls, data = environment
    result = acquire_selected_signed_platform_asset(**args)
    assert result["received_bytes"] == 2048
    assert result["verified_bytes"] == 0
    assert result["cache_state"] == "CACHED_UNVERIFIED"
    assert result["owner_proof_consumed"] is False
    assert result["installed"] is None and result["active"] is None
    assert calls == [("fetch", 0)]


def test_full_recipient_fetch_invokes_exact_signed_handoff(environment):
    args, calls, data = environment
    args["max_chunks"] = 100
    result = acquire_selected_signed_platform_asset(**args)
    assert result["received_bytes"] == len(data)
    assert result["verified_bytes"] == len(data)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["owner_proof_consumed"] is True
    assert result["install_executed"] is False
    assert calls == [("fetch", 0), ("admit", args["transfer"].content_sha256)]


def test_current_recipient_denial_prevents_network_and_cache(environment):
    args, calls, _ = environment
    args["current_host_admit"] = lambda _: False
    with pytest.raises(PermissionError, match="SAFE"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []


def test_publisher_revocation_denies_before_network_and_cache(environment):
    args, calls, _ = environment
    args["publisher_current"] = lambda _: False
    with pytest.raises(ChunkTransferRejected, match="publisher"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []


def test_wrong_artifact_kind_uses_dedicated_pipeline(environment):
    args, calls, _ = environment
    prior = args["transfer"]
    args["transfer"] = PinnedChunkTransfer(
        source_platform_id=prior.source_platform_id,
        target_platform_id=prior.target_platform_id,
        content_sha256=prior.content_sha256, size_bytes=prior.size_bytes,
        generation=prior.generation, manifest_sha256=prior.manifest_sha256,
        catalog_revision=prior.catalog_revision, artifact_kind="module",
        license_distribution="permitted", data_class="public",
    )
    with pytest.raises(ChunkTransferRejected, match="separate module"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []
