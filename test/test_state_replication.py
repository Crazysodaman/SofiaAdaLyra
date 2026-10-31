from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.state.model import StateClass, StateKey, StateRecord
from sofia.platform.state.plane import StatePlane
from sofia.platform.state.replication import (
    ReplicatedStatePlane,
    ReplicationPartialCommitError,
    SQLiteReplicationWitness,
    StaleWriterError,
    WriterLeaseHeldError,
)
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


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


def _bootstrapped_plane(path):
    # This is an explicit disposable test setup, never an implicit owner write.
    return SQLiteStatePlane(bootstrap_canonical_sqlite(path))


def make_plane(tmp_path, *, replica=None, writer="writer-a", now=None):
    primary = _bootstrapped_plane(tmp_path / "primary.db")
    secondary = replica or _bootstrapped_plane(tmp_path / "secondary.db")
    witness = SQLiteReplicationWitness(
        tmp_path / "witness.db", allow_first_bootstrap=True,
    )
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
    secondary = FlakyPlane(_bootstrapped_plane(tmp_path / "secondary.db"))
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
    secondary = FlakyPlane(_bootstrapped_plane(tmp_path / "secondary.db"))
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



def test_second_acquire_is_denied_even_for_same_writer_id(tmp_path):
    _, _, _, witness = make_plane(tmp_path, writer="writer-a", now=NOW)

    with pytest.raises(WriterLeaseHeldError):
        witness.acquire_writer(
            "writer-a",
            now=NOW + timedelta(seconds=1),
            ttl_seconds=30,
        )


def test_expired_writer_cannot_renew_old_epoch_without_reacquiring(tmp_path):
    plane, _, _, witness = make_plane(tmp_path, writer="writer-a", now=NOW)

    with pytest.raises(StaleWriterError, match="expired"):
        witness.renew_writer(
            plane.writer_lease,
            now=NOW + timedelta(seconds=31),
            ttl_seconds=30,
        )

    reacquired = witness.acquire_writer(
        "writer-a",
        now=NOW + timedelta(seconds=31),
        ttl_seconds=30,
    )
    assert reacquired.epoch == plane.writer_lease.epoch + 1



def test_stale_writer_cannot_ack_or_commit_after_takeover(tmp_path):
    plane, _, _, witness = make_plane(tmp_path, writer="writer-a", now=NOW)
    key = StateKey("test", "pending")
    desired = record(key, 1, b"pending")
    sequence = witness.prepare(
        lease=plane.writer_lease,
        operation_kind="write",
        key=key,
        expected_revision=None,
        record=desired,
        now=NOW + timedelta(seconds=1),
    )

    witness.acquire_writer(
        "writer-b",
        now=NOW + timedelta(seconds=31),
        ttl_seconds=30,
    )

    with pytest.raises(StaleWriterError):
        witness.ack(
            sequence,
            "primary",
            lease=plane.writer_lease,
            ok=True,
            now=NOW + timedelta(seconds=31),
        )
    with pytest.raises(StaleWriterError):
        witness.commit_if_complete(
            sequence,
            lease=plane.writer_lease,
            target_ids=("primary", "secondary"),
            now=NOW + timedelta(seconds=31),
        )


def test_g3_previous_writer_cannot_private_serve_after_epoch_takeover(tmp_path):
    """Old Core must stop read/list access after a successor takes the lease."""
    plane, primary, secondary, witness = make_plane(tmp_path)
    key = StateKey(
        "private", "autobiography", principal_id="owner",
        audience="private:owner",
    )
    private_record = record(key, 1, b"protected owner context")
    assert plane.write(private_record, expected_revision=None) == private_record
    assert plane.read(key) == private_record
    assert plane.list_namespace(
        "private", principal_id="owner", audience="private:owner",
    ) == (private_record,)
    assert plane.list_scopes("private") == (("owner", "private:owner"),)

    prior = plane.writer_lease
    successor = witness.acquire_writer(
        "writer-on-artemis",
        now=prior.expires_at + timedelta(seconds=1),
        ttl_seconds=30,
    )
    assert successor.epoch == prior.epoch + 1

    with pytest.raises(StaleWriterError, match="fenced"):
        plane.read(key)
    with pytest.raises(StaleWriterError, match="fenced"):
        plane.list_namespace(
            "private", principal_id="owner", audience="private:owner",
        )
    with pytest.raises(StaleWriterError, match="fenced"):
        plane.list_scopes("private")
    # The old Core cannot renew read authority or mutate the shared state.
    with pytest.raises(StaleWriterError, match="fenced"):
        plane.write(record(key, 2, b"stale source must never change me"),
                    expected_revision=1)
    assert primary.read(key) == secondary.read(key) == private_record
    assert witness.current_writer() == successor


def test_g3_expired_core_cannot_read_even_before_takeover(tmp_path):
    """Lost witness contact/expired authority never implies read permission."""
    plane, _, _, witness = make_plane(tmp_path, now=NOW)
    current = witness.current_writer()
    assert current is not None
    assert current.expires_at < datetime.now(timezone.utc)
    key = StateKey("private", "state")
    with pytest.raises(StaleWriterError, match="expired"):
        plane.read(key)
    with pytest.raises(StaleWriterError, match="expired"):
        plane.list_namespace("private")
    with pytest.raises(StaleWriterError, match="expired"):
        plane.list_scopes("private")
    # Read requests deliberately do not renew or reacquire authority.
    assert witness.current_writer() == current


def test_g3_fencing_precedes_call_to_backing_storage(tmp_path, monkeypatch):
    """A fenced Core cannot even reach its legacy private backing plane."""
    plane, primary, _, witness = make_plane(tmp_path)
    owner = plane.writer_lease
    witness.acquire_writer(
        "successor", now=owner.expires_at + timedelta(seconds=1),
    )
    accesses = []
    def forbidden(*args, **kwargs):
        accesses.append((args, kwargs))
        raise AssertionError("stale Core accessed private storage")
    monkeypatch.setattr(primary, "read", forbidden)
    monkeypatch.setattr(primary, "list_namespace", forbidden)
    monkeypatch.setattr(primary, "list_scopes", forbidden)
    with pytest.raises(StaleWriterError):
        plane.read(StateKey("private", "memory"))
    with pytest.raises(StaleWriterError):
        plane.list_namespace("private")
    with pytest.raises(StaleWriterError):
        plane.list_scopes("private")
    assert accesses == []
