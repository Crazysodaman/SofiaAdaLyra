"""Phase 06 temporal candidates cannot escape the canonical SQLite authority."""
from contextlib import closing
from datetime import datetime, timezone
import os
import sqlite3

import pytest

from sofia.core.memory.temporal_candidates import TemporalCandidateStore
from sofia.platform.state.canonical_sqlite import (
    CanonicalStateUnavailable, bootstrap_canonical_sqlite,
)

WHEN = datetime(2026, 10, 12, 16, 30, tzinfo=timezone.utc)


def _candidate(store, *, principal="person:sparks", audience="local:text", prior=None):
    return store.propose(
        principal_id=principal,
        audience_id=audience,
        subject_key="machine:artemis",
        assertion="Artemis has a verified environment change.",
        evidence_ref="conversation-original:123",
        asserted_valid_at=WHEN,
        supersedes_candidate_id=prior,
    )


def test_temporal_candidate_requires_prior_authorized_first_install(tmp_path):
    path = tmp_path / "missing" / "sofia.db"
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        TemporalCandidateStore(path)
    assert not path.exists()
    assert not path.parent.exists()


def test_temporal_candidates_persist_in_one_authorized_home_and_preserve_scope(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TemporalCandidateStore(path)
    record = _candidate(store)
    assert store.candidates(
        principal_id="person:sparks",
        audience_id="local:text",
        subject_key="machine:artemis",
    ) == (record,)
    assert store.candidates(
        principal_id="person:another",
        audience_id="local:text",
        subject_key="machine:artemis",
    ) == ()
    assert TemporalCandidateStore(path).candidates(
        principal_id="person:sparks",
        audience_id="local:text",
        subject_key="machine:artemis",
    ) == (record,)
    with pytest.raises(PermissionError, match="different audience"):
        _candidate(
            store, principal="person:another", prior=record.candidate_id,
        )


def test_temporal_memory_refuses_deleted_canonical_home_without_recreation(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TemporalCandidateStore(path)
    _candidate(store)
    path.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.candidates(
            principal_id="person:sparks", audience_id="local:text",
            subject_key="machine:artemis",
        )
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        _candidate(store)
    assert not path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows does not permit replacing open canonical SQLite owners")
def test_temporal_memory_refuses_replaced_canonical_home(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TemporalCandidateStore(path)
    _candidate(store)
    replacement = tmp_path / "replacement.db"
    with closing(sqlite3.connect(replacement)) as db, db:
        db.execute("CREATE TABLE decoy (id INTEGER)")
    os.replace(replacement, path)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.candidates(
            principal_id="person:sparks", audience_id="local:text",
            subject_key="machine:artemis",
        )
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        _candidate(store)
