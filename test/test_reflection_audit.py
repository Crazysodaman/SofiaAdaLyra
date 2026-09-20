"""Audit cannot fabricate worker activity or expose private journal prose."""
from datetime import datetime, timezone
from hashlib import sha256
import sqlite3

from sofia.personality.audit import reflection_audit
from sofia.personality.reflection import ReflectionJournal

NOW = datetime(2026, 9, 20, 20, tzinfo=timezone.utc)


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.db"
    assert reflection_audit(path)["database"] == "missing"
    assert reflection_audit(path)["model_thoughts"] == "unknown"
    assert not path.exists()


def test_missing_worker_schema_is_not_reported_as_zero_activity(tmp_path):
    path = tmp_path / "state.db"
    store = ReflectionJournal(path)
    assert store.recent_thoughts() == ()
    report = reflection_audit(path)
    assert report["idle_worker"] == "not_installed"
    assert report["model_thoughts"] == 0
    assert report["idle_attempts"] == "unknown"
    assert report["pending_unsent"] == 0


def test_completed_worker_event_with_thought_and_abstention_are_distinct(tmp_path):
    path = tmp_path / "state.db"
    store = ReflectionJournal(path)
    event_id = "actual-event-1"
    model_thought = "model-reflection:" + sha256(event_id.encode()).hexdigest()[:32]
    store.record_thought(thought_id=model_thought, kind="reflection",
                         subject="Sensitive subject", content="Private model reflection text",
                         evidence_refs=(event_id,), created_at=NOW)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE idle_reflection_attempts (
            event_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            claimed_at TEXT NOT NULL, next_retry_at TEXT, last_error_type TEXT)""")
        db.executemany("INSERT INTO idle_reflection_attempts VALUES (?,?,?,?,?)", [
            (event_id, "done", NOW.isoformat(), None, None),
            ("valid-abstention", "done", NOW.isoformat(), None, None),
            ("failed-event", "failed", NOW.isoformat(), NOW.isoformat(), "RuntimeError"),
        ])
    report = reflection_audit(path)
    assert report["idle_worker"] == "installed"
    assert report["idle_attempts"] == {"done": 2, "failed": 1}
    assert report["completed_with_model_thought"] == 1
    assert report["completed_without_model_thought"] == 1
    assert report["last_error_type"] == "RuntimeError"
    assert report["last_model_thought_at"] == NOW.isoformat()
    assert "Private model reflection text" not in str(report)
    assert "Sensitive subject" not in str(report)
    assert event_id not in str(report)


def test_database_not_modified_by_audit(tmp_path):
    path = tmp_path / "state.db"
    ReflectionJournal(path)
    before = path.stat().st_mtime_ns
    reflection_audit(path)
    after = path.stat().st_mtime_ns
    assert before == after
