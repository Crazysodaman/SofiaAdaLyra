"""Evidence lookup must not invent timestamps from incomplete conversation schemas."""
from datetime import datetime, timezone
import sqlite3

from sofia.goals.evidence import GoalEvidenceIndex
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_minimal_conversation_schema_does_not_crash_or_promote_missing_evidence(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, role TEXT)")
        db.execute(
            "INSERT INTO conversation_messages VALUES (?, ?)",
            ("a-real-message-without-timestamp", "user"),
        )
    index = GoalEvidenceIndex(state)
    assert index.lookup("goal-evidence:imaginary") is None
    assert index.lookup("a-real-message-without-timestamp") is None


def test_timestamped_conversation_schema_remains_a_valid_evidence_source(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    observed = datetime(2026, 10, 13, 17, 0, tzinfo=timezone.utc)
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE conversation_messages "
            "(id TEXT PRIMARY KEY, role TEXT, created_at TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO conversation_messages VALUES (?, ?, ?)",
            ("evidence-message", "user", observed.isoformat()),
        )
    result = GoalEvidenceIndex(state).lookup("evidence-message")
    assert result is not None
    assert result.kind == "conversation_message"
    assert result.observed_at == observed
    assert result.source == "conversation"
