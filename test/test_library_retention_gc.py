"""D028 B1 retention graph and governed one-blob GC security regressions.

Mock owner authorization is confined to isolated tmp_path tests and is NOT
production signer, installed-host evidence, or a valid SAFE approval.
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import os
import sqlite3

import pytest

from sofia.platform.ops.library_retention_gc import (
    GC_CAPABILITY, GovernedLibraryRetention,
)
from sofia.platform.ops.library_retention_graph import (
    LIVE_PIN_REASONS, LibraryRetentionDenied, build_library_pin_graph,
)
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore


class FakeStop:
    active = False

    def __init__(self, _path):
        pass

    def current(self):
        return SimpleNamespace(active=self.active)


class FakeApproval:
    allowed = True
    called = []
    on_consume = None

    def __init__(self, _path):
        pass

    def consume(self, *, approval_id, capability, parameters, now):
        if not self.allowed:
            raise PermissionError("no independently verified owner approval")
        assert approval_id == "owner-one-time"
        assert capability == GC_CAPABILITY
        assert parameters["content_sha256"] == parameters["content_sha256"].lower()
        self.called.append(dict(parameters))
        if type(self).on_consume is not None:
            type(self).on_consume()
        return SimpleNamespace(approved_by="person:sparks")


class FakeAudit:
    fail = False
    calls = []

    def __init__(self, _path):
        pass

    def append(self, *, actor_id, event_type, payload, occurred_at, event_id):
        if self.fail:
            raise RuntimeError("synthetic SQLite audit failure")
        assert actor_id == "person:sparks"
        assert event_type == "library.cache.gc.completed"
        assert payload["deletion_verified"] is True
        self.calls.append((event_id, payload))
        return "e" * 64


@pytest.fixture
def gc_environment(tmp_path, monkeypatch):
    import sofia.platform.ops.library_retention_gc as module
    monkeypatch.setattr(module, "OperatorStopStore", FakeStop)
    monkeypatch.setattr(module, "ExecutionApprovalVerifier", FakeApproval)
    monkeypatch.setattr(module, "AuditChain", FakeAudit)
    FakeStop.active = False
    FakeApproval.allowed = True
    FakeApproval.called = []
    FakeApproval.on_consume = None
    FakeAudit.fail = False
    FakeAudit.calls = []
    raw = b"owner-verified-unpinned-sdk" * 100
    content_digest = sha256(raw).hexdigest()
    cache = OfflineArtifactCache(tmp_path / "cache", max_bytes=65536)
    source = tmp_path / "verified-media"
    source.write_bytes(raw)
    source.chmod(0o600)
    artifact = PlatformArtifact(
        artifact_id="sdk.test", version="1.0", platform=PlatformKind.LINUX,
        architecture="x86_64", sha256=content_digest,
        signer_key_id="independently-reviewed-test-key",
        signature_verified=True, source="disposable-signer-test",
    )
    cache.import_artifact(artifact, source)
    store = PlatformInstallationStore(tmp_path / "b1" / "install.db")
    pins = {reason: tuple() for reason in LIVE_PIN_REASONS}
    host_status = {"allowed": True}
    def current_graph():
        return build_library_pin_graph(
            store=store, platform_id="recipient-platform",
            run_generation=3,
            independently_verified_assets_for_manifest=lambda _: (content_digest,),
            read_current_live_pins=lambda: dict(pins),
        )
    controller = GovernedLibraryRetention(
        cache=cache, store=store, canonical_safe_state=tmp_path / "safe.db",
        platform_id="recipient-platform", run_generation=3,
        independently_verified_assets_for_manifest=lambda _: (content_digest,),
        read_current_live_pins=lambda: dict(pins),
        current_host_admit=lambda _: host_status["allowed"],
        hold_pin_revision=lambda: nullcontext(),
    )
    return controller, cache, store, artifact, pins, host_status, current_graph


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_preview_is_readonly_and_does_not_consume_owner_proof(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    snapshot = controller.preview(content_sha256=artifact.sha256)
    assert snapshot["deletion_eligible"] is True
    assert len(snapshot["pin_graph_sha256"]) == 64
    assert snapshot["deletion_executed"] is False
    assert FakeApproval.called == []
    assert (cache.root / artifact.sha256).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_owner_proof_deletes_exactly_one_unpinned_verified_blob(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    before = controller.preview(content_sha256=artifact.sha256)
    receipt = controller.delete_one(
        content_sha256=artifact.sha256,
        expected_pin_graph_sha256=before["pin_graph_sha256"],
        approval_id="owner-one-time",
    )
    assert receipt["deletion_executed"] is True
    assert receipt["owner_approved"] is True
    assert receipt["cache_state"] == "REMOVED"
    assert receipt["install_executed"] is False
    assert not (cache.root / artifact.sha256).exists()
    assert len(FakeApproval.called) == 1
    assert FakeAudit.calls[0][0] == "library-gc:owner-one-time"


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
@pytest.mark.parametrize("reason", sorted(LIVE_PIN_REASONS))
def test_gc_preserves_every_live_protected_pin(reason, gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    pins[reason] = (artifact.sha256,)
    snapshot = controller.preview(content_sha256=artifact.sha256)
    assert snapshot["deletion_eligible"] is False
    assert reason in snapshot["pin_reasons"]
    with pytest.raises(LibraryRetentionDenied, match="pinned"):
        controller.delete_one(
            content_sha256=artifact.sha256,
            expected_pin_graph_sha256=snapshot["pin_graph_sha256"],
            approval_id="owner-one-time",
        )
    assert FakeApproval.called == []
    assert cache.resolve(artifact).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_preserves_historical_successful_installs_even_after_deactivation(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO ops_platform_installation_history"
            " (receipt_id,release_id,operation,result,revision,manifest_sha256,recorded_at)"
            " VALUES (?,?,?,?,?,?,?)",
            ("test-receipt", "test-release", "install", "SUCCEEDED",
             1, "a" * 64, datetime.now(timezone.utc).isoformat()),
        )
    snapshot = controller.preview(content_sha256=artifact.sha256)
    assert "ROLLBACK_RETAINED" in snapshot["pin_reasons"]
    assert snapshot["deletion_eligible"] is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_denies_pending_install_and_missing_complete_pin_graph(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    store.begin_attempt(
        "test-release", "a" * 64, cache.root / "install-target",
        "install", datetime.now(timezone.utc),
    )
    with pytest.raises(LibraryRetentionDenied, match="unresolved"):
        controller.preview(content_sha256=artifact.sha256)
    assert cache.resolve(artifact).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_rechecks_changed_pin_graph_after_approval(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    before = controller.preview(content_sha256=artifact.sha256)
    FakeApproval.on_consume = lambda: pins.__setitem__(
        "OPERATOR_PIN", (artifact.sha256,),
    )
    with pytest.raises(LibraryRetentionDenied, match="changed"):
        controller.delete_one(
            content_sha256=artifact.sha256,
            expected_pin_graph_sha256=before["pin_graph_sha256"],
            approval_id="owner-one-time",
        )
    assert len(FakeApproval.called) == 1
    assert cache.resolve(artifact).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_missing_approval_or_stop_does_not_delete(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    before = controller.preview(content_sha256=artifact.sha256)
    FakeApproval.allowed = False
    with pytest.raises(PermissionError, match="approval"):
        controller.delete_one(
            content_sha256=artifact.sha256,
            expected_pin_graph_sha256=before["pin_graph_sha256"],
            approval_id="owner-one-time",
        )
    FakeStop.active = True
    with pytest.raises(LibraryRetentionDenied, match="STOP"):
        controller.preview(content_sha256=artifact.sha256)
    assert cache.resolve(artifact).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_stale_graph_denies_before_consuming_owner_proof(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    with pytest.raises(LibraryRetentionDenied, match="graph changed"):
        controller.delete_one(
            content_sha256=artifact.sha256,
            expected_pin_graph_sha256="f" * 64,
            approval_id="owner-one-time",
        )
    assert FakeApproval.called == []
    assert cache.resolve(artifact).is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_audit_failure_is_outcome_unknown_not_false_success(gc_environment):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    before = controller.preview(content_sha256=artifact.sha256)
    FakeAudit.fail = True
    with pytest.raises(RuntimeError, match="OUTCOME_UNKNOWN"):
        controller.delete_one(
            content_sha256=artifact.sha256,
            expected_pin_graph_sha256=before["pin_graph_sha256"],
            approval_id="owner-one-time",
        )
    assert not (cache.root / artifact.sha256).exists()
    assert len(FakeApproval.called) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX immutable CAS inode and private mode")
def test_gc_rejects_hardlinked_cached_object(gc_environment, tmp_path):
    controller, cache, store, artifact, pins, host_status, graph = gc_environment
    # A linked inode could remain accessible outside the B1 cache after GC.
    outside = tmp_path / "outside-hardlink"
    cached = cache.root / artifact.sha256
    os.link(cached, outside)
    inode = cached.stat().st_ino
    with pytest.raises(LibraryRetentionDenied, match="linked"):
        controller.preview(content_sha256=artifact.sha256)
    # GC preserves both links, while canonical cache resolution must itself
    # reject the unsafe object introduced by this disposable attack fixture.
    assert cached.is_file() and outside.is_file()
    assert cached.stat().st_ino == outside.stat().st_ino == inode
    assert cached.stat().st_nlink == 2
    assert sha256(cached.read_bytes()).hexdigest() == artifact.sha256
    with pytest.raises(PermissionError, match="unsafe"):
        cache.resolve(artifact)
