"""Stable host process controller for an active Sofía release."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import time
import uuid
from typing import Callable

from sofia.platform.run.active_release import PreparedReleaseEnvironment


class ReleaseProcessError(RuntimeError):
    pass


@dataclass(slots=True)
class ReleaseChildProcess:
    environment: PreparedReleaseEnvironment | None
    state_path: Path
    control_root: Path
    python_path: Path | None = None
    runtime_label: str | None = None
    expected_generation_epoch: int | None = None
    process: subprocess.Popen | None = None
    ready_file: Path | None = None
    stop_file: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    _stdout_handle: object | None = None
    _stderr_handle: object | None = None

    def _identity(self) -> tuple[Path, str]:
        if self.environment is not None:
            if self.python_path is not None or self.runtime_label is not None:
                raise ValueError("release environment cannot use runtime overrides")
            return (
                self.environment.python_path,
                self.environment.release.release_id,
            )
        if self.python_path is None or not self.runtime_label:
            raise ValueError("bootstrap runtime requires python path and label")
        return self.python_path, self.runtime_label

    def start(
        self,
        *,
        ready_timeout_seconds: float = 90.0,
        should_stop: Callable[[], bool] | None = None,
    ) -> bool:
        if self.process is not None:
            raise ReleaseProcessError("release child is already started")
        if ready_timeout_seconds < 5 or ready_timeout_seconds > 300:
            raise ValueError("ready timeout must be in 5..300 seconds")

        if self.expected_generation_epoch is not None and (
            type(self.expected_generation_epoch) is not int
            or self.expected_generation_epoch < 1
        ):
            raise ValueError("expected_generation_epoch must be positive or None")
        python_path, label = self._identity()
        token = uuid.uuid4().hex
        self.control_root.mkdir(parents=True, exist_ok=True)
        self.ready_file = self.control_root / f"{token}.ready.json"
        self.stop_file = self.control_root / f"{token}.stop"
        logs = self.control_root.parent / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.stdout_path = logs / (
            f"{label}.{token}.stdout.log"
        )
        self.stderr_path = logs / (
            f"{label}.{token}.stderr.log"
        )
        self._stdout_handle = self.stdout_path.open("ab")
        self._stderr_handle = self.stderr_path.open("ab")
        # A per-launch token binds readiness to this exact process attempt,
        # independent of any previous ready marker or reused OS PID.
        try:
            command = [
                str(python_path),
                "-m",
                "sofia.platform.run.runtime_child",
                "--state-path", str(self.state_path),
                "--ready-file", str(self.ready_file),
                "--stop-file", str(self.stop_file),
                "--start-token", token,
            ]
            if self.expected_generation_epoch is not None:
                command.extend((
                    "--expected-generation-epoch",
                    str(self.expected_generation_epoch),
                ))
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=self._stdout_handle,
                stderr=self._stderr_handle,
            )
            deadline = time.monotonic() + ready_timeout_seconds
            while time.monotonic() < deadline:
                if should_stop is not None and should_stop():
                    self.stop()
                    return False
                code = self.process.poll()
                if code is not None:
                    raise ReleaseProcessError(
                        f"release child exited before readiness with code {code}"
                    )
                if self.ready_file.is_file():
                    try:
                        marker = json.loads(
                            self.ready_file.read_text(encoding="utf-8")
                        )
                    except (OSError, ValueError, UnicodeError) as exc:
                        raise ReleaseProcessError(
                            "release child readiness is invalid"
                        ) from exc
                    required = {
                        "pid", "ready_at", "state_path", "start_token",
                        "generation_epoch",
                    }
                    if (
                        not isinstance(marker, dict)
                        or set(marker) != required
                        or type(marker["pid"]) is not int
                        or marker["pid"] != self.process.pid
                        or marker["state_path"] != str(self.state_path.resolve())
                        or marker["start_token"] != token
                        or marker["generation_epoch"] != self.expected_generation_epoch
                        or type(marker["ready_at"]) is not str
                        or not marker["ready_at"].strip()
                    ):
                        raise ReleaseProcessError(
                            "release child readiness identity or generation mismatch"
                        )
                    # Do not advertise READY based on a dead child that left
                    # an otherwise valid marker at process exit.
                    if self.process.poll() is not None:
                        raise ReleaseProcessError(
                            "release child exited during readiness validation"
                        )
                    return True
                time.sleep(0.25)
            raise ReleaseProcessError(
                "release child did not report readiness before timeout"
            )
        except BaseException as exc:
            try:
                self.stop()
            except Exception as cleanup_exc:
                exc.add_note(
                    "release child cleanup failed: "
                    f"{type(cleanup_exc).__name__}"
                )
            raise

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
            # A timed-out or unverified forced kill must retain its process
            # identity: never claim a clean stop while the child may be alive.
            if process.poll() is not None:
                self.process = None
            self._close_logs()
        if self.process is not None:
            raise ReleaseProcessError(
                "release child exit could not be verified"
            )

    def _close_logs(self) -> None:
        for name in ("_stdout_handle", "_stderr_handle"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    handle.close()
                finally:
                    setattr(self, name, None)
