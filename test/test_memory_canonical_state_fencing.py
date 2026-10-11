"""Promoted-memory canonical source fencing contracts.

Authored but intentionally not executed during the V18 coding workstream.
"""
from datetime import datetime, timezone
import os
import sqlite3
from uuid import uuid4

import pytest

from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import MemoryCandidate, CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.state.canonical_sqlite import CanonicalStateUnavailable


def _candidate():
    now = datetime.now(timezone.utc)
    return MemoryCandidate(
        candidate_id=uuid4(),
        content="A promoted fact with source provenance",
        sources=(SourceMessage(
            message_id="original-1", session_id="owner-session",
            role="user", content="Original source text",
            created_at=now, position=0,
        ),),
        created_at=now,
        principal_id="person:sparks",
        audience_id="desktop:private",
    )


def test_promoted_memory_refuses_missing_canonical_state_after_restart(tmp_path):
    path = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(path)
    candidate = _candidate()
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    store.close()
    path.unlink()

    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.open()
    assert not path.exists()


def test_promoted_memory_refuses_replacement_after_restart(tmp_path):
    path = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(path)
    candidate = _candidate()
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    store.close()

    alternate = tmp_path / "other.db"
    with sqlite3.connect(alternate) as conn:
        conn.execute("CREATE TABLE decoy (x INTEGER)")
    os.replace(alternate, path)

    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.open()
    with pytest.raises(RuntimeError, match="closed"):
        store.list_ids(status=CandidateStatus.PROMOTED)


@pytest.mark.skipif(os.name == "nt", reason="Windows prevents replacement of open SQLite files")
def test_open_memory_handle_refuses_orphaned_state_after_swap(tmp_path):
    path = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(path)
    candidate = _candidate()
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    alternate = tmp_path / "alternate.db"
    with sqlite3.connect(alternate) as conn:
        conn.execute("CREATE TABLE decoy (x INTEGER)")
    try:
        os.replace(alternate, path)
        with pytest.raises(CanonicalStateUnavailable, match="replaced"):
            store.get(candidate.candidate_id)
        with pytest.raises(CanonicalStateUnavailable, match="replaced"):
            store.revoke(candidate.candidate_id)
    finally:
        store.close()
