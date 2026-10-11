"""Deferred fail-closed replication composition preflight contracts."""
from pathlib import Path
import sqlite3

import pytest

import sofia.state.factory as factory
from sofia.state.canonical_sqlite import CanonicalStateUnavailable
from sofia.state.replication import (
    ReplicatedStatePlane, SQLiteReplicationWitness, ReplicationError,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


def _paths(tmp_path, monkeypatch):
    primary = tmp_path / "venus" / "sofia.db"
    replica = tmp_path / "replica" / "sofia.db"
    witness = tmp_path / "separate-witness" / "writer.db"
    primary.parent.mkdir()
    replica.parent.mkdir()
    SQLiteStatePlane(primary)
    SQLiteStatePlane(replica)
    monkeypatch.setenv("SOFIA_STATE_REPLICATION_ENABLED", "true")
    monkeypatch.setenv("SOFIA_STATE_WITNESS_PATH", str(witness))
    monkeypatch.setenv("SOFIA_STATE_REPLICAS", f"secondary={replica}")
    monkeypatch.setenv("SOFIA_STATE_REPLICATION_AUTO_SEED", "false")
    monkeypatch.setenv("SOFIA_STATE_WRITER_ID", "Venus")
    return primary, replica, witness


def test_missing_witness_fails_before_constructing_any_replicated_plane(
    tmp_path, monkeypatch,
):
    primary, replica, witness = _paths(tmp_path, monkeypatch)
    attempts = []

    def unexpected_state_plane(path):
        attempts.append(path)
        raise AssertionError("no data plane may start without witness")

    monkeypatch.setattr(factory, "SQLiteStatePlane", unexpected_state_plane)
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        factory.create_state_plane(primary)
    assert attempts == []
    assert not witness.exists()
    assert primary.exists() and replica.exists()


def test_corrupt_existing_witness_rejects_replicated_startup(tmp_path, monkeypatch):
    primary, replica, witness = _paths(tmp_path, monkeypatch)
    witness.parent.mkdir()
    with sqlite3.connect(witness) as db:
        db.execute("CREATE TABLE unrelated (id INTEGER)")
    with pytest.raises(ReplicationError, match="witness schema missing"):
        factory.create_state_plane(primary)
    assert primary.exists() and replica.exists()


def test_explicitly_bootstrapped_witness_allows_existing_replicas(
    tmp_path, monkeypatch,
):
    primary, replica, witness = _paths(tmp_path, monkeypatch)
    SQLiteReplicationWitness(witness, allow_first_bootstrap=True)
    plane = factory.create_state_plane(primary)
    assert isinstance(plane, ReplicatedStatePlane)
    assert plane.writer_lease.owner_id == "Venus"
    assert plane.writer_lease.epoch == 1


def test_symlinked_independent_witness_is_not_normalized_away(
    tmp_path, monkeypatch,
):
    primary, replica, witness = _paths(tmp_path, monkeypatch)
    real = tmp_path / "unapproved" / "other.db"
    real.parent.mkdir()
    SQLiteReplicationWitness(real, allow_first_bootstrap=True)
    witness.parent.mkdir()
    try:
        witness.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(CanonicalStateUnavailable, match="symbolic link"):
        factory.create_state_plane(primary)
