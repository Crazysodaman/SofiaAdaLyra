from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run.health import RunHeartbeatStore
from sofia.run.lifecycle import RunLifecycleStore
from sofia.run.watchdog import (
    HostServiceController,
    HostServiceObservation,
    HostServiceState,
    IndependentRunWatchdog,
    WatchdogPolicy,
)


T0 = datetime(2026, 9, 26, 23, 0, tzinfo=timezone.utc)


class FakeController(HostServiceController):
    def __init__(self, state=HostServiceState.RUNNING):
        self.state = state
        self.starts = 0
        self.restarts = 0
        self.stops = 0

    def observe(self):
        return HostServiceObservation(self.state)

    def start(self):
        self.starts += 1
        self.state = HostServiceState.START_PENDING

    def restart(self):
        self.restarts += 1
        self.state = HostServiceState.START_PENDING

    def stop(self):
        self.stops += 1
        self.state = HostServiceState.STOP_PENDING


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    lifecycle = RunLifecycleStore(path)
    heartbeat = RunHeartbeatStore(path)
    return path, lifecycle, heartbeat


def make_watchdog(path, lifecycle, heartbeat, controller, **policy):
    return IndependentRunWatchdog(
        state_path=path,
        lifecycle_store=lifecycle,
        heartbeat_store=heartbeat,
        controller=controller,
        policy=WatchdogPolicy(**policy),
    )


def make_ready(lifecycle, heartbeat):
    lifecycle.begin_start(at=T0)
    lifecycle.mark_recovering(at=T0 + timedelta(seconds=1))
    ready = lifecycle.mark_ready(at=T0 + timedelta(seconds=2))
    heartbeat.begin(
        session_id="session-1",
        process_id=123,
        at=T0 + timedelta(seconds=2),
        lifecycle=ready,
    )
    return ready


def test_fresh_healthy_service_is_left_alone(setup):
    path, lifecycle, heartbeat = setup
    make_ready(lifecycle, heartbeat)
    controller = FakeController()
    watchdog = make_watchdog(path, lifecycle, heartbeat, controller)

    result = watchdog.reconcile(now=T0 + timedelta(seconds=10))

    assert result.action == "healthy"
    assert controller.restarts == 0


def test_stale_running_service_is_restarted(setup):
    path, lifecycle, heartbeat = setup
    make_ready(lifecycle, heartbeat)
    controller = FakeController()
    watchdog = make_watchdog(path, lifecycle, heartbeat, controller)

    result = watchdog.reconcile(now=T0 + timedelta(seconds=40))

    assert result.action == "restarted"
    assert controller.restarts == 1


def test_stopped_desired_service_is_started(setup):
    path, lifecycle, heartbeat = setup
    controller = FakeController(HostServiceState.STOPPED)
    watchdog = make_watchdog(path, lifecycle, heartbeat, controller)

    result = watchdog.reconcile(now=T0)

    assert result.action == "started"
    assert controller.starts == 1


def test_unknown_service_state_fails_closed(setup):
    path, lifecycle, heartbeat = setup
    controller = FakeController(HostServiceState.UNKNOWN)
    watchdog = make_watchdog(path, lifecycle, heartbeat, controller)

    result = watchdog.reconcile(now=T0)

    assert result.action == "unknown_service"
    assert controller.starts == 0
    assert controller.restarts == 0


def test_fenced_lifecycle_stops_running_service(setup):
    path, lifecycle, heartbeat = setup
    lifecycle.mark_fenced(
        at=T0,
        detail="lost authority",
        owner_id="host-a",
        epoch=2,
    )
    controller = FakeController()
    watchdog = make_watchdog(path, lifecycle, heartbeat, controller)

    result = watchdog.reconcile(now=T0 + timedelta(seconds=1))

    assert result.action == "fenced_stopped"
    assert controller.stops == 1


def test_restart_cooldown_blocks_repeat_recovery(setup):
    path, lifecycle, heartbeat = setup
    make_ready(lifecycle, heartbeat)
    controller = FakeController()
    watchdog = make_watchdog(
        path, lifecycle, heartbeat, controller,
        restart_cooldown=timedelta(seconds=30),
    )

    assert watchdog.reconcile(now=T0 + timedelta(seconds=40)).action == "restarted"
    controller.state = HostServiceState.RUNNING
    second = watchdog.reconcile(now=T0 + timedelta(seconds=50))

    assert second.action == "recovery_blocked"
    assert controller.restarts == 1


def test_restart_window_limit_requires_operator_review(setup):
    path, lifecycle, heartbeat = setup
    make_ready(lifecycle, heartbeat)
    controller = FakeController()
    watchdog = make_watchdog(
        path, lifecycle, heartbeat, controller,
        restart_cooldown=timedelta(seconds=1),
        restart_window=timedelta(minutes=10),
        max_restarts_in_window=2,
    )

    assert watchdog.reconcile(now=T0 + timedelta(seconds=40)).action == "restarted"
    controller.state = HostServiceState.RUNNING
    assert watchdog.reconcile(now=T0 + timedelta(seconds=42)).action == "restarted"
    controller.state = HostServiceState.RUNNING
    third = watchdog.reconcile(now=T0 + timedelta(seconds=44))

    assert third.action == "recovery_blocked"
    assert "limit" in third.detail
    assert controller.restarts == 2
