"""Deferred source/destination fencing evidence for Venus -> Artemis.

Simulates the operator-approved staging path with isolated temporary files.
Does NOT touch either live host or execute migration.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import sofia.platform.ops.state_relocation as relocation
from sofia.platform.ops.backup import BackupCipher, BackupEngine, BackupError
from sofia.platform.ops.recovery import RestoreVerification
from sofia.platform.ops.state_relocation import (
    RelocationAuthorization, StagedStateHome, stage_verified_state_home,
)


NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _plan(tmp_path, *, source="Venus", target="Artemis"):
    existing = tmp_path / "venus" / "sofia.db"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"isolated-original-fixture")
    return RelocationAuthorization(
        source_state_path=existing,
        destination_root=tmp_path / "artemis-staged",
        writer_host_id=target,
        source_writer_host_id=source,
        next_writer_epoch=2,
        operator_approval_ref="operator-approval-fixture",
        writer_fence_ref="independent-fence-fixture",
        protected_operation_id="offline:supervised-venus-artemis-fixture",
        operator_principal_id="owner:supervised-fixture",
        source_writer_epoch=1,
    )


def _stage(
    proof, tmp_path, monkeypatch, *,
    manifest_source="Venus", approve=True,
    fail_restore=False, omit_identity=False,
    revoke_before_publish=False, advance_journal_before_publish=False,
    unapplied_erasure=False,
):
    engine = BackupEngine(BackupCipher(b"k" * 32))
    calls = []

    def fake_create(**kwargs):
        calls.append(("create", kwargs))
        return tmp_path / "backups" / "encrypted-fixture", None

    def fake_verify(_bundle):
        return SimpleNamespace(
            source_host_id=manifest_source,
            entries=(SimpleNamespace(logical_path="sofia.db"),),
            backup_id="isolated-archive",
        )

    def fake_restore(**kwargs):
        calls.append(("restore", kwargs))
        staging = kwargs["target_state_path"].parent
        staging.mkdir(parents=True, exist_ok=True)
        kwargs["target_state_path"].write_bytes(b"isolated-stage-fixture")
        if fail_restore:
            raise BackupError("simulated interrupted protected-file recovery")
        protected = staging / "protected"
        protected.mkdir(exist_ok=True)
        if not omit_identity:
            (protected / "identity.json").write_text(
                '{"name":"Sofia fixture"}', encoding="utf-8",
            )
        return RestoreVerification(
            backup_id="isolated-archive", verified_at=NOW,
            verifier=kwargs["verifier"], succeeded=True,
        )

    monkeypatch.setattr(engine, "create", fake_create)
    monkeypatch.setattr(engine, "verify", fake_verify)
    monkeypatch.setattr(engine, "restore", fake_restore)
    # This fixture deliberately writes synthetic bytes rather than SQLite and
    # does not provision a real external deletion journal. Mock the existing
    # independently tested journal reader only for this staging integration
    # fixture; production must use the real authenticated replay verifier.
    from sofia.core.memory.deletion_ledger import MemoryDeletionLedger, MemoryErasureError

    journal_reads = 0

    def fake_journal_entries(_ledger):
        nonlocal journal_reads
        journal_reads += 1
        if advance_journal_before_publish and journal_reads >= 3:
            return ({"candidate_id": "new-signed-erasure"},)
        return ()

    def fake_verify_applied(_ledger, _state_path):
        if unapplied_erasure:
            raise MemoryErasureError("synthetic unapplied signed deletion")
        return {"signed_deletions": 0, "verified_absent": 0}

    monkeypatch.setattr(MemoryDeletionLedger, "entries", fake_journal_entries)
    monkeypatch.setattr(MemoryDeletionLedger, "verify_applied", fake_verify_applied)
    monkeypatch.setattr(
        relocation, "inspect_state_relocation",
        lambda *_args: SimpleNamespace(
            eligible_for_review=True, blockers=(), warnings=(),
        ),
    )
    monkeypatch.setattr(
        "sofia.platform.ops.state_mobility._filesystem_kind",
        lambda _path: "local",
    )
    authorization_checks = 0

    def verify_fence(received):
        nonlocal authorization_checks
        authorization_checks += 1
        return (
            approve
            and received is proof
            and (not revoke_before_publish or authorization_checks == 1)
        )

    (tmp_path / "operator-held").mkdir(exist_ok=True)
    output = stage_verified_state_home(
        proof=proof,
        independently_verify_authorization=verify_fence,
        backup_engine=engine,
        encrypted_backup_root=tmp_path / "backups",
        failure_domain="separate-offline-fixture",
        erasure_journal_path=tmp_path / "operator-held" / "erasures.jsonl",
    )
    return output, calls


def test_operator_staging_attributes_backup_to_venus_not_artemis(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    staged, calls = _stage(proof, tmp_path, monkeypatch)
    assert isinstance(staged, StagedStateHome)
    assert staged.writer_host_id == "Artemis"
    assert staged.proposed_writer_epoch == 2
    assert staged.activated is False
    assert calls[0][0] == "create"
    assert calls[0][1]["source_host_id"] == "Venus"
    assert calls[1][0] == "restore"
    assert calls[1][1]["target_state_path"] != proof.destination_root / "sofia.db"
    assert calls[1][1]["target_state_path"].parent.name.startswith(
        "." + proof.destination_root.name + ".restore-"
    )
    assert (proof.destination_root / "sofia.db").is_file()
    assert (proof.destination_root / "protected" / "identity.json").is_file()
    assert not calls[1][1]["target_state_path"].parent.exists()


def test_wrong_authenticated_backup_origin_never_reaches_restore(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    with pytest.raises(BackupError, match="source host"):
        _stage(proof, tmp_path, monkeypatch, manifest_source="Artemis")
    assert not proof.destination_root.exists()


def test_missing_source_writer_identity_rejected_before_backup(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path, source="")
    with pytest.raises(ValueError, match="fencing provenance"):
        _stage(proof, tmp_path, monkeypatch)


def test_rejected_writer_fence_never_creates_backup(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    with pytest.raises(PermissionError, match="fencing"):
        _stage(proof, tmp_path, monkeypatch, approve=False)
    assert not proof.destination_root.exists()


def test_failed_restore_does_not_publish_partial_state_home(tmp_path, monkeypatch):
    proof = _plan(tmp_path)
    with pytest.raises(BackupError, match="interrupted protected-file"):
        _stage(proof, tmp_path, monkeypatch, fail_restore=True)
    assert not proof.destination_root.exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))
    assert proof.source_state_path.read_bytes() == b"isolated-original-fixture"


def test_missing_protected_identity_never_publishes_staging(tmp_path, monkeypatch):
    proof = _plan(tmp_path)
    with pytest.raises(BackupError, match="protected identity"):
        _stage(proof, tmp_path, monkeypatch, omit_identity=True)
    assert not proof.destination_root.exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))


def test_existing_even_empty_destination_is_not_replaced(tmp_path, monkeypatch):
    proof = _plan(tmp_path)
    proof.destination_root.mkdir()
    sentinel = proof.destination_root / "owner-marker"
    sentinel.write_bytes(b"keep-existing-directory")
    with pytest.raises(FileExistsError, match="fresh absent destination"):
        _stage(proof, tmp_path, monkeypatch)
    assert sentinel.read_bytes() == b"keep-existing-directory"
    assert not (proof.destination_root / "sofia.db").exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))


def test_relocation_rechecks_live_fence_after_restore_before_publication(
    tmp_path, monkeypatch,
):
    """Stale early approval must not publish after the broker revokes it."""
    proof = _plan(tmp_path)
    with pytest.raises(PermissionError, match="withdrawn before publishing"):
        _stage(proof, tmp_path, monkeypatch, revoke_before_publish=True)

    assert not proof.destination_root.exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))
    assert proof.source_state_path.read_bytes() == b"isolated-original-fixture"


def test_relocation_refuses_erasures_missing_from_staged_candidate(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    with pytest.raises(BackupError, match="current authenticated erasures"):
        _stage(proof, tmp_path, monkeypatch, unapplied_erasure=True)

    assert not proof.destination_root.exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))


def test_relocation_refuses_journal_advance_after_restored_candidate_verified(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    with pytest.raises(BackupError, match="advanced before candidate publication"):
        _stage(
            proof, tmp_path, monkeypatch,
            advance_journal_before_publish=True,
        )

    assert not proof.destination_root.exists()
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))
    assert proof.source_state_path.read_bytes() == b"isolated-original-fixture"


def test_source_link_is_rejected_before_backup_collection(tmp_path, monkeypatch):
    """A verified restore must not quietly omit redirected protected files."""
    proof = _plan(tmp_path)
    external = tmp_path / "foreign-protected"
    external.mkdir()
    (external / "identity.json").write_text('{"foreign": true}')
    try:
        (proof.source_state_path.parent / "protected").symlink_to(
            external, target_is_directory=True,
        )
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not allow source-directory symlinks")
    with pytest.raises(BackupError, match="linked or junction"):
        _stage(proof, tmp_path, monkeypatch)
    assert not proof.destination_root.exists()
    assert (external / "identity.json").is_file()


def test_source_special_entry_is_rejected_before_backup_collection(tmp_path, monkeypatch):
    """A FIFO/device/socket under a known home is not an omitted backup asset."""
    import os
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX named pipes unavailable")
    proof = _plan(tmp_path)
    protected = proof.source_state_path.parent / "protected"
    protected.mkdir()
    fifo = protected / "original-events.fifo"
    try:
        os.mkfifo(fifo)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not allow named pipes")
    with pytest.raises(BackupError, match="special filesystem entries"):
        _stage(proof, tmp_path, monkeypatch)
    assert not proof.destination_root.exists()
    assert fifo.exists()


def test_source_inventory_drift_blocks_staging_after_backup(tmp_path, monkeypatch):
    """A file appearing after backup must not become an unarchived old source."""
    proof = _plan(tmp_path)
    from sofia.platform.ops.state_relocation import _inventory_persistent_state_files
    original_inventory = _inventory_persistent_state_files
    calls = []

    def changing_inventory(root):
        result = original_inventory(root)
        calls.append(result)
        if len(calls) == 2:
            (root / "new-identity-log.json").write_text('{"new": true}')
            result = original_inventory(root)
        return result

    monkeypatch.setattr(
        relocation, "_inventory_persistent_state_files", changing_inventory,
    )
    with pytest.raises(BackupError, match="file inventory changed"):
        _stage(proof, tmp_path, monkeypatch)
    assert len(calls) == 2
    assert not proof.destination_root.exists()
    assert (proof.source_state_path.parent / "new-identity-log.json").is_file()


def test_same_epoch_source_and_destination_rejected_before_backup(
    tmp_path, monkeypatch,
):
    from dataclasses import replace

    proof = replace(_plan(tmp_path), source_writer_epoch=2)
    with pytest.raises(ValueError, match="exceed independently witnessed old epoch"):
        _stage(proof, tmp_path, monkeypatch)
    assert not proof.destination_root.exists()


@pytest.mark.parametrize("invalid", (
    {"protected_operation_id": ""},
    {"operator_principal_id": " "},
    {"source_writer_epoch": 0},
))
def test_invalid_exact_approval_or_old_epoch_prevents_staging(
    tmp_path, monkeypatch, invalid,
):
    from dataclasses import replace

    proof = replace(_plan(tmp_path), **invalid)
    with pytest.raises(ValueError):
        _stage(proof, tmp_path, monkeypatch)
    assert not proof.destination_root.exists()
