from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import json
import sqlite3

import pytest

from sofia.config.defaults import production_storage_layout
from sofia.ops.backup import (
    BackupCipher,
    BackupEngine,
    BackupError,
    rotate_backups,
)


NOW = datetime(2026, 10, 3, 1, 30, tzinfo=timezone.utc)


def make_state(tmp_path: Path) -> Path:
    state = tmp_path / "live" / "sofia.db"
    state.parent.mkdir()
    with sqlite3.connect(state) as db:
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
    target.write_bytes(b"existing")

    monkeypatch.setattr(
        "sofia.ops.backup.verify_production_component_schemas",
        lambda _path: None,
    )

    with pytest.raises(BackupError, match="replace_existing"):
        engine.restore(
            backup_dir=backup_dir,
            target_state_path=target,
            verifier="test",
        )

    result = engine.restore(
        backup_dir=backup_dir,
        target_state_path=target,
        verifier="test",
        replace_existing=True,
        now=NOW,
    )
    assert result.succeeded is True
    with sqlite3.connect(target) as db:
        assert db.execute(
            "SELECT value FROM state_plane_meta WHERE key='schema_revision'"
        ).fetchone() == ("1",)


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
    from sofia.ops.backup import BackupEntry

    with pytest.raises(ValueError, match="safe relative path"):
        BackupEntry(
            logical_path="../escape.txt",
            payload_name="0000.bin",
            sha256="a" * 64,
            size=1,
            nonce_b64="AA==",
        )
