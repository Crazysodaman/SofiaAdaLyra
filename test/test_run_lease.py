from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.platform.run import LocalRunLeaseStore

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


def test_scoped_leases_are_independent_and_cannot_be_cross_used(state):
    runtime = LocalRunLeaseStore(state)
    core = LocalRunLeaseStore(state, lease_key="component:core:sofia")

    runtime_lease = runtime.acquire(owner_id="watchdog", now=START).lease
    core_lease = core.acquire(owner_id="platform", now=START).lease

    assert runtime_lease is not None and core_lease is not None
    assert runtime_lease.lease_key == "runtime"
    assert core_lease.lease_key == "component:core:sofia"
    assert runtime.holds(runtime_lease, now=START + timedelta(seconds=1))
    assert core.holds(core_lease, now=START + timedelta(seconds=1))
    assert not runtime.holds(core_lease, now=START + timedelta(seconds=1))
    assert not core.holds(runtime_lease, now=START + timedelta(seconds=1))
    assert [event[0] for event in runtime.events()] == ["acquired"]
    assert [event[0] for event in core.events()] == ["acquired"]


def test_existing_unscoped_event_table_migrates_without_losing_audit(state):
    with sqlite3.connect(state) as db:
        db.execute(
            """CREATE TABLE run_local_lease_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL, owner_id TEXT NOT NULL,
            epoch INTEGER NOT NULL, occurred_at TEXT NOT NULL,
            detail TEXT NOT NULL)"""
        )
        db.execute(
            "INSERT INTO run_local_lease_events "
            "(event_type,owner_id,epoch,occurred_at,detail) VALUES (?,?,?,?,?)",
            ("acquired", "legacy", 1, START.isoformat(), "legacy event"),
        )

    runtime = LocalRunLeaseStore(state)
    assert runtime.events() == (
        ("acquired", "legacy", 1, START.isoformat(), "legacy event"),
    )
    assert LocalRunLeaseStore(
        state, lease_key="component:core:sofia"
    ).events() == ()


@pytest.mark.parametrize("ttl", [0, 4, 301, True])
def test_invalid_ttl_rejected(state, ttl):
    store = LocalRunLeaseStore(state)
    with pytest.raises(ValueError):
        store.acquire(owner_id="a", now=START, ttl_seconds=ttl)


def test_existing_state_database_is_required(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalRunLeaseStore(tmp_path / "missing.db")
