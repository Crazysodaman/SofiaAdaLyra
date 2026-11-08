from pathlib import Path
import json

import pytest

import sofia.platform.run.release_process as release_process
from sofia.platform.run.release_process import ReleaseChildProcess


class _BlockedProcess:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.returncode = None
        self.waits = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waits.append(timeout)
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class _UnresponsiveProcess(_BlockedProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.terminated = 0
        self.killed = 0

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.killed:
            self.returncode = -9
            return -9
        raise release_process.subprocess.TimeoutExpired("runtime-child", timeout)

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1


def test_service_stop_interrupts_child_readiness_wait(tmp_path, monkeypatch):
    processes = []

    def popen(*args, **kwargs):
        process = _BlockedProcess(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(release_process.subprocess, "Popen", popen)
    child = ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "sofia.db",
        control_root=tmp_path / "control",
        python_path=Path("python.exe"),
        runtime_label="bootstrap",
    )

    assert child.start(should_stop=lambda: True) is False
    assert len(processes) == 1
    assert processes[0].waits == [30.0]
    assert child.process is None


def test_bootstrap_child_requires_explicit_interpreter_and_label(tmp_path):
    child = ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "sofia.db",
        control_root=tmp_path / "control",
    )

    with pytest.raises(ValueError, match="python path and label"):
        child.start()


def test_nonresponsive_child_is_terminated_then_killed(tmp_path):
    child = ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "sofia.db",
        control_root=tmp_path / "control",
        python_path=Path("python.exe"),
        runtime_label="bootstrap",
    )
    process = _UnresponsiveProcess()
    child.process = process
    child.stop_file = tmp_path / "control" / "runtime.stop"

    child.stop(timeout_seconds=5)

    assert child.stop_file.is_file()
    assert process.waits == [5, 10, 10]
    assert process.terminated == 1
    assert process.killed == 1
    assert child.process is None


def test_child_crash_before_readiness_is_rejected(tmp_path, monkeypatch):
    process = _BlockedProcess()
    process.returncode = 23
    monkeypatch.setattr(
        release_process.subprocess, "Popen", lambda *args, **kwargs: process,
    )
    child = ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "sofia.db",
        control_root=tmp_path / "control",
        python_path=Path("python.exe"),
        runtime_label="bootstrap",
    )

    with pytest.raises(
        release_process.ReleaseProcessError,
        match="exited before readiness with code 23",
    ):
        child.start()


def test_frozen_startup_times_out_and_stops_child(tmp_path, monkeypatch):
    process = _BlockedProcess()
    monkeypatch.setattr(
        release_process.subprocess, "Popen", lambda *args, **kwargs: process,
    )
    moments = iter((0.0, 6.0))
    monkeypatch.setattr(release_process.time, "monotonic", lambda: next(moments))
    child = ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "sofia.db",
        control_root=tmp_path / "control",
        python_path=Path("python.exe"),
        runtime_label="bootstrap",
    )

    with pytest.raises(
        release_process.ReleaseProcessError,
        match="did not report readiness before timeout",
    ):
        child.start(ready_timeout_seconds=5)
    assert process.waits == [30.0]
    assert child.process is None


# CORE-001: synthetic readiness and cleanup regressions. No actual Core or
# production SQLite is created or contacted by these tests.
class _CORE001MarkerProcess(_BlockedProcess):
    pid = 14591


def _core001_child(tmp_path, *, epoch=None):
    return ReleaseChildProcess(
        environment=None,
        state_path=tmp_path / "disposable-state.db",
        control_root=tmp_path / "control",
        python_path=Path("python.exe"),
        runtime_label="disposable",
        expected_generation_epoch=epoch,
    )


