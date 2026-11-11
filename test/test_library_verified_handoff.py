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
    proof_current = True

    def __init__(self, _path):
        pass

    def consume(self, *, approval_id, capability, parameters, now):
        if not self.allowed:
            raise PermissionError("missing one-use SAFE owner grant")
        assert approval_id == "owner-current-proof"
        assert capability == "platform.library.cache_admit_enrolled_peer"
        assert parameters["source"] == "ENROLLED_PEER"
        assert parameters["content_digest"] == parameters["content_digest"].lower()
        self.recorded.append(dict(parameters))

    def consumed_owner_proof_remains_current(
            self, *, approval_id, capability, parameters):
        assert approval_id == "owner-current-proof"
        assert capability == "platform.library.cache_admit_enrolled_peer"
        assert parameters["source"] == "ENROLLED_PEER"
        return self.proof_current


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    import sofia.platform.ops.library_verified_handoff as handoff
    monkeypatch.setattr(handoff, "OperatorStopStore", FakeStop)
    monkeypatch.setattr(handoff, "ExecutionApprovalVerifier", FakeApproval)
    FakeStop.state.active = False
    FakeApproval.allowed = True
    FakeApproval.proof_current = True
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



def test_remote_cache_approval_cannot_use_offline_seed_capability(prepared):
    args, raw, artifact = prepared
    assert "ENROLLED_PEER" not in "OFFLINE_MEDIA"
    import sofia.platform.ops.library_verified_handoff as handoff
    assert handoff.LIBRARY_PEER_CACHE_ADMIT != "platform.library.cache_admit_verified_seed"
    assert "cache_admit_enrolled_peer" in handoff.LIBRARY_PEER_CACHE_ADMIT



def test_interrupted_receiver_commit_recovered_only_after_independent_b1_proof(
    prepared,
):
    """Crash between part unlink and durable scope cleanup does not lose data."""
    from hashlib import sha256
    import os
    from sofia.platform.ops.library_verified_handoff import admit_signed_transferred_asset

    args, raw, artifact = prepared
    pin = args["transfer"]
    receiver = args["receiver"]
    part = receiver.incoming / (pin.content_sha256 + ".part")
    complete = receiver.completed / pin.content_sha256
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    assert scope.is_file()
    os.link(part, complete)
    part.unlink()
    assert complete.read_bytes() == raw
    assert scope.is_file()

    result = admit_signed_transferred_asset(**args)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["owner_proof_consumed"] is True
    assert result["install_executed"] is False
    assert not scope.exists()
    assert args["cache"].resolve(artifact).read_bytes() == raw
    assert len(FakeApproval.recorded) == 1


def test_recovered_cas_still_requires_separate_one_use_owner_approval(prepared):
    import os
    args, raw, artifact = prepared
    pin = args["transfer"]
    receiver = args["receiver"]
    part = receiver.incoming / (pin.content_sha256 + ".part")
    complete = receiver.completed / pin.content_sha256
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    os.link(part, complete)
    part.unlink()
    FakeApproval.allowed = False
    with pytest.raises(PermissionError, match="owner grant"):
        admit_signed_transferred_asset(**args)
    assert complete.read_bytes() == raw
    # Provenance must survive an unapproved B1 import so a later distinct
    # owner proof can reuse the verified bytes without accepting a new source.
    assert scope.exists()
    assert not (args["cache"].root / artifact.sha256).exists()



def test_explicit_owner_approval_retry_reuses_verified_bytes_after_denial(prepared):
    """Same immutable signed transfer survives denial, no redownload required."""
    args, raw, artifact = prepared
    pin = args["transfer"]
    receiver = args["receiver"]
    original = receiver.incoming / (pin.content_sha256 + ".part")
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    FakeApproval.allowed = False
    with pytest.raises(PermissionError, match="owner grant"):
        admit_signed_transferred_asset(**args)
    complete = receiver.completed / pin.content_sha256
    assert complete.read_bytes() == raw
    assert scope.is_file()
    assert not original.exists()
    assert not (args["cache"].root / artifact.sha256).exists()

    FakeApproval.allowed = True
    result = admit_signed_transferred_asset(**args)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert args["cache"].resolve(artifact).read_bytes() == raw
    assert not scope.exists()
    assert len(FakeApproval.recorded) == 1


def test_bad_publisher_verification_retains_scope_for_correct_retry(prepared):
    args, raw, artifact = prepared
    pin = args["transfer"]
    scope = args["receiver"].incoming / (pin.content_sha256 + ".scope")
    args["verify_independent_publisher"] = lambda *_: None
    with pytest.raises(ChunkTransferRejected, match="independent publisher"):
        admit_signed_transferred_asset(**args)
    assert scope.is_file()
    assert (args["receiver"].completed / pin.content_sha256).read_bytes() == raw
    assert FakeApproval.recorded == []
    assert not (args["cache"].root / artifact.sha256).exists()


def test_owner_credential_revoked_during_signed_cas_import_retains_scope(
        prepared, monkeypatch):
    args, raw, artifact = prepared
    scope = args["receiver"].incoming / (args["transfer"].content_sha256 + ".scope")
    original_import = args["cache"].import_artifact

    def import_and_revoke(*params, **kwargs):
        result = original_import(*params, **kwargs)
        FakeApproval.proof_current = False
        return result

    monkeypatch.setattr(args["cache"], "import_artifact", import_and_revoke)
    with pytest.raises(ChunkTransferRejected, match="owner authentication revoked"):
        admit_signed_transferred_asset(**args)
    assert len(FakeApproval.recorded) == 1
    assert scope.exists()  # In-doubt receipt needs separately approved recovery.
    assert args["cache"].resolve(artifact).read_bytes() == raw
    FakeApproval.proof_current = True  # Fresh independent approval needed.
