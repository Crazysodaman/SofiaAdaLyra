from test.owner_auth_fixture import record_verified_restore_receipt, revoke_verified_restore_receipt
from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path
from hashlib import sha256
import json
import sqlite3

import pytest

from sofia.platform.config.defaults import production_storage_layout
from sofia.core.memory.deletion_ledger import MemoryDeletionLedger
from sofia.platform.ops.backup import (
    BackupCipher,
    BackupEngine,
    BackupError,
    rotate_backups,
)
from sofia.platform.ops.restore_authority import (
    ProtectedRestoreLedger,
    ProtectedRestoreReplacementApproval,
    replacement_parameters,
)
from sofia.platform.safe.operator_stop import OperatorStopStore


NOW = datetime(2026, 10, 3, 1, 30, tzinfo=timezone.utc)


def make_state(tmp_path: Path) -> Path:
    state = tmp_path / "live" / "sofia.db"
    state.parent.mkdir()
    # closing() is not cosmetic: an unclosed sqlite connection keeps the
    # Windows file handle alive (only a gc cycle collects it), and that
    # handle denies the engine's os.replace publication of this exact
    # destination file later in the same test.
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            "CREATE TABLE state_plane_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO state_plane_meta VALUES ('schema_revision','1')"
        )
        db.execute(
            """
            CREATE TABLE component_schema (
                component TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.commit()
    layout = production_storage_layout(state_path=state)
    layout.protected_root.mkdir(parents=True)
    layout.identity_path.write_text(
        json.dumps(
            {
                "name": "Sofía Ada Lyra",
                "instance_id": "11111111-1111-4111-8111-111111111111",
            }
        ),
        encoding="utf-8",
    )
    constitution_text = "# Constitution\nTest"
    layout.constitution_path.write_text(
        constitution_text,
        encoding="utf-8",
    )
    layout.constitution_hash_path.write_text(
        sha256(constitution_text.encode("utf-8")).hexdigest(),
        encoding="utf-8",
    )
    layout.personality_path.write_text("{}", encoding="utf-8")
    return state


def make_erasure_journal(tmp_path: Path) -> Path:
    root = tmp_path / "operator-held-erasure"
    root.mkdir(exist_ok=True)
    path = root / "memory-deletion.jsonl"
    MemoryDeletionLedger(path, BackupCipher(b"k" * 32)).initialize()
    return path


def make_restore_authority(tmp_path: Path) -> ProtectedRestoreLedger:
    """Owner-provisioned ledger outside the restored state and snapshots."""
    return ProtectedRestoreLedger.initialize(
        tmp_path / "owner-ledger" / "restore-authority.db"
    )


def mint_replacement(
    ledger: ProtectedRestoreLedger,
    target: Path,
    manifest,
    *,
    approval_id: str = "restore.replacement-1",
    approved_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ProtectedRestoreReplacementApproval:
    parameters = replacement_parameters(target, manifest)
    record_verified_restore_receipt(ledger,
        ProtectedRestoreReplacementApproval(
            approval_id=approval_id,
            target_state_path=parameters["target_state_path"],
            backup_id=parameters["backup_id"],
            manifest_digest=parameters["backup_manifest_digest"],
            approved_by="Sparks",
            approved_at=approved_at or NOW - timedelta(seconds=30),
            expires_at=expires_at or NOW + timedelta(hours=2),
        )
    )
    try:
        return next(
            receipt for receipt in ledger.active_receipts(now=NOW)
            if receipt.approval_id == approval_id
        )
    except StopIteration:  # pragma: no cover - mint failure surfaces here
        raise AssertionError(f"receipt {approval_id} did not become active")


@pytest.fixture
def engine():
    return BackupEngine(BackupCipher(b"k" * 32))


def test_backup_uses_consistent_sqlite_snapshot_and_encrypted_payloads(
    tmp_path,
    engine,
):
    state = make_state(tmp_path)
    destination = tmp_path / "backups"

    backup_dir, evidence = engine.create(
        state_path=state,
        destination_root=destination,
        source_host_id="venus",
        failure_domain="external-disk",
        now=NOW,
    )

    assert backup_dir.is_dir()
    assert evidence.failure_domain == "external-disk"
    manifest = engine.verify(backup_dir)
    assert manifest.digest == evidence.content_digest
    assert any(entry.logical_path == "sofia.db" for entry in manifest.entries)
    encrypted = next((backup_dir / "payload").iterdir()).read_bytes()
    assert b"SQLite format 3" not in encrypted


def test_restore_requires_explicit_overwrite_and_recreates_state(
    tmp_path,
    engine,
    monkeypatch,
):
    state = make_state(tmp_path)
    backup_dir, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "backups",
        source_host_id="venus",
        failure_domain="external-disk",
        now=NOW,
    )
    target = tmp_path / "restore" / "sofia.db"
    target.parent.mkdir()
    # A replaceable destination must be identifiable protected state. The
    # independently enforced operator-stop provenance check refuses to
    # conclude anything about arbitrary unidentifiable bytes.
    with closing(sqlite3.connect(target)) as db, db:
        db.execute("CREATE TABLE existing_state (key TEXT PRIMARY KEY)")
    replacement = make_restore_authority(tmp_path)
    mint_replacement(
        replacement, target, engine.verify(backup_dir),
    )

    with pytest.raises(BackupError, match="replace_existing"):
        engine.restore(
            backup_dir=backup_dir,
            target_state_path=target,
            verifier="test",
            erasure_journal=make_erasure_journal(tmp_path),
        )

    result = engine.restore(
        backup_dir=backup_dir,
        target_state_path=target,
        verifier="test",
        replace_existing=True,
        now=NOW,
        erasure_journal=make_erasure_journal(tmp_path),
        replacement_authority=replacement,
    )
    assert result.succeeded is True
    with sqlite3.connect(target) as db:
        assert db.execute(
            "SELECT value FROM state_plane_meta WHERE key='schema_revision'"
        ).fetchone() == ("1",)
    # The receipt is single-use: a repeat replacement attempt is refused
    # even though the same ledger now holds the consumed record.
    with pytest.raises(
        BackupError, match="receipt was already consumed",
    ):
        engine.restore(
            backup_dir=backup_dir,
            target_state_path=target,
            verifier="test",
            replace_existing=True,
            now=NOW,
            erasure_journal=make_erasure_journal(tmp_path),
            replacement_authority=replacement,
        )


def test_restore_rechecks_replacement_authority_before_publication(
    tmp_path, engine, monkeypatch,
):
    state = make_state(tmp_path)
    backup_dir, _ = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="source", failure_domain="external", now=NOW,
    )
    existing_root = tmp_path / "existing"
    existing_root.mkdir()
    target = make_state(existing_root)
    # Establish the operator-stop provenance before capturing an intact
    # baseline so lock/audit bootstrap cannot count as a replaced byte.
    OperatorStopStore(target).current()
    before = target.read_bytes()
    replacement = make_restore_authority(tmp_path)
    approval = mint_replacement(
        replacement, target, engine.verify(backup_dir),
    )
    original_preflight = ProtectedRestoreLedger.require_replacement

    def revoke_while_staging(instance, *_args, **_kwargs):
        original_preflight(instance, *_args, **_kwargs)
        single = instance.active_receipts(now=NOW)[0]
        revoke_verified_restore_receipt(instance,
            single.approval_id, reason="owner retracted before publish",
            at=NOW,
        )

    monkeypatch.setattr(
        ProtectedRestoreLedger, "require_replacement",
        revoke_while_staging,
    )
    monkeypatch.setattr(
        "sofia.platform.ops.backup.verify_production_component_schemas",
        lambda _path: None,
    )

    with pytest.raises(BackupError, match="revoked or refused before publication"):
        engine.restore(
            backup_dir=backup_dir, target_state_path=target,
            verifier="test", replace_existing=True,
            now=NOW,
            erasure_journal=make_erasure_journal(tmp_path),
            replacement_authority=replacement,
        )
    assert target.read_bytes() == before


def test_verify_rejects_modified_encrypted_payload(tmp_path, engine):
    state = make_state(tmp_path)
    backup_dir, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "backups",
        source_host_id="venus",
        failure_domain="external-disk",
        now=NOW,
    )
    payload = next((backup_dir / "payload").iterdir())
    data = bytearray(payload.read_bytes())
    data[-1] ^= 0x01
    payload.write_bytes(bytes(data))

    with pytest.raises(Exception):
        engine.verify(backup_dir)


def test_rotation_keeps_newest_directories(tmp_path):
    root = tmp_path / "backups"
    root.mkdir()
    for name in ("20260101-a", "20260102-b", "20260103-c"):
        item = root / name
        item.mkdir()
        (item / "manifest.json").write_text("{}", encoding="utf-8")

    removed = rotate_backups(root, keep=2)

    assert [path.name for path in removed] == ["20260101-a"]
    assert sorted(path.name for path in root.iterdir()) == [
        "20260102-b",
        "20260103-c",
    ]


def test_manifest_entry_rejects_path_traversal():
    from sofia.platform.ops.backup import BackupEntry

    with pytest.raises(ValueError, match="safe relative path"):
        BackupEntry(
            logical_path="../escape.txt",
            payload_name="0000.bin",
            sha256="a" * 64,
            size=1,
            nonce_b64="AA==",
        )


def test_manifest_authentication_rejects_metadata_tampering(
    tmp_path,
    engine,
):
    state = make_state(tmp_path)
    backup_dir, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "backups",
        source_host_id="venus",
        failure_domain="external-disk",
        now=NOW,
    )
    manifest_path = backup_dir / "manifest.json"
    payload = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        payload.replace("external-disk", "same-host-disk"),
        encoding="utf-8",
    )

    with pytest.raises(BackupError, match="authentication failed"):
        engine.verify(backup_dir)
