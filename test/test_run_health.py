from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run.health import RunHealthState, RunHeartbeatStore
from sofia.run.lifecycle import RunLifecycleState, RunLifecycleStore


T0 = datetime(2026, 9, 26, 22, 0, tzinfo=timezone.utc)


@pytest.fixture
def stores(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    lifecycle = RunLifecycleStore(path)
    heartbeat = RunHeartbeatStore(path)
    return path, lifecycle, heartbeat


def ready(lifecycle):
    lifecycle.begin_start(at=T0)
    lifecycle.mark_recovering(at=T0 + timedelta(seconds=1))
    return lifecycle.mark_ready(at=T0 + timedelta(seconds=2))


def test_fresh_ready_heartbeat_is_alive_ready_and_healthy(stores):
    _path, lifecycle, heartbeat = stores
    snapshot = ready(lifecycle)
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=2),
        lifecycle=snapshot,
    )

    health = heartbeat.assess(now=T0 + timedelta(seconds=10))

    assert health.state is RunHealthState.HEALTHY
    assert health.alive is True
    assert health.ready is True
    assert health.healthy is True
    assert health.degraded is False


def test_degraded_is_ready_but_not_healthy(stores):
    _path, lifecycle, heartbeat = stores
    ready(lifecycle)
    degraded = lifecycle.mark_degraded(
        at=T0 + timedelta(seconds=3),
        detail="provider unavailable",
    )
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=3),
        lifecycle=degraded,
    )

    health = heartbeat.assess(now=T0 + timedelta(seconds=4))

    assert health.state is RunHealthState.DEGRADED
    assert health.alive and health.ready and health.degraded
    assert health.healthy is False


def test_stale_heartbeat_is_not_alive_even_if_last_lifecycle_was_ready(stores):
    _path, lifecycle, heartbeat = stores
    snapshot = ready(lifecycle)
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=2),
        lifecycle=snapshot,
    )

    health = heartbeat.assess(
        now=T0 + timedelta(seconds=40),
        stale_after=timedelta(seconds=30),
    )

    assert health.state is RunHealthState.STALE
    assert health.alive is False
    assert health.ready is False


def test_new_session_fences_old_writer(stores):
    _path, lifecycle, heartbeat = stores
    snapshot = ready(lifecycle)
    heartbeat.begin(
        session_id="old",
        process_id=111,
        at=T0 + timedelta(seconds=2),
        lifecycle=snapshot,
    )
    heartbeat.begin(
        session_id="new",
        process_id=222,
        at=T0 + timedelta(seconds=3),
        lifecycle=snapshot,
    )

    with pytest.raises(RuntimeError, match="stale"):
        heartbeat.pulse(
            session_id="old",
            process_id=111,
            at=T0 + timedelta(seconds=4),
            lifecycle=snapshot,
        )

    current = heartbeat.current()
    assert current is not None
    assert current.session_id == "new"


def test_lifecycle_generation_cannot_regress(stores):
    _path, lifecycle, heartbeat = stores
    starting = lifecycle.begin_start(at=T0)
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0,
        lifecycle=starting,
    )
    recovering = lifecycle.mark_recovering(at=T0 + timedelta(seconds=1))
    heartbeat.pulse(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=1),
        lifecycle=recovering,
    )

    with pytest.raises(RuntimeError, match="regressed"):
        heartbeat.pulse(
            session_id="session-1",
            process_id=123,
            at=T0 + timedelta(seconds=2),
            lifecycle=starting,
        )


def test_closed_session_reports_stopped_and_refuses_more_pulses(stores):
    _path, lifecycle, heartbeat = stores
    snapshot = ready(lifecycle)
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=2),
        lifecycle=snapshot,
    )
    lifecycle.begin_drain(at=T0 + timedelta(seconds=3))
    lifecycle.begin_stop(at=T0 + timedelta(seconds=4))
    stopped = lifecycle.mark_stopped(at=T0 + timedelta(seconds=5))
    heartbeat.close(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=5),
        lifecycle=stopped,
    )

    health = heartbeat.assess(now=T0 + timedelta(seconds=6))

    assert health.state is RunHealthState.STOPPED
    assert health.alive is False
    with pytest.raises(RuntimeError, match="stale or closed"):
        heartbeat.pulse(
            session_id="session-1",
            process_id=123,
            at=T0 + timedelta(seconds=7),
            lifecycle=stopped,
        )
