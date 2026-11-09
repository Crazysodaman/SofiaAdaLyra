"""D028 independent recipient handoff regressions, using disposable SAFE doubles.

This is NOT a signed production publisher test or installed-host acceptance.
Real B1 signing keys, enrolled host proof and SAFE owner authentication are
required by the internal service at the actual integration boundary.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_verified_handoff import admit_signed_transferred_asset
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from test.test_library_tls_chunk_transport import _transfer


class StopState:
    active = False


class FakeStop:
    state = StopState()

    def __init__(self, _path):
        pass

    def current(self):
        return self.state


class FakeApproval:
    recorded = []
    allowed = True

    def __init__(self, _path):
        pass

    def consume(self, *, approval_id, capability, parameters, now):
        if not self.allowed:
            raise PermissionError("missing one-use SAFE owner grant")
        assert approval_id == "owner-current-proof"
        assert capability == "platform.library.cache_admit_verified_seed"
        assert parameters["source"] == "ENROLLED_PEER"
        assert parameters["content_digest"] == parameters["content_digest"].lower()
        self.recorded.append(dict(parameters))


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    import sofia.platform.ops.library_verified_handoff as handoff
    monkeypatch.setattr(handoff, "OperatorStopStore", FakeStop)
    monkeypatch.setattr(handoff, "ExecutionApprovalVerifier", FakeApproval)
    FakeStop.state.active = False
    FakeApproval.allowed = True
    FakeApproval.recorded = []
    raw = b"public-release-bytes-" * 500
    pin = _transfer(raw)
    # This specific handoff only supports existing Platform/SDK B1 cache.
    pin = PinnedChunkTransfer(
        source_platform_id=pin.source_platform_id,
        target_platform_id=pin.target_platform_id,
        content_sha256=pin.content_sha256,
        size_bytes=pin.size_bytes, generation=pin.generation,
        manifest_sha256=pin.manifest_sha256,
        catalog_revision=pin.catalog_revision,
        artifact_kind="sdk", license_distribution="permitted", data_class="public",
    )
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=len(raw) + 128)
    receiver.append_chunk(
        pin, offset=0, chunk=raw, chunk_sha256=sha256(raw).hexdigest(),
        authorize=lambda _: True,
    )
    cache = OfflineArtifactCache(tmp_path / "canonical-cache", max_bytes=1_000_000)
    artifact = PlatformArtifact(
        artifact_id="signed-release", version="1.0",
        platform=PlatformKind.LINUX, architecture="x86_64",
        sha256=pin.content_sha256, signer_key_id="independent-publisher-key",
        signature_verified=True, source="recipient-publisher-verifier",
    )
    args = dict(
        transfer=pin, receiver=receiver, cache=cache,
        canonical_safe_state=tmp_path / "canonical-safe.db",
        approval_id="owner-current-proof",
        verify_independent_publisher=lambda _pin, _path: artifact,
        publisher_current=lambda _: True,
        current_host_admit=lambda _: True,
    )
    return args, raw, artifact


def test_signed_recipient_handoff_stops_at_verified_cache(prepared):
    args, raw, artifact = prepared
    result = admit_signed_transferred_asset(**args)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["owner_proof_consumed"] is True
    assert result["install_executed"] is False
    assert result["core_activated"] is False
    assert result["installed"] is None and result["active"] is None
    assert args["cache"].resolve(artifact).read_bytes() == raw
    assert len(FakeApproval.recorded) == 1
    assert FakeApproval.recorded[0]["target_platform_id"] == args["transfer"].target_platform_id


def test_missing_owner_proof_never_admits_bytes(prepared):
    args, _raw, artifact = prepared
    FakeApproval.allowed = False
    with pytest.raises(PermissionError, match="owner grant"):
        admit_signed_transferred_asset(**args)
    assert not (args["cache"].root / artifact.sha256).exists()
    assert FakeApproval.recorded == []


def test_stop_refuses_before_publisher_or_approval(prepared):
    args, _raw, artifact = prepared
    FakeStop.state.active = True
    calls = []
    args["verify_independent_publisher"] = lambda *_: calls.append(True)
    with pytest.raises(PermissionError, match="STOP"):
        admit_signed_transferred_asset(**args)
    assert calls == []
    assert FakeApproval.recorded == []
    assert not (args["cache"].root / artifact.sha256).exists()


def test_mismatched_publisher_archive_rejected_before_owner_proof(prepared):
    args, _raw, artifact = prepared
    wrong = PlatformArtifact(
        artifact_id=artifact.artifact_id, version=artifact.version,
        platform=artifact.platform, architecture=artifact.architecture,
        sha256="f" * 64, signer_key_id=artifact.signer_key_id,
        signature_verified=True, source=artifact.source,
    )
    args["verify_independent_publisher"] = lambda *_: wrong
    with pytest.raises(ChunkTransferRejected, match="differs"):
        admit_signed_transferred_asset(**args)
    assert FakeApproval.recorded == []
    assert not (args["cache"].root / artifact.sha256).exists()


def test_module_bytes_require_dedicated_module_verifier(prepared):
    args, _raw, artifact = prepared
    raw = args["transfer"]
    args["transfer"] = PinnedChunkTransfer(
        source_platform_id=raw.source_platform_id,
        target_platform_id=raw.target_platform_id,
        content_sha256=raw.content_sha256, size_bytes=raw.size_bytes,
        generation=raw.generation, manifest_sha256=raw.manifest_sha256,
        catalog_revision=raw.catalog_revision, artifact_kind="module",
        license_distribution="permitted", data_class="public",
    )
    with pytest.raises(ChunkTransferRejected, match="dedicated"):
        admit_signed_transferred_asset(**args)
    assert FakeApproval.recorded == []
    assert not (args["cache"].root / artifact.sha256).exists()


def test_revocation_after_signed_review_cannot_import(prepared):
    args, _raw, artifact = prepared
    state = {"revoked": False}
    def verify_and_revoke(_transfer, _path):
        state["revoked"] = True
        return artifact
    args["verify_independent_publisher"] = verify_and_revoke
    args["publisher_current"] = lambda _: not state["revoked"]
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        admit_signed_transferred_asset(**args)
    assert FakeApproval.recorded == []
    assert not (args["cache"].root / artifact.sha256).exists()
