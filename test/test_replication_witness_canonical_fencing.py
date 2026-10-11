"""Deferred independent witness lost/replaced authority regression contracts.

The witness is NOT sofia.db; it must live in an independent failure domain.
Live runtime never creates a missing epoch-one witness.
"""
from datetime import datetime, timezone
import os
import sqlite3

import pytest

from sofia.state.canonical_sqlite import CanonicalStateUnavailable
from sofia.state.replication import (
    SQLiteReplicationWitness, ReplicationError,
)


NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def test_missing_witness_cannot_start_production_control_plane(tmp_path):
    path = tmp_path / "separate-witness" / "witness.db"
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        SQLiteReplicationWitness(path)
    assert not path.parent.exists()


def test_first_bootstrap_is_explicit_and_restart_retains_writer_epoch(tmp_path):
    path = tmp_path / "witness.db"
    witness = SQLiteReplicationWitness(path, allow_first_bootstrap=True)
    lease = witness.acquire_writer("Venus", now=NOW, ttl_seconds=30)
    assert lease.epoch == 1
    restart = SQLiteReplicationWitness(path)
    current = restart.current_writer()
    assert current is not None
    assert current.owner_id == "Venus"
    assert current.epoch == lease.epoch
    assert path.is_file()


def test_witness_loss_does_not_allow_fresh_epoch_one_takeover(tmp_path):
    path = tmp_path / "witness.db"
    witness = SQLiteReplicationWitness(path, allow_first_bootstrap=True)
    witness.acquire_writer("Venus", now=NOW, ttl_seconds=30)
    path.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        witness.current_writer()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        SQLiteReplicationWitness(path)
    assert not path.exists()


def test_witness_file_replacement_rejected_by_existing_owner(tmp_path):
    path = tmp_path / "witness.db"
    witness = SQLiteReplicationWitness(path, allow_first_bootstrap=True)
    witness.acquire_writer("Venus", now=NOW, ttl_seconds=30)
    other = tmp_path / "imposter.db"
    with sqlite3.connect(other) as db:
        db.execute("CREATE TABLE decoy (x INTEGER)")
    os.replace(other, path)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        witness.current_writer()
    with pytest.raises(ReplicationError, match="witness schema missing"):
        SQLiteReplicationWitness(path)


def test_existing_empty_witness_cannot_be_accepted_as_prior_authority(tmp_path):
    path = tmp_path / "witness.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE empty (x INTEGER)")
    with pytest.raises(ReplicationError, match="witness schema missing"):
        SQLiteReplicationWitness(path)
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='replication_writer'"
        ).fetchone() is None
