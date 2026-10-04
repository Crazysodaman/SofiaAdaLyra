from datetime import datetime, timezone
from dataclasses import asdict, replace
import json
import sqlite3
import pytest

from sofia.knowledge.lifecycle import (
    DocumentDisposition,
    SQLiteKnowledgeLifecycle,
)
from sofia.knowledge.model import (
    KnowledgeDocument,
    KnowledgeFact,
    SourceKind,
)
from sofia.knowledge.persistence import (
    SQLiteKnowledgeStore,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def document():
    return KnowledgeDocument(
        document_id="doc-1",
        source_kind=SourceKind.MANUAL,
        source_uri="manual://doc-1",
        version="1",
        retrieved_at=NOW,
        content_hash="abc123",
        trusted_for_reference=True,
    )


def fact():
    return KnowledgeFact(
        fact_id="fact-1",
        document_id="doc-1",
        statement="Grounded test fact.",
        locator="line:1",
        observed_at=NOW,
    )


def test_sqlite_knowledge_round_trip_uses_canonical_database(tmp_path):
    state = tmp_path / "sofia.db"
    store = SQLiteKnowledgeStore(state)
    store.register_document(document())
    store.record_fact(fact())

    restored = SQLiteKnowledgeStore(state)

    assert restored.document("doc-1") == document()
    assert restored.fact("fact-1") == fact()


def test_legacy_knowledge_json_migrates_and_retires(tmp_path):
    legacy_path = tmp_path / "knowledge.json"
    doc = asdict(document())
    doc.update(source_kind=document().source_kind.value, retrieved_at=NOW.isoformat())
    value = asdict(fact())
    value["observed_at"] = NOW.isoformat()
    legacy_path.write_text(json.dumps({"documents": [doc], "facts": [value]}), encoding="utf-8")

    state = tmp_path / "sofia.db"
    store = SQLiteKnowledgeStore(
        state,
        legacy_path=legacy_path,
    )

    assert store.document("doc-1") == document()
    assert store.fact("fact-1") == fact()
    assert not legacy_path.exists()
    assert (tmp_path / "knowledge.json.migrated").is_file()


def test_sqlite_lifecycle_round_trip_and_legacy_migration(tmp_path):
    legacy_path = tmp_path / "knowledge-lifecycle.json"
    legacy_path.write_text(json.dumps([
        {"document_id": "doc-1", "disposition": "superseded", "replaced_by": "doc-2"},
        {"document_id": "doc-2", "disposition": "active", "replaced_by": None},
    ]), encoding="utf-8")

    state = tmp_path / "sofia.db"
    lifecycle = SQLiteKnowledgeLifecycle(
        state,
        legacy_path=legacy_path,
    )

    assert lifecycle.status("doc-1").disposition is (
        DocumentDisposition.SUPERSEDED
    )
    assert lifecycle.status("doc-1").replaced_by == "doc-2"
    assert lifecycle.active("doc-1") is False
    assert lifecycle.active("doc-2") is True
    assert not legacy_path.exists()
    assert (tmp_path / "knowledge-lifecycle.json.migrated").is_file()

    restored = SQLiteKnowledgeLifecycle(state)
    assert restored.status("doc-1") == lifecycle.status("doc-1")


@pytest.mark.parametrize("target", ["document", "fact"])
def test_failed_knowledge_write_does_not_publish_unpersisted_cache(tmp_path, target):
    state = tmp_path / "sofia.db"
    store = SQLiteKnowledgeStore(state)
    if target == "fact":
        store.register_document(document())
    table = "knowledge_" + target
    with sqlite3.connect(state) as db:
        db.execute(f"CREATE TRIGGER block_write BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'blocked'); END")

    with pytest.raises(sqlite3.IntegrityError, match="blocked"):
        store.register_document(document()) if target == "document" else store.record_fact(fact())

    assert store.document("doc-1") == (None if target == "document" else document())
    assert store.fact("fact-1") is None
    restored = SQLiteKnowledgeStore(state)
    assert restored.documents() == store.documents()
    assert restored.facts() == store.facts()
    with sqlite3.connect(state) as db:
        db.execute("DROP TRIGGER block_write")
    store.register_document(document()) if target == "document" else store.record_fact(fact())
    restored = SQLiteKnowledgeStore(state)
    assert restored.documents() == store.documents()
    assert restored.facts() == store.facts()


@pytest.mark.parametrize("operation", ["register", "supersede", "invalidate"])
def test_failed_lifecycle_write_keeps_last_durable_status(tmp_path, operation):
    state = tmp_path / "sofia.db"
    lifecycle = SQLiteKnowledgeLifecycle(state)
    lifecycle.register("doc-1")
    lifecycle.register("doc-2")
    with sqlite3.connect(state) as db:
        db.execute("CREATE TRIGGER block_write BEFORE INSERT ON knowledge_document_lifecycle BEGIN SELECT RAISE(ABORT, 'blocked'); END")

    with pytest.raises(sqlite3.IntegrityError, match="blocked"):
        if operation == "register":
            lifecycle.register("new-doc")
        elif operation == "supersede":
            lifecycle.supersede("doc-1", "doc-2")
        else:
            lifecycle.invalidate("doc-1")

    assert lifecycle.status("new-doc") is None
    assert lifecycle.status("doc-1").disposition is DocumentDisposition.ACTIVE
    assert SQLiteKnowledgeLifecycle(state).status("doc-1") == lifecycle.status("doc-1")


def test_legacy_import_preserves_additional_canonical_knowledge(tmp_path):
    state = tmp_path / "sofia.db"
    store = SQLiteKnowledgeStore(state)
    extra = replace(document(), document_id="extra-doc", source_uri="manual://extra")
    store.register_document(extra)
    store.register_document(document())
    legacy = tmp_path / "knowledge.json"
    doc = asdict(document())
    doc.update(source_kind=document().source_kind.value, retrieved_at=NOW.isoformat())
    value = asdict(fact())
    value["observed_at"] = NOW.isoformat()
    legacy.write_text(json.dumps({"documents": [doc], "facts": [value]}), encoding="utf-8")

    migrated = SQLiteKnowledgeStore(state, legacy_path=legacy)

    assert migrated.document(extra.document_id) == extra
    assert migrated.document("doc-1") == document()
    assert migrated.fact("fact-1") == fact()
    assert not legacy.exists()
    assert legacy.with_name(legacy.name + ".migrated").is_file()
