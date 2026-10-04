from datetime import datetime, timedelta, timezone

import pytest

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane
from sofia.state.replication import (
    ReplicatedStatePlane,
    ReplicationPartialCommitError,
    SQLiteReplicationWitness,
    StaleWriterError,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)


def record(key: StateKey, revision: int, value: bytes) -> StateRecord:
    return StateRecord(
        key=key,
        state_class=StateClass.SHARED_AUTHORITATIVE,
        revision=revision,
        value=value,
        updated_at=NOW + timedelta(seconds=revision),
        source="test:replication",
    )


class FlakyPlane(StatePlane):
    def __init__(self, inner: StatePlane) -> None:
        self.inner = inner
        self.fail = False

    @property
    def schema_revision(self):
        return self.inner.schema_revision

    def read(self, key):
        return self.inner.read(key)

    def write(self, record, *, expected_revision):
        if self.fail:
            raise OSError("replica unavailable")
        return self.inner.write(record, expected_revision=expected_revision)

    def delete(self, key, *, expected_revision):
        if self.fail:
            raise OSError("replica unavailable")
        return self.inner.delete(key, expected_revision=expected_revision)

    def list_namespace(self, namespace, *, principal_id=None, audience=None):
        return self.inner.list_namespace(
            namespace,
            principal_id=principal_id,
            audience=audience,
        )


def make_plane(tmp_path, *, replica=None, writer="writer-a", now=NOW):
    primary = SQLiteStatePlane(tmp_path / "primary.db")
    secondary = replica or SQLiteStatePlane(tmp_path / "secondary.db")
    witness = SQLiteReplicationWitness(tmp_path / "witness.db")
    plane = ReplicatedStatePlane(
        {"primary": primary, "secondary": secondary},
        witness=witness,
        writer_id=writer,
        primary_target_id="primary",
        now=now,
    )
    return plane, primary, secondary, witness


def test_replicated_write_commits_to_every_target(tmp_path):
    plane, primary, secondary, witness = make_plane(tmp_path)
    key = StateKey("test", "alpha")
    desired = record(key, 1, b"one")

    assert plane.write(desired, expected_revision=None) == desired
    assert primary.read(key) == desired
    assert secondary.read(key) == desired

    health = witness.health()
    assert health.pending_operations == 0
    assert health.committed_sequence == 1
    assert all(item.last_acked_sequence == 1 for item in health.targets)


def test_partial_commit_blocks_new_writes_until_repaired(tmp_path):
    secondary = FlakyPlane(SQLiteStatePlane(tmp_path / "secondary.db"))
    plane, primary, _, witness = make_plane(tmp_path, replica=secondary)
    key = StateKey("test", "alpha")
    secondary.fail = True

    with pytest.raises(ReplicationPartialCommitError):
        plane.write(record(key, 1, b"one"), expected_revision=None)

    assert primary.read(key) is not None
    with pytest.raises(ReplicationPartialCommitError):
        plane.write(
            record(StateKey("test", "beta"), 1, b"two"),
            expected_revision=None,
        )

    secondary.fail = False
    assert plane.repair_pending() == 1
    assert witness.health().pending_operations == 0
    assert secondary.read(key) == primary.read(key)


def test_expired_writer_is_fenced_after_takeover(tmp_path):
    plane, _, _, witness = make_plane(tmp_path, writer="writer-a", now=NOW)
    takeover = witness.acquire_writer(
        "writer-b",
        now=NOW + timedelta(seconds=31),
        ttl_seconds=30,
    )
    assert takeover.epoch == plane.writer_lease.epoch + 1

    with pytest.raises(StaleWriterError):
        plane.write(
            record(StateKey("test", "stale"), 1, b"nope"),
            expected_revision=None,
        )


def test_promotion_switches_read_primary_only_when_caught_up(tmp_path):
    plane, primary, secondary, witness = make_plane(tmp_path)
    key = StateKey("test", "alpha")
    desired = record(key, 1, b"one")
    plane.write(desired, expected_revision=None)

    plane.promote("secondary")
    assert witness.health().primary_target_id == "secondary"
    assert plane.read(key) == secondary.read(key) == primary.read(key)


def test_replicated_delete_is_idempotently_repairable(tmp_path):
    secondary = FlakyPlane(SQLiteStatePlane(tmp_path / "secondary.db"))
    plane, primary, _, witness = make_plane(tmp_path, replica=secondary)
    key = StateKey("test", "alpha")
    plane.write(record(key, 1, b"one"), expected_revision=None)

    secondary.fail = True
    with pytest.raises(ReplicationPartialCommitError):
        plane.delete(key, expected_revision=1)
    assert primary.read(key) is None

    secondary.fail = False
    plane.repair_pending()
    assert secondary.read(key) is None
    assert witness.health().pending_operations == 0
