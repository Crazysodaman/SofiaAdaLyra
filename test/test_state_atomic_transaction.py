from datetime import datetime, timezone

import pytest

from sofia.platform.state import (
    SQLiteStatePlane,
    StateClass,
    StateKey,
    StatePlaneConflictError,
    StateRecord,
    StateWrite,
)


NOW = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)


def record(key: str, value: bytes, *, revision: int = 1) -> StateRecord:
    return StateRecord(
        key=StateKey("platform.test", key, "principal:owner", "private"),
        state_class=StateClass.SHARED_AUTHORITATIVE,
        revision=revision,
        value=value,
        updated_at=NOW,
        source="test:platform-transaction",
    )


def test_atomic_state_writes_commit_together_and_record_lineage(canonical_state_path):
    plane = SQLiteStatePlane(canonical_state_path)
    first, second = plane.write_transaction(
        (StateWrite(record("one", b"a"), None), StateWrite(record("two", b"b"), None))
    )
    assert (first.revision, second.revision) == (1, 1)
    lineage = plane.audit_lineage(namespace="platform.test")
    assert [item["record_key"] for item in lineage] == ["two", "one"]
    assert all(item["operation"] == "write" for item in lineage)
    assert all(len(str(item["value_sha256"])) == 64 for item in lineage)


def test_atomic_state_write_rolls_back_all_records_on_stale_revision(canonical_state_path):
    plane = SQLiteStatePlane(canonical_state_path)
    plane.write(record("existing", b"old"), expected_revision=None)
    with pytest.raises(StatePlaneConflictError):
        plane.write_transaction(
            (
                StateWrite(record("new", b"must-not-survive"), None),
                StateWrite(record("existing", b"stale", revision=3), 2),
            )
        )
    assert plane.read(record("new", b"").key) is None
    assert plane.read(record("existing", b"").key).value == b"old"
    assert [item["record_key"] for item in plane.audit_lineage()] == ["existing"]


def test_atomic_state_write_rejects_duplicate_key(canonical_state_path):
    plane = SQLiteStatePlane(canonical_state_path)
    with pytest.raises(ValueError, match="same key"):
        plane.write_transaction(
            (StateWrite(record("one", b"a"), None), StateWrite(record("one", b"b"), None))
        )


def test_delete_preserves_hashed_lineage_without_record_content(canonical_state_path):
    plane = SQLiteStatePlane(canonical_state_path)
    created = plane.write(record("one", b"private-content"), expected_revision=None)
    plane.delete(created.key, expected_revision=1)
    assert plane.read(created.key) is None
    event = plane.audit_lineage(limit=1)[0]
    assert event["operation"] == "delete"
    assert event["record_key"] == "one"
    assert "private-content" not in repr(event)
