"""Deferred source/destination fencing evidence for Venus -> Artemis.

Simulates the operator-approved staging path with isolated temporary files.
Does NOT touch either live host or execute migration.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import sofia.ops.state_relocation as relocation
from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from sofia.ops.recovery import RestoreVerification
from sofia.ops.state_relocation import (
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
    )


def _stage(proof, tmp_path, monkeypatch, *, manifest_source="Venus", approve=True):
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
        return RestoreVerification(
            backup_id="isolated-archive", verified_at=NOW,
            verifier=kwargs["verifier"], succeeded=True,
        )

    monkeypatch.setattr(engine, "create", fake_create)
    monkeypatch.setattr(engine, "verify", fake_verify)
    monkeypatch.setattr(engine, "restore", fake_restore)
    monkeypatch.setattr(
        relocation, "inspect_state_relocation",
        lambda *_args: SimpleNamespace(
            eligible_for_review=True, blockers=(), warnings=(),
        ),
    )
    output = stage_verified_state_home(
        proof=proof,
        independently_verify_authorization=lambda received:
            approve and received is proof,
        backup_engine=engine,
        encrypted_backup_root=tmp_path / "backups",
        failure_domain="separate-offline-fixture",
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
    assert not proof.destination_root.exists()


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
