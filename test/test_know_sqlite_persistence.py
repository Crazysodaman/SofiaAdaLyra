from datetime import datetime, timezone

from sofia.knowledge.lifecycle import (
    DocumentDisposition,
    KnowledgeLifecycle,
    SQLiteKnowledgeLifecycle,
)
from sofia.knowledge.model import (
    KnowledgeDocument,
    KnowledgeFact,
    SourceKind,
)
from sofia.knowledge.persistence import (
    JsonKnowledgeStore,
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
    legacy = JsonKnowledgeStore(legacy_path)
    legacy.register_document(document())
    legacy.record_fact(fact())

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
    legacy = KnowledgeLifecycle(legacy_path)
    legacy.register("doc-1")
    legacy.register("doc-2")
    legacy.supersede("doc-1", "doc-2")

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
