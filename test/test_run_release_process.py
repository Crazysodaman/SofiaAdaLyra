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
