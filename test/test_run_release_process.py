from pathlib import Path

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
