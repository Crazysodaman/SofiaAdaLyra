"""Stable host process controller for an active Sofía release."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
import uuid

from sofia.run.active_release import PreparedReleaseEnvironment


class ReleaseProcessError(RuntimeError):
    pass


@dataclass(slots=True)
class ReleaseChildProcess:
    environment: PreparedReleaseEnvironment
    state_path: Path
    control_root: Path
    process: subprocess.Popen | None = None
    ready_file: Path | None = None
    stop_file: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    _stdout_handle: object | None = None
    _stderr_handle: object | None = None

    def start(self, *, ready_timeout_seconds: float = 90.0) -> None:
        if self.process is not None:
            raise ReleaseProcessError("release child is already started")
        if ready_timeout_seconds < 5 or ready_timeout_seconds > 300:
            raise ValueError("ready timeout must be in 5..300 seconds")

        token = uuid.uuid4().hex
        self.control_root.mkdir(parents=True, exist_ok=True)
        self.ready_file = self.control_root / f"{token}.ready.json"
        self.stop_file = self.control_root / f"{token}.stop"
        logs = self.control_root.parent / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.stdout_path = logs / (
            f"{self.environment.release.release_id}.{token}.stdout.log"
        )
        self.stderr_path = logs / (
            f"{self.environment.release.release_id}.{token}.stderr.log"
        )
        self._stdout_handle = self.stdout_path.open("ab")
        self._stderr_handle = self.stderr_path.open("ab")
        self.process = subprocess.Popen(
            [
                str(self.environment.python_path),
                "-m",
                "sofia.run.runtime_child",
                "--state-path",
                str(self.state_path),
                "--ready-file",
                str(self.ready_file),
                "--stop-file",
                str(self.stop_file),
            ],
            stdin=subprocess.DEVNULL,
            stdout=self._stdout_handle,
            stderr=self._stderr_handle,
        )
        deadline = time.monotonic() + ready_timeout_seconds
        while time.monotonic() < deadline:
            if self.ready_file.is_file():
                return
            code = self.process.poll()
            if code is not None:
                raise ReleaseProcessError(
                    f"release child exited before readiness with code {code}"
                )
            time.sleep(0.25)
        self.stop()
        raise ReleaseProcessError(
            "release child did not report readiness before timeout"
        )

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self, *, timeout_seconds: float = 30.0) -> None:
        process = self.process
        if process is None:
            self._close_logs()
            return
        if self.stop_file is not None:
            self.stop_file.parent.mkdir(parents=True, exist_ok=True)
            self.stop_file.touch(exist_ok=True)
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        finally:
            self.process = None
            self._close_logs()

    def _close_logs(self) -> None:
        for name in ("_stdout_handle", "_stderr_handle"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    handle.close()
                finally:
                    setattr(self, name, None)
