import pytest

from sofia.run.release_rollout import (
    ReleaseRolloutCoordinator,
    ReleaseRolloutError,
    ReleaseRolloutJournal,
    ReleaseRolloutTarget,
    RolloutRing,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


class FakeOperator:
    def __init__(self, *, fail_activate=None, unhealthy_host=None):
        self.current_state = {
            "canary": {
                "active": True,
                "release_id": "old",
                "manifest_sha256": "0" * 64,
            },
            "normal": {
                "active": True,
                "release_id": "old",
                "manifest_sha256": "0" * 64,
            },
            "delayed": {
                "active": True,
                "release_id": "old",
                "manifest_sha256": "0" * 64,
            },
        }
        self.previous = {
            host: dict(value)
            for host, value in self.current_state.items()
        }
        self.calls = []
        self.fail_activate = fail_activate
        self.unhealthy_host = unhealthy_host

    def stage(self, host_id, release_id, manifest_sha256):
        self.calls.append(("stage", host_id))
        return {"staged": True}

    def activate(self, host_id, release_id, manifest_sha256):
        self.calls.append(("activate", host_id))
        if host_id == self.fail_activate:
            raise RuntimeError("activation failed")
        self.previous[host_id] = dict(self.current_state[host_id])
        self.current_state[host_id] = {
            "active": True,
            "release_id": release_id,
            "manifest_sha256": manifest_sha256,
        }
        return dict(self.current_state[host_id])

    def current(self, host_id):
        self.calls.append(("current", host_id))
        return dict(self.current_state[host_id])

    def restart_runtime(self, host_id):
        self.calls.append(("restart", host_id))
        return {"outcome": "reported_success"}

    def runtime_healthy(self, host_id):
        self.calls.append(("health", host_id))
        return host_id != self.unhealthy_host

    def rollback(self, host_id, failed_release_id, reason):
        self.calls.append(("rollback", host_id))
        self.current_state[host_id] = dict(self.previous[host_id])
        return dict(self.current_state[host_id])


def targets():
    return (
        ReleaseRolloutTarget("canary", RolloutRing.CANARY),
        ReleaseRolloutTarget("normal", RolloutRing.NORMAL),
        ReleaseRolloutTarget("delayed", RolloutRing.DELAYED),
    )


def test_rollout_runs_canary_normal_delayed_then_converges(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    operator = FakeOperator()
    coordinator = ReleaseRolloutCoordinator(
        state_plane=plane,
        operator=operator,
        health_interval_seconds=0,
    )

    result = coordinator.rollout(
        rollout_id="rollout-1",
        release_id="new",
        manifest_sha256="a" * 64,
        targets=targets(),
    )

    assert result.status == "completed"
    activation_order = [
        host for action, host in operator.calls if action == "activate"
    ]
    assert activation_order == ["canary", "normal", "delayed"]
    assert all(
        state["release_id"] == "new"
        for state in operator.current_state.values()
    )
    assert (
        ReleaseRolloutJournal(plane).get("rollout-1")["status"]
        == "completed"
    )


def test_wave_failure_stops_later_wave_and_rolls_back_activated_hosts(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    operator = FakeOperator(fail_activate="normal")
    coordinator = ReleaseRolloutCoordinator(
        state_plane=plane,
        operator=operator,
        health_interval_seconds=0,
    )

    with pytest.raises(ReleaseRolloutError):
        coordinator.rollout(
            rollout_id="rollout-2",
            release_id="new",
            manifest_sha256="b" * 64,
            targets=targets(),
        )

    assert ("activate", "delayed") not in operator.calls
    assert operator.current_state["canary"]["release_id"] == "old"
    journal = ReleaseRolloutJournal(plane).get("rollout-2")
    assert journal["status"] == "rolled_back"


def test_multi_host_rollout_requires_canary(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    coordinator = ReleaseRolloutCoordinator(
        state_plane=plane,
        operator=FakeOperator(),
        health_interval_seconds=0,
    )
    with pytest.raises(ValueError, match="canary"):
        coordinator.rollout(
            rollout_id="rollout-3",
            release_id="new",
            manifest_sha256="c" * 64,
            targets=(
                ReleaseRolloutTarget("normal", RolloutRing.NORMAL),
                ReleaseRolloutTarget("delayed", RolloutRing.DELAYED),
            ),
        )


def test_unhealthy_canary_rolls_back_and_stops_later_waves(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    operator = FakeOperator(unhealthy_host="canary")
    coordinator = ReleaseRolloutCoordinator(
        state_plane=plane,
        operator=operator,
        health_attempts=2,
        health_interval_seconds=0,
    )

    with pytest.raises(ReleaseRolloutError, match="runtime did not become healthy"):
        coordinator.rollout(
            rollout_id="rollout-4",
            release_id="new",
            manifest_sha256="d" * 64,
            targets=targets(),
        )

    assert ("activate", "normal") not in operator.calls
    assert ("activate", "delayed") not in operator.calls
    assert ("rollback", "canary") in operator.calls
    assert operator.current_state["canary"]["release_id"] == "old"
