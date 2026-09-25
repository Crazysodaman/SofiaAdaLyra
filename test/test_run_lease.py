from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run import LocalRunLeaseStore

START = datetime(2026, 9, 25, 18, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved (value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('yes')")
    return path


def test_initial_acquire_and_same_owner_renew_keep_epoch(state):
    store = LocalRunLeaseStore(state)
    first = store.acquire(owner_id="supervisor-a", now=START, ttl_seconds=30)
    assert first.status == "acquired"
    assert first.lease.epoch == 1

    renewed = store.acquire(
        owner_id="supervisor-a",
        now=START + timedelta(seconds=10),
        ttl_seconds=30,
    )
    assert renewed.status == "renewed"
    assert renewed.lease.epoch == 1
    assert renewed.lease.expires_at == START + timedelta(seconds=40)
    assert store.holds(renewed.lease, now=START + timedelta(seconds=20))


def test_other_owner_cannot_take_unexpired_lease(state):
    store = LocalRunLeaseStore(state)
    first = store.acquire(owner_id="supervisor-a", now=START)
    blocked = store.acquire(
        owner_id="supervisor-b",
        now=START + timedelta(seconds=1),
    )
    assert blocked.status == "held_by_other"
    assert blocked.holder_id == "supervisor-a"
    assert blocked.holder_epoch == first.lease.epoch


def test_expired_lease_takeover_increments_epoch_and_fences_old_owner(state):
    store = LocalRunLeaseStore(state)
    first = store.acquire(
        owner_id="supervisor-a",
        now=START,
        ttl_seconds=10,
    ).lease
    second = store.acquire(
        owner_id="supervisor-b",
        now=START + timedelta(seconds=10),
        ttl_seconds=10,
    )
    assert second.status == "acquired"
    assert second.lease.epoch == first.epoch + 1
    assert not store.holds(first, now=START + timedelta(seconds=11))

    stale = store.renew(
        first,
        now=START + timedelta(seconds=11),
        ttl_seconds=10,
    )
    assert stale.status == "stale"
    assert stale.holder_id == "supervisor-b"


def test_explicit_release_allows_new_epoch(state):
    store = LocalRunLeaseStore(state)
    first = store.acquire(owner_id="a", now=START).lease
    released = store.release(first, now=START + timedelta(seconds=5))
    assert released.status == "released"
    assert store.current(now=START + timedelta(seconds=6)) is None

    second = store.acquire(
        owner_id="b",
        now=START + timedelta(seconds=6),
    ).lease
    assert second.epoch == first.epoch + 1


def test_old_clock_is_uncertain_not_a_takeover(state):
    store = LocalRunLeaseStore(state)
    store.acquire(owner_id="a", now=START)
    result = store.acquire(
        owner_id="a",
        now=START - timedelta(seconds=1),
    )
    assert result.status == "clock_uncertain"


def test_expired_lease_cannot_be_renewed_without_new_epoch(state):
    store = LocalRunLeaseStore(state)
    first = store.acquire(
        owner_id="a",
        now=START,
        ttl_seconds=5,
    ).lease
    result = store.renew(
        first,
        now=START + timedelta(seconds=5),
        ttl_seconds=5,
    )
    assert result.status == "stale"
    reacquired = store.acquire(
        owner_id="a",
        now=START + timedelta(seconds=5),
        ttl_seconds=5,
    ).lease
    assert reacquired.epoch == first.epoch + 1


def test_events_are_audit_only_and_existing_state_is_preserved(state):
    store = LocalRunLeaseStore(state)
    lease = store.acquire(owner_id="a", now=START).lease
    lease = store.renew(
        lease,
        now=START + timedelta(seconds=5),
    ).lease
    store.release(lease, now=START + timedelta(seconds=6))
    kinds = [row[0] for row in store.events()]
    assert kinds == ["acquired", "renewed", "released"]
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT value FROM preserved").fetchone() == ("yes",)


@pytest.mark.parametrize("ttl", [0, 4, 301, True])
def test_invalid_ttl_rejected(state, ttl):
    store = LocalRunLeaseStore(state)
    with pytest.raises(ValueError):
        store.acquire(owner_id="a", now=START, ttl_seconds=ttl)


def test_existing_state_database_is_required(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalRunLeaseStore(tmp_path / "missing.db")
