from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run.lifecycle import RunLifecycleState, RunLifecycleStore


T0 = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved (value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('yes')")
    return path


def test_initial_state_is_stopped_without_activity(state):
    store = RunLifecycleStore(state)
    current = store.current()

    assert current.state is RunLifecycleState.STOPPED
    assert current.generation == 0
    assert store.events() == ()


def test_clean_start_recovery_ready_shutdown_sequence(state):
    store = RunLifecycleStore(state)

    assert store.begin_start(at=T0).state is RunLifecycleState.STARTING
    assert store.mark_recovering(at=T0 + timedelta(seconds=1)).state is RunLifecycleState.RECOVERING
    assert store.mark_ready(at=T0 + timedelta(seconds=2)).state is RunLifecycleState.READY
    assert store.begin_drain(at=T0 + timedelta(seconds=3)).state is RunLifecycleState.DRAINING
    assert store.begin_stop(at=T0 + timedelta(seconds=4)).state is RunLifecycleState.STOPPING
    stopped = store.mark_stopped(at=T0 + timedelta(seconds=5))

    assert stopped.state is RunLifecycleState.STOPPED
    assert stopped.generation == 6
    assert len(store.events()) == 6


@pytest.mark.parametrize(
    "prior",
    [
        RunLifecycleState.STARTING,
        RunLifecycleState.RECOVERING,
        RunLifecycleState.READY,
        RunLifecycleState.DEGRADED,
        RunLifecycleState.DRAINING,
        RunLifecycleState.STOPPING,
    ],
)
def test_begin_start_detects_unclean_prior_state(state, prior):
    store = RunLifecycleStore(state)
    if prior is RunLifecycleState.STARTING:
        store.begin_start(at=T0)
    else:
        store.begin_start(at=T0)
        if prior is RunLifecycleState.RECOVERING:
            store.mark_recovering(at=T0 + timedelta(seconds=1))
        elif prior is RunLifecycleState.READY:
            store.mark_ready(at=T0 + timedelta(seconds=1))
        elif prior is RunLifecycleState.DEGRADED:
            store.mark_degraded(at=T0 + timedelta(seconds=1), detail="provider offline")
        elif prior is RunLifecycleState.DRAINING:
            store.mark_ready(at=T0 + timedelta(seconds=1))
            store.begin_drain(at=T0 + timedelta(seconds=2))
        elif prior is RunLifecycleState.STOPPING:
            store.begin_stop(at=T0 + timedelta(seconds=1))

    recovered = store.begin_start(at=T0 + timedelta(minutes=1))

    assert recovered.state is RunLifecycleState.RECOVERING
    assert "unclean restart" in recovered.detail


def test_illegal_transition_fails_closed(state):
    store = RunLifecycleStore(state)

    with pytest.raises(RuntimeError, match="illegal"):
        store.transition(
            expected=RunLifecycleState.STOPPED,
            target=RunLifecycleState.READY,
            at=T0,
        )

    assert store.current().state is RunLifecycleState.STOPPED


def test_fenced_state_requires_explicit_stop_before_restart(state):
    store = RunLifecycleStore(state)
    store.mark_fenced(at=T0, detail="lost lease", owner_id="host-a", epoch=7)

    with pytest.raises(RuntimeError, match="operator clear"):
        store.begin_start(at=T0 + timedelta(seconds=1))

    stopped = store.mark_stopped(at=T0 + timedelta(seconds=2), detail="operator cleared fence")
    assert stopped.state is RunLifecycleState.STOPPED


def test_authority_metadata_is_all_or_nothing(state):
    store = RunLifecycleStore(state)

    with pytest.raises(ValueError):
        store.transition(
            expected=RunLifecycleState.STOPPED,
            target=RunLifecycleState.FENCED,
            at=T0,
            owner_id="host-a",
        )


def test_unrelated_database_state_is_preserved(state):
    RunLifecycleStore(state).begin_start(at=T0)
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT value FROM preserved").fetchone() == ("yes",)
