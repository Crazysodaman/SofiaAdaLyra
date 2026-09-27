from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.memory.chatgpt_import import parse_chatgpt_memory_dump
from sofia.memory.chatgpt_import_store import ChatGPTMemoryImportStore
from sofia.memory.chatgpt_migration import ChatGPTMemoryMigrationService
from sofia.memory.import_chatgpt import main as import_chatgpt_main
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID, local_sparks_principal
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.verify.semantic_integrity import SemanticIntegrityVerifier


PAYLOAD = """{
  "memories": [
    {
      "id": "model-trains",
      "content": "Sparks prefers HO scale model trains.",
      "created_at": "2026-09-01T12:00:00Z"
    },
    {
      "id": "server",
      "content": "Artemis is Sparks' Windows server."
    }
  ]
}"""


def _import(
    state_path: Path,
):
    batch = parse_chatgpt_memory_dump(
        PAYLOAD,
        observed_at=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )
    store = ChatGPTMemoryImportStore(state_path)
    assert store.save(batch, original_payload=PAYLOAD) is True
    migration = ChatGPTMemoryMigrationService(
        state_path,
        imports=store,
    )
    candidate_ids = migration.propose_batch(batch.source_digest)
    return batch, store, migration, candidate_ids


def test_parser_preserves_exact_source_identity_and_timestamp():
    batch = parse_chatgpt_memory_dump(
        PAYLOAD,
        observed_at=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )

    assert len(batch.items) == 2
    assert batch.items[0].source_id.endswith(":model-trains")
    assert batch.items[0].content == "Sparks prefers HO scale model trains."
    assert batch.items[0].source_created_at == datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )
    assert batch.items[1].source_created_at is None
    assert len(batch.source_digest) == 64


def test_parser_accepts_plain_text_memory_summary():
    batch = parse_chatgpt_memory_dump(
        "- Sparks prefers clear chunked formatting.\n"
        "- Sofía's canonical name is Sofía Ada Lyra.\n",
        observed_at=datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    )

    assert [item.content for item in batch.items] == [
        "Sparks prefers clear chunked formatting.",
        "Sofía's canonical name is Sofía Ada Lyra.",
    ]


def test_exact_import_is_durable_and_idempotent_across_restart(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"
    batch = parse_chatgpt_memory_dump(PAYLOAD)

    first = ChatGPTMemoryImportStore(state_path)
    assert first.save(batch, original_payload=PAYLOAD) is True
    assert first.save(batch, original_payload=PAYLOAD) is False
    assert first.original_payload(batch.source_digest) == PAYLOAD
    first.close()

    reopened = ChatGPTMemoryImportStore(state_path)
    restored = reopened.load_batch(batch.source_digest)

    assert restored == batch
    assert reopened.list_imports() == (
        (batch.source_digest, batch.observed_at, 2),
    )
    reopened.close()


def test_import_proposes_sparks_scoped_memory_without_cognitive_visibility(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"
    batch, store, migration, candidate_ids = _import(state_path)

    assert len(candidate_ids) == 2
    for candidate_id in candidate_ids:
        candidate = migration.candidates.get(candidate_id)
        assert candidate is not None
        assert candidate.principal_id == SPARKS_PRINCIPAL_ID
        assert candidate.audience_id is None
        assert candidate.sources[0].session_id == (
            f"chatgpt-import:{batch.source_digest}"
        )
        assert migration.candidates.status(candidate_id) is CandidateStatus.PROPOSED

    memory_store = MemoryStore(state_path)
    memory = MemorySystem(
        memory_store,
        candidate_store=migration.candidates,
    )
    assert memory.recall_relevant(
        "model trains",
        principal=local_sparks_principal(),
    ) == ()

    memory_store.close()
    migration.close()
    store.close()


def test_explicit_sparks_promotion_enters_reviewed_retrieval_and_survives_restart(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"
    _, store, migration, candidate_ids = _import(state_path)
    promoted_at = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)

    with pytest.raises(PermissionError):
        migration.promote(
            candidate_ids[0],
            approved_by="not-sparks",
            at=promoted_at,
        )

    migration.promote(
        candidate_ids[0],
        approved_by="Sparks",
        at=promoted_at,
    )
    migration.close()
    store.close()

    candidate_store = DurableMemoryCandidateStore(state_path)
    memory_store = MemoryStore(state_path)
    memory = MemorySystem(
        memory_store,
        candidate_store=candidate_store,
    )

    recalled = memory.recall_relevant(
        "HO scale model trains",
        principal=local_sparks_principal(),
    )
    assert len(recalled) == 1
    assert recalled[0].content == "Sparks prefers HO scale model trains."

    other = PrincipalContext(
        principal_id="person:someone-else",
        audience_id="local:text",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Someone Else",
    )
    assert memory.recall_relevant(
        "HO scale model trains",
        principal=other,
    ) == ()

    memory.close()


def test_semantic_integrity_links_promoted_memory_back_to_exact_import(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"
    state_plane = SQLiteStatePlane(state_path)
    batch, store, migration, candidate_ids = _import(state_path)

    migration.promote(
        candidate_ids[0],
        approved_by="Sparks",
        at=datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc),
    )
    migration.close()
    store.close()

    verifier = SemanticIntegrityVerifier(
        state_path,
        state_plane=state_plane,
    )
    clean = verifier.verify()
    assert clean.accepted is True

    with sqlite3.connect(state_path) as db:
        db.execute(
            """
            UPDATE chatgpt_memory_import_item
            SET content=?
            WHERE source_digest=? AND source_id=?
            """,
            (
                "tampered evidence",
                batch.source_digest,
                batch.items[0].source_id,
            ),
        )
        db.commit()

    tampered = verifier.verify()
    assert tampered.accepted is False
    assert "memory.import_source_changed" in {
        item.code for item in tampered.findings
    }


def test_cli_dry_run_import_then_explicit_bulk_promotion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    source = tmp_path / "chatgpt-memory.json"
    source.write_text(PAYLOAD, encoding="utf-8")
    state_path = tmp_path / "sofia.db"

    assert import_chatgpt_main(
        [
            str(source),
            "--state-path",
            str(state_path),
            "--dry-run",
        ]
    ) == 0
    assert state_path.exists() is False

    assert import_chatgpt_main(
        [
            str(source),
            "--state-path",
            str(state_path),
        ]
    ) == 0

    candidate_store = DurableMemoryCandidateStore(state_path)
    proposed = candidate_store.list_ids(
        status=CandidateStatus.PROPOSED,
        principal_id=SPARKS_PRINCIPAL_ID,
    )
    assert len(proposed) == 2
    candidate_store.close()

    assert import_chatgpt_main(
        [
            str(source),
            "--state-path",
            str(state_path),
            "--promote-all",
            "--approved-by",
            "Sparks",
        ]
    ) == 0

    candidate_store = DurableMemoryCandidateStore(state_path)
    promoted = candidate_store.list_ids(
        status=CandidateStatus.PROMOTED,
        principal_id=SPARKS_PRINCIPAL_ID,
    )
    assert len(promoted) == 2
    candidate_store.close()

    output = capsys.readouterr().out
    assert "proposed_for_review" in output
    assert "memory_status=promoted" in output
