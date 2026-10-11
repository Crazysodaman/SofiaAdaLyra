"""Option B acceptance: erase live candidate; replay across an older backup.

These cases are written for the user's deferred test campaign. Do not
execute them during production-code authoring.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
import sqlite3

import pytest

from sofia.memory.deletion_ledger import MemoryDeletionLedger, MemoryErasureError
from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from test.test_ops_backup_restore import make_state


NOW = datetime(2026, 10, 11, 15, 0, tzinfo=timezone.utc)
CANDIDATE = UUID("aaaaaaaa-1111-4111-8111-111111111111")


def _prepare(tmp_path):
    state = make_state(tmp_path)
    with sqlite3.connect(state) as db:
        db.executescript("""
            CREATE TABLE memory_candidate (
                candidate_id TEXT PRIMARY KEY,content TEXT NOT NULL,
                created_at TEXT NOT NULL,status TEXT NOT NULL,
                principal_id TEXT,audience_id TEXT
            );
            CREATE TABLE memory_candidate_source (
                candidate_id TEXT NOT NULL,ordinal INTEGER NOT NULL,
                message_id TEXT NOT NULL,session_id TEXT NOT NULL,
                role TEXT NOT NULL,content TEXT NOT NULL,
                created_at TEXT NOT NULL,position INTEGER NOT NULL,
                PRIMARY KEY(candidate_id,ordinal)
            );
            CREATE TABLE memory_candidate_validity (
                candidate_id TEXT PRIMARY KEY,expires_at TEXT,
                reviewed_at TEXT NOT NULL,reviewed_by TEXT NOT NULL,
                reason TEXT NOT NULL
            );
        """)
        db.execute(
            "INSERT INTO memory_candidate VALUES(?,?,?,?,?,?)",
            (str(CANDIDATE), "PRIVATE-REMOVED-SUMMARY",
             NOW.isoformat(), "promoted", "person:sparks", "local:text"),
        )
        db.execute(
            "INSERT INTO memory_candidate_source VALUES(?,?,?,?,?,?,?,?)",
            (str(CANDIDATE), 0, "message:one", "session:one",
             "user", "PRIVATE-REMOVED-SOURCE", NOW.isoformat(), 0),
        )
        db.execute(
            "INSERT INTO memory_candidate_validity VALUES(?,?,?,?,?)",
            (str(CANDIDATE), None, NOW.isoformat(), "person:sparks", "approved"),
        )
    operator = tmp_path / "separate-operator-journal"
    operator.mkdir()
    cipher = BackupCipher(b"k" * 32)
    ledger = MemoryDeletionLedger(operator / "erasure.jsonl", cipher)
    ledger.initialize()
    engine = BackupEngine(cipher)
    return state, ledger, engine


def _erase(ledger):
    assert ledger.request(
        candidate_id=CANDIDATE, principal_id="person:sparks",
        audience_id="local:text",
        authority_ref="operator:approved-delete-01",
        at=NOW,
        approve=lambda candidate, principal, audience, approval: (
            candidate == str(CANDIDATE)
            and principal == "person:sparks"
            and audience == "local:text"
            and approval == "operator:approved-delete-01"
        ),
    ) is True


def _assert_no_deleted_candidate(db_path):
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT content FROM memory_candidate WHERE candidate_id=?",
            (str(CANDIDATE),),
        ).fetchone() is None
        assert db.execute(
            "SELECT content FROM memory_candidate_source WHERE candidate_id=?",
            (str(CANDIDATE),),
        ).fetchone() is None
        assert db.execute(
            "SELECT * FROM memory_candidate_validity WHERE candidate_id=?",
            (str(CANDIDATE),),
        ).fetchone() is None


def test_deletion_replayed_before_older_backup_is_published(
    tmp_path, monkeypatch,
):
    state, ledger, engine = _prepare(tmp_path)
    backup, _evidence = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="venus", failure_domain="offline",
        now=NOW,
    )
    # The encrypted backup predates the candidate deletion and is NOT
    # rewritten. An independently authenticated external journal survives.
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT content FROM memory_candidate",
        ).fetchone()[0] == "PRIVATE-REMOVED-SUMMARY"

    _erase(ledger)
    assert ledger.apply_to_sqlite(state) == 1
    assert ledger.apply_to_sqlite(state) == 0
    _assert_no_deleted_candidate(state)

    monkeypatch.setattr(
        "sofia.ops.backup.verify_production_component_schemas",
        lambda _state: None,
    )
    restored = tmp_path / "restored" / "sofia.db"
    receipt = engine.restore(
        backup_dir=backup, target_state_path=restored,
        verifier="offline-owner-recovery", erasure_journal=ledger.path,
        now=NOW,
    )
    assert receipt.succeeded is True
    _assert_no_deleted_candidate(restored)
    assert engine.verify(backup).backup_id == receipt.backup_id
    assert len(ledger.entries()) == 1


def test_restore_fails_closed_without_external_current_journal(tmp_path):
    state, ledger, engine = _prepare(tmp_path)
    backup, _evidence = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="venus", failure_domain="offline",
        now=NOW,
    )
    target = tmp_path / "dangerous-restore" / "sofia.db"
    with pytest.raises(BackupError, match="erasure_journal"):
        engine.restore(
            backup_dir=backup, target_state_path=target,
            verifier="untrusted-restore",
        )
    assert not target.exists()


def test_restore_denies_tampered_or_truncated_journal_before_publish(tmp_path):
    state, ledger, engine = _prepare(tmp_path)
    backup, _ = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="venus", failure_domain="offline",
        now=NOW,
    )
    _erase(ledger)
    ledger.path.write_bytes(ledger.path.read_bytes()[:-12])
    target = tmp_path / "restore" / "sofia.db"
    with pytest.raises(BackupError, match="deletion journal"):
        engine.restore(
            backup_dir=backup, target_state_path=target,
            verifier="not-approved", erasure_journal=ledger.path,
        )
    assert not target.exists()


def test_journal_requires_independent_approval_and_original_audience(tmp_path):
    state, ledger, _engine = _prepare(tmp_path)
    with pytest.raises(PermissionError, match="authority"):
        ledger.request(
            candidate_id=CANDIDATE,
            principal_id="person:sparks", audience_id="local:text",
            authority_ref="unknown", at=NOW,
            approve=lambda *_: False,
        )
    assert ledger.entries() == ()
    with pytest.raises(MemoryErasureError, match="scope conflict"):
        _erase(ledger)
        ledger.request(
            candidate_id=CANDIDATE,
            principal_id="person:other", audience_id="private:other",
            authority_ref="operator:approved-delete-01", at=NOW,
            approve=lambda *_: True,
        )
    assert ledger.apply_to_sqlite(state) == 1
    _assert_no_deleted_candidate(state)
