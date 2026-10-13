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

 
def test_goal_evidence_fails_closed_if_database_swapped_during_read_open(
    tmp_path, monkeypatch,
):
    from contextlib import closing
    import os
    import pytest
    from sofia.state.canonical_sqlite import CanonicalStateUnavailable

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    replacement = bootstrap_canonical_sqlite(tmp_path / "other.db")
    index = GoalEvidenceIndex(state)
    actual_connect = sqlite3.connect
    swapped = []

    def swap_during_sqlite_open(database, *args, **kwargs):
        if not swapped:
            # The existing owner has already validated the original inode.
            # A rogue state replacement before sqlite3_open must be rejected
            # even if the replacement itself has a well-formed SQLite schema.
            os.replace(replacement, state)
            swapped.append(True)
        return actual_connect(database, *args, **kwargs)

    monkeypatch.setattr(
        "sofia.state.canonical_sqlite.sqlite3.connect",
        swap_during_sqlite_open,
    )
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        index.lookup("goal-evidence:forged")
    assert swapped == [True]


def test_guard_read_only_connection_cannot_mutate_database(tmp_path):
    from contextlib import closing
    import pytest
    from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with closing(CanonicalSQLiteGuard(path).connect(read_only=True)) as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("CREATE TABLE unauthorized_evidence(id TEXT PRIMARY KEY)")
