"""Protected replacement receipts require independent owner proof, not a name."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops.backup import BackupCipher, BackupEngine
from sofia.platform.ops.backup_cli import main
from sofia.platform.ops.restore_authority import ProtectedRestoreLedger, ProtectedRestoreReplacementApproval
from test.test_ops_backup_restore import make_state


def test_name_only_restore_receipt_cannot_be_recorded(tmp_path):
    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    now = datetime.now(timezone.utc)
    receipt = ProtectedRestoreReplacementApproval(
        "restore:unverified", str(tmp_path / "target" / "sofia.db"), "backup-test", "a" * 64,
        "Sparks", now, now + timedelta(minutes=5),
    )
    with pytest.raises(PermissionError, match="owner"):
        ledger.record(receipt)
    assert ledger.active_receipts(now=now) == ()


def test_restore_approval_cli_cannot_mint_owner_authority_without_proof(tmp_path):
    state = make_state(tmp_path)
    key = tmp_path / "backup.key"
    key.write_bytes(b"k" * 32)
    now = datetime.now(timezone.utc)
    archive, _ = BackupEngine(BackupCipher(b"k" * 32)).create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="test-source", failure_domain="test-external", now=now,
    )
    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    assert main([
        "restore-approve", "--key", str(key), "--ledger", str(ledger.path),
        "--backup-dir", str(archive), "--target-state", str(tmp_path / "target" / "sofia.db"),
    ]) == 2
    assert ledger.active_receipts(now=datetime.now(timezone.utc)) == ()


class Manifest:
    backup_id = "backup-test"
    digest = "a" * 64


def software_proof(ledger, capability, parameters, monkeypatch):
    from uuid import uuid4
    from sofia.platform.safe import owner_secret
    from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint

    monkeypatch.setattr(owner_secret, "require_venus_interactive_windows",
                        lambda **kwargs: "S-1-5-21-SYNTHETIC-OWNER")
    secret = "ab" * 32
    store = owner_secret.OwnerSecretStore(ledger.path)
    if not store.enabled():
        store.enroll(secret)
    fingerprint = execution_fingerprint(capability, parameters)
    event = store.authenticate(secret, action_fingerprint=fingerprint)
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(str(uuid4()), capability, fingerprint, "person:sparks",
                                 now, now + timedelta(minutes=2))
    ExecutionApprovalVerifier(ledger.path).record(approval, authentication_event_id=event)
    return approval, store, secret


def prepared_receipt(tmp_path, monkeypatch, *, filename="restore.db"):
    from sofia.platform.ops.restore_authority import RESTORE_REPLACEMENT_CAPABILITY, replacement_parameters

    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / filename)
    target = tmp_path / "target" / "sofia.db"
    parameters = replacement_parameters(target, Manifest())
    proof, store, secret = software_proof(ledger, RESTORE_REPLACEMENT_CAPABILITY, parameters, monkeypatch)
    receipt = ProtectedRestoreReplacementApproval(
        "restore:verified", str(target), Manifest.backup_id, Manifest.digest, "Sparks",
        proof.approved_at, proof.expires_at + timedelta(hours=1),
    )
    ledger.record(receipt, owner_approval_id=proof.approval_id, now=proof.approved_at)
    return ledger, target, proof, store, secret, parameters


def test_64_hex_secret_without_fido_clamps_window_and_consumes_atomically(tmp_path, monkeypatch):
    import sqlite3
    from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier

    ledger, target, proof, _, _, parameters = prepared_receipt(tmp_path, monkeypatch)
    receipts = ledger.active_receipts(now=proof.approved_at)
    assert len(receipts) == 1
    assert receipts[0].approved_by == "person:sparks"
    assert receipts[0].expires_at == proof.expires_at
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT COUNT(*) FROM safe_owner_credential").fetchone()[0] == 0
    verifier = ExecutionApprovalVerifier(ledger.path)
    assert ledger.require_replacement(target, Manifest(), now=proof.approved_at) == receipts[0].approval_id
    assert verifier.matches_unconsumed(approval_id=proof.approval_id, capability=proof.capability,
                                      parameters=parameters, now=proof.approved_at)
    ledger.consume_replacement(target, Manifest(), now=proof.approved_at)
    assert not verifier.matches_unconsumed(approval_id=proof.approval_id, capability=proof.capability,
                                          parameters=parameters, now=proof.approved_at)
    with pytest.raises(PermissionError, match="consumed"):
        ledger.consume_replacement(target, Manifest(), now=proof.approved_at)


def test_owner_secret_rotation_between_preflight_and_publication_denies(tmp_path, monkeypatch):
    import sqlite3

    ledger, target, proof, store, secret, _ = prepared_receipt(tmp_path, monkeypatch)
    ledger.require_replacement(target, Manifest(), now=proof.approved_at)
    store.rotate(secret, "cd" * 32)
    assert ledger.active_receipts(now=proof.approved_at) == ()
    with pytest.raises(PermissionError, match="owner approval"):
        ledger.consume_replacement(target, Manifest(), now=proof.approved_at)
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT consumed_at FROM ops_restore_replacement_approval").fetchone()[0] is None
    assert not target.exists()


def test_receipt_audit_failure_rolls_back_owner_proof_and_receipt(tmp_path, monkeypatch):
    import sqlite3
    from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier

    ledger, target, proof, _, _, parameters = prepared_receipt(tmp_path, monkeypatch)
    append = ledger.audit.append_in_transaction

    def fail_receipt(*args, **kwargs):
        if kwargs.get("event_type") == ledger.AUDIT_CONSUMED:
            raise OSError("synthetic receipt audit failure")
        return append(*args, **kwargs)

    monkeypatch.setattr(ledger.audit, "append_in_transaction", fail_receipt)
    with pytest.raises(OSError, match="audit failure"):
        ledger.consume_replacement(target, Manifest(), now=proof.approved_at)
    assert ExecutionApprovalVerifier(ledger.path).matches_unconsumed(
        approval_id=proof.approval_id, capability=proof.capability,
        parameters=parameters, now=proof.approved_at,
    )
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT consumed_at FROM ops_restore_replacement_approval").fetchone()[0] is None
        assert db.execute("SELECT COUNT(*) FROM safe_audit_event WHERE event_type='execution.approval.consumed'").fetchone()[0] == 0
    monkeypatch.setattr(ledger.audit, "append_in_transaction", append)
    ledger.consume_replacement(target, Manifest(), now=proof.approved_at)


@pytest.mark.parametrize("mode", ["target", "manifest", "ledger", "reused"])
def test_exact_owner_proof_cannot_be_rebound(tmp_path, monkeypatch, mode):
    from dataclasses import replace

    ledger, target, proof, _, _, _ = prepared_receipt(tmp_path, monkeypatch)
    receipt = ProtectedRestoreReplacementApproval(
        "restore:other", str(target), Manifest.backup_id, Manifest.digest, "person:sparks",
        proof.approved_at, proof.expires_at,
    )
    if mode == "target":
        receipt = replace(receipt, target_state_path=str(tmp_path / "foreign" / "sofia.db"))
    elif mode == "manifest":
        receipt = replace(receipt, manifest_digest="b" * 64)
    elif mode == "ledger":
        ledger = ProtectedRestoreLedger.initialize(tmp_path / "other-owner" / "restore.db")
    with pytest.raises(PermissionError, match="owner approval"):
        ledger.record(receipt, owner_approval_id=proof.approval_id, now=proof.approved_at)


def test_revocation_requires_fresh_exact_proof_and_ignores_actor_label(tmp_path, monkeypatch):
    from sofia.platform.ops.restore_authority import RESTORE_REVOCATION_CAPABILITY, restore_revocation_parameters

    ledger, target, proof, _, _, _ = prepared_receipt(tmp_path, monkeypatch)
    with pytest.raises(PermissionError, match="owner revocation"):
        ledger.revoke("restore:verified", reason="withdraw", at=proof.approved_at, revoked_by="Sparks")
    parameters = restore_revocation_parameters("restore:verified", "withdraw")
    revoke, _, _ = software_proof(ledger, RESTORE_REVOCATION_CAPABILITY, parameters, monkeypatch)
    ledger.revoke("restore:verified", reason="withdraw", at=revoke.approved_at,
                  revoked_by="spoofed metadata", owner_approval_id=revoke.approval_id)
    with pytest.raises(PermissionError, match="revoked"):
        ledger.consume_replacement(target, Manifest(), now=revoke.approved_at)


def test_uri_sensitive_ledger_filename_preserves_exact_identity(tmp_path, monkeypatch):
    ledger, target, proof, _, _, _ = prepared_receipt(tmp_path, monkeypatch, filename="Sofía #100%.db")
    reopened = ProtectedRestoreLedger(ledger.path)
    reopened.consume_replacement(target, Manifest(), now=proof.approved_at)


def test_legacy_name_only_rows_are_preserved_but_never_promoted(tmp_path, monkeypatch):
    import sqlite3
    from sofia.platform.ops.restore_authority import RESTORE_AUTHORITY_SCHEMA, RESTORE_REPLACEMENT_CAPABILITY, replacement_parameters
    from sofia.platform.safe.execution_approval import execution_fingerprint

    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    target = tmp_path / "target" / "sofia.db"
    now = datetime.now(timezone.utc)
    parameters = replacement_parameters(target, Manifest())
    with sqlite3.connect(ledger.path) as db:
        db.execute("DROP TABLE ops_restore_owner_binding")
        db.execute("UPDATE ops_restore_authority_meta SET value='sofia.platform.ops.restore-authority-v1' WHERE key='schema'")
        db.execute("INSERT INTO ops_restore_replacement_approval VALUES(?,?,?,?,?,?,?,?,NULL,NULL,NULL)", (
            "restore:legacy", str(target), Manifest.backup_id, Manifest.digest,
            execution_fingerprint(RESTORE_REPLACEMENT_CAPABILITY, parameters), "Sparks",
            now.isoformat(), (now + timedelta(hours=1)).isoformat(),
        ))
    migrated = ProtectedRestoreLedger(ledger.path)
    assert migrated.active_receipts(now=now) == ()
    with pytest.raises(PermissionError, match="owner proof"):
        migrated.require_replacement(target, Manifest(), now=now)
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT value FROM ops_restore_authority_meta WHERE key='schema'").fetchone()[0] == RESTORE_AUTHORITY_SCHEMA
        legacy = db.execute("SELECT approved_by,revoked_at,revocation_reason FROM ops_restore_replacement_approval WHERE approval_id='restore:legacy'").fetchone()
        assert legacy[0] == "Sparks"
        assert legacy[1] is not None
        assert "fresh authenticated owner" in legacy[2]
    proof, _, _ = software_proof(migrated, RESTORE_REPLACEMENT_CAPABILITY, parameters, monkeypatch)
    fresh = ProtectedRestoreReplacementApproval("restore:fresh", str(target), Manifest.backup_id, Manifest.digest,
                                                "person:sparks", proof.approved_at, proof.expires_at)
    migrated.record(fresh, owner_approval_id=proof.approval_id, now=proof.approved_at)
    migrated.consume_replacement(target, Manifest(), now=proof.approved_at)


@pytest.mark.parametrize("corruption", ["unknown_schema", "missing_binding_table"])
def test_corrupt_or_future_authority_is_refused_without_repair(tmp_path, corruption):
    import sqlite3
    from sofia.platform.ops.restore_authority import RestoreAuthorityUnavailable

    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    with sqlite3.connect(ledger.path) as db:
        if corruption == "unknown_schema":
            db.execute("UPDATE ops_restore_authority_meta SET value='future-v999' WHERE key='schema'")
        else:
            db.execute("DROP TABLE ops_restore_owner_binding")
    before = ledger.path.read_bytes()
    with pytest.raises(RestoreAuthorityUnavailable):
        ProtectedRestoreLedger(ledger.path)
    assert ledger.path.read_bytes() == before


def test_cli_uses_software_owner_proof_and_reports_effective_expiry(tmp_path, monkeypatch, capsys):
    from sofia.platform.ops.restore_authority import RESTORE_REPLACEMENT_CAPABILITY, replacement_parameters

    state = make_state(tmp_path)
    key = tmp_path / "backup.key"
    key.write_bytes(b"k" * 32)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(state_path=state, destination_root=tmp_path / "backups",
                               source_host_id="test-source", failure_domain="test-external",
                               now=datetime.now(timezone.utc))
    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    target = tmp_path / "target" / "sofia.db"
    manifest = engine.verify(archive)
    proof, _, secret = software_proof(ledger, RESTORE_REPLACEMENT_CAPABILITY,
                                       replacement_parameters(target, manifest), monkeypatch)
    assert main(["restore-approve", "--key", str(key), "--ledger", str(ledger.path),
                 "--backup-dir", str(archive), "--target-state", str(target),
                 "--owner-approval-id", proof.approval_id]) == 0
    output = capsys.readouterr().out
    assert f"expires_at={proof.expires_at.isoformat()}" in output
    assert secret not in output
    assert len(ledger.active_receipts(now=datetime.now(timezone.utc))) == 1
    assert not target.exists()


def test_late_secret_rotation_blocks_real_restore_before_publication(tmp_path, monkeypatch):
    from sofia.platform.ops.backup import BackupError
    from sofia.platform.ops.restore_authority import RESTORE_REPLACEMENT_CAPABILITY, replacement_parameters
    from test.test_ops_backup_restore import make_erasure_journal

    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(state_path=state, destination_root=tmp_path / "backups",
                               source_host_id="test-source", failure_domain="test-external",
                               now=datetime.now(timezone.utc))
    manifest = engine.verify(archive)
    target = tmp_path / "target" / "sofia.db"
    ledger = ProtectedRestoreLedger.initialize(tmp_path / "owner" / "restore.db")
    proof, store, secret = software_proof(ledger, RESTORE_REPLACEMENT_CAPABILITY,
                                          replacement_parameters(target, manifest), monkeypatch)
    receipt = ProtectedRestoreReplacementApproval("restore:late", str(target), manifest.backup_id,
                                                  manifest.digest, "Sparks", proof.approved_at, proof.expires_at)
    ledger.record(receipt, owner_approval_id=proof.approval_id, now=proof.approved_at)
    consume = ledger.consume_replacement

    def rotate_before_publish(*args, **kwargs):
        store.rotate(secret, "cd" * 32)
        return consume(*args, **kwargs)

    monkeypatch.setattr(ledger, "consume_replacement", rotate_before_publish)
    monkeypatch.setattr("sofia.platform.ops.backup.verify_production_component_schemas", lambda path: None)
    with pytest.raises(BackupError, match="owner approval"):
        engine.restore(backup_dir=archive, target_state_path=target, verifier="test",
                       replace_existing=True, now=datetime.now(timezone.utc),
                       erasure_journal=make_erasure_journal(tmp_path), replacement_authority=ledger)
    assert not target.exists()
    assert not list(target.parent.glob(".*restore*"))