def _core001_marker_spawn(tmp_path, monkeypatch, *, mode, epoch=7):
    process = _CORE001MarkerProcess()

    def popen(args, **kwargs):
        marker = Path(args[args.index("--ready-file") + 1])
        state_path = Path(args[args.index("--state-path") + 1])
        token = args[args.index("--start-token") + 1]
        generation = (
            int(args[args.index("--expected-generation-epoch") + 1])
            if "--expected-generation-epoch" in args else None
        )
        record = {
            "pid": process.pid,
            "ready_at": "2026-11-08T09:35:00+00:00",
            "state_path": str(state_path.resolve()),
            "start_token": token,
            "phase": "PROCESS_READY",
            "generation_epoch": generation,
        }
        if mode == "dead":
            process.returncode = 42
        elif mode == "wrong-pid":
            record["pid"] += 1
        elif mode == "wrong-state":
            record["state_path"] = str(tmp_path / "elsewhere.db")
        elif mode == "stale-attempt":
            record["start_token"] = "f" * 32 if token != "f" * 32 else "e" * 32
        elif mode == "wrong-generation":
            record["generation_epoch"] = generation + 1
        elif mode == "missing-field":
            record.pop("start_token")
        elif mode == "malformed-json":
            marker.write_text("not-json", encoding="utf-8")
            return process
        elif mode == "dead-during-validation":
            polls = [None, 42]
            process.poll = lambda: polls.pop(0) if polls else 42
        marker.write_text(json.dumps(record), encoding="utf-8")
        return process

    monkeypatch.setattr(release_process.subprocess, "Popen", popen)
    return process


def test_core001_valid_marker_matches_live_process_launch_and_epoch(tmp_path, monkeypatch):
    process = _core001_marker_spawn(tmp_path, monkeypatch, mode="valid")
    child = _core001_child(tmp_path, epoch=7)
    assert child.start(ready_timeout_seconds=5) is True
    assert child.running()
    child.stop(timeout_seconds=0.01)
    child.stop(timeout_seconds=0.01)
    assert process.returncode == 0
    assert child.process is None
    assert child._stdout_handle is None and child._stderr_handle is None


@pytest.mark.parametrize(
    "mode",
    [
        "dead",
        "wrong-pid",
        "wrong-state",
        "stale-attempt",
        "wrong-generation",
        "missing-field",
        "malformed-json",
        "dead-during-validation",
    ],
)
def test_core001_never_accepts_dead_stale_or_wrong_generation(
    tmp_path, monkeypatch, mode,
):
    _core001_marker_spawn(tmp_path, monkeypatch, mode=mode)
    child = _core001_child(tmp_path, epoch=7)
    with pytest.raises(release_process.ReleaseProcessError):
        child.start(ready_timeout_seconds=5)
    assert child.process is None
    assert child._stdout_handle is None and child._stderr_handle is None


def test_core001_early_exit_releases_handles_and_permits_restart(tmp_path, monkeypatch):
    first = _CORE001MarkerProcess()
    first.returncode = 23
    monkeypatch.setattr(
        release_process.subprocess, "Popen", lambda *args, **kwargs: first,
    )
    child = _core001_child(tmp_path)
    with pytest.raises(release_process.ReleaseProcessError, match="exited before readiness"):
        child.start(ready_timeout_seconds=5)
    assert child.process is None
    assert child._stdout_handle is None and child._stderr_handle is None

    _core001_marker_spawn(tmp_path, monkeypatch, mode="valid", epoch=None)
    assert child.start(ready_timeout_seconds=5)
    child.stop(timeout_seconds=0.01)
    assert child.process is None


def test_core001_failed_spawn_releases_log_handles(tmp_path, monkeypatch):
    def denied_spawn(*args, **kwargs):
        raise OSError("disposable spawn rejected")

    monkeypatch.setattr(release_process.subprocess, "Popen", denied_spawn)
    child = _core001_child(tmp_path)
    with pytest.raises(OSError, match="disposable spawn rejected"):
        child.start(ready_timeout_seconds=5)
    assert child.process is None
    assert child._stdout_handle is None and child._stderr_handle is None


def test_core001_unverified_forced_kill_retains_process_identity(tmp_path):
    class Unkillable:
        returncode = None
        def __init__(self):
            self.calls = []
        def poll(self):
            return self.returncode
        def wait(self, timeout=None):
            self.calls.append(("wait", timeout))
            if self.returncode is not None:
                return self.returncode
            raise release_process.subprocess.TimeoutExpired("synthetic-child", timeout)
        def terminate(self):
            self.calls.append(("terminate",))
        def kill(self):
            self.calls.append(("kill",))

    child = _core001_child(tmp_path)
    process = Unkillable()
    child.process = process
    child.stop_file = tmp_path / "control" / "synthetic.stop"
    with pytest.raises(release_process.subprocess.TimeoutExpired):
        child.stop(timeout_seconds=0.01)
    assert child.process is process
    assert child.stop_file.is_file()
    assert ("terminate",) in process.calls and ("kill",) in process.calls
    # An independently verified late exit makes a later idempotent stop safe.
    process.returncode = -9
    child.stop(timeout_seconds=0.01)
    assert child.process is None
