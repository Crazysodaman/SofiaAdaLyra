"""Supervised synthetic Core process backend.

The backend launches a caller-supplied synthetic Core entrypoint from an
explicit argv list. It never uses a shell, exposes only an allowlisted
environment, bounds the working directory beneath a caller-supplied root and
integrity-checks the entrypoint bytes before every launch.

This module deliberately has no knowledge of the real Sofía Core, personal
memory or production credentials. It implements the narrow
:class:`~sofia.platform.ops.synthetic_core_lifecycle.SyntheticCoreProcessBackend`
protocol so the lifecycle state machine can supervise a disposable process.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from threading import RLock
from typing import Mapping, Sequence

from sofia.platform.ops.synthetic_core_lifecycle import CoreProcessObservation
from sofia.platform.state.private_file import assert_no_redirected_components

_SHA256 = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,199}")
_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,127}")
_SECRET_FRAGMENTS = (
    "SECRET", "TOKEN", "PASSWORD", "PASSWD", "APIKEY", "API_KEY",
    "CREDENTIAL", "PRIVATE", "AUTH",
)
_INHERITED_ENVIRONMENT = frozenset({
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "COMSPEC",
    "OS", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "HOME",
    "LANG", "LC_ALL", "LC_CTYPE",
})

READY_FILE_ENV = "SOFIA_SYNTHETIC_CORE_READY_FILE"
STOP_FILE_ENV = "SOFIA_SYNTHETIC_CORE_STOP_FILE"
GENERATION_ENV = "SOFIA_SYNTHETIC_CORE_GENERATION"


class SyntheticCoreBackendError(RuntimeError):
    """A synthetic Core process could not be launched or observed safely."""


@dataclass(slots=True)
class _ProcessRecord:
    core_id: str
    lineage_id: str
    generation: int
    launcher_pid: int
    pid: int
    process: subprocess.Popen
    control_directory: Path
    started_at: datetime

    @property
    def ready_path(self) -> Path:
        return self.control_directory / "ready.json"

    @property
    def stop_path(self) -> Path:
        return self.control_directory / "stop"


class SyntheticCoreProcessBackend:
    """One-writer supervised process backend for disposable synthetic Cores."""

    def __init__(
        self,
        *,
        argv: Sequence[str],
        entrypoint_path: Path | str,
        entrypoint_sha256: str,
        working_root: Path | str,
        working_directory: Path | str,
        environment: Mapping[str, str] | None = None,
        readiness_timeout: float = 15.0,
        stop_timeout: float = 5.0,
        poll_interval: float = 0.05,
    ) -> None:
        self._argv = self._validate_argv(argv)
        self._entrypoint = self._absolute_path(entrypoint_path, "entrypoint_path")
        assert_no_redirected_components(self._entrypoint, include_leaf=True)
        if not self._entrypoint.is_file():
            raise FileNotFoundError("synthetic Core entrypoint is missing")
        if not isinstance(entrypoint_sha256, str) or _SHA256.fullmatch(
            entrypoint_sha256
        ) is None:
            raise ValueError("entrypoint_sha256 must be a lowercase SHA-256")
        self._entrypoint_sha256 = entrypoint_sha256
        self._verify_entrypoint()

        self._root = self._absolute_path(working_root, "working_root")
        self._root.mkdir(parents=True, exist_ok=True)
        assert_no_redirected_components(self._root, include_leaf=True)
        self._working_directory = self._absolute_path(
            working_directory, "working_directory"
        )
        self._working_directory.mkdir(parents=True, exist_ok=True)
        assert_no_redirected_components(
            self._working_directory, include_leaf=True
        )
        if not self._working_directory.resolve().is_relative_to(
            self._root.resolve()
        ):
            raise ValueError(
                "working_directory must remain beneath working_root"
            )

        self._environment = self._validate_environment(environment or {})
        self.readiness_timeout = self._timeout(readiness_timeout, "readiness_timeout")
        self.stop_timeout = self._timeout(stop_timeout, "stop_timeout")
        if type(poll_interval) not in {int, float} or not (
            0.005 <= poll_interval <= 1.0
        ):
            raise ValueError("poll_interval must be in 0.005..1.0 seconds")
        self.poll_interval = float(poll_interval)
        self._lock = RLock()
        self._running: dict[str, _ProcessRecord] = {}
        self._last_generation: dict[tuple[str, str], int] = {}

    @property
    def working_directory(self) -> Path:
        return self._working_directory

    @staticmethod
    def _absolute_path(value: Path | str, label: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError(f"{label} must be an absolute path")
        return path

    @staticmethod
    def _validate_argv(argv: Sequence[str]) -> tuple[str, ...]:
        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
            raise TypeError("argv must be a sequence of arguments")
        values = tuple(argv)
        if not values or len(values) > 64:
            raise ValueError("argv must contain between 1 and 64 arguments")
        for value in values:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ValueError("argv entries must be non-empty strings")
            if len(value) > 4096:
                raise ValueError("argv entry exceeds the bounded length")
        interpreter = Path(values[0])
        if not interpreter.is_absolute():
            raise ValueError("argv[0] must be an absolute interpreter path")
        if not interpreter.is_file():
            raise FileNotFoundError("argv[0] interpreter is missing")
        return values

    @staticmethod
    def _timeout(value: object, label: str) -> float:
        if type(value) not in {int, float} or not 0.1 <= float(value) <= 300.0:
            raise ValueError(f"{label} must be in 0.1..300 seconds")
        return float(value)

    @staticmethod
    def _validate_environment(environment: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(environment, Mapping):
            raise TypeError("environment must be a mapping")
        validated: dict[str, str] = {}
        for key, value in environment.items():
            if not isinstance(key, str) or _ENV_NAME.fullmatch(key) is None:
                raise ValueError("environment keys must be bounded canonical names")
            upper = key.upper()
            if any(fragment in upper for fragment in _SECRET_FRAGMENTS):
                raise ValueError(
                    "environment overrides must not carry credential-like names"
                )
            if (
                not isinstance(value, str)
                or "\x00" in value
                or len(value) > 4096
            ):
                raise ValueError("environment values must be bounded strings")
            validated[key] = value
        return validated

    def _verify_entrypoint(self) -> None:
        assert_no_redirected_components(self._entrypoint, include_leaf=True)
        if not self._entrypoint.is_file():
            raise SyntheticCoreBackendError(
                "synthetic Core entrypoint disappeared before launch"
            )
        digest = sha256(self._entrypoint.read_bytes()).hexdigest()
        if digest != self._entrypoint_sha256:
            raise SyntheticCoreBackendError(
                "synthetic Core entrypoint failed its integrity check"
            )

    def _child_environment(
        self, *, ready_path: Path, stop_path: Path, generation: int,
    ) -> dict[str, str]:
        child = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in _INHERITED_ENVIRONMENT
        }
        child.update(self._environment)
        child.update({
            READY_FILE_ENV: str(ready_path),
            STOP_FILE_ENV: str(stop_path),
            GENERATION_ENV: str(generation),
        })
        return child

    @staticmethod
    def _require_identifier(value: object, label: str) -> str:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"{label} must be a bounded path-safe identifier")
        return value

    def _record_for(
        self, core_id: str, lineage_id: str, generation: int
    ) -> _ProcessRecord | None:
        record = self._running.get(core_id)
        if record is None:
            return None
        if record.lineage_id != lineage_id or record.generation != generation:
            return None
        return record

    def start(
        self, *, core_id: str, lineage_id: str, generation: int
    ) -> CoreProcessObservation:
        core = self._require_identifier(core_id, "core_id")
        lineage = self._require_identifier(lineage_id, "lineage_id")
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be a positive integer")
        with self._lock:
            existing = self._running.get(core)
            if existing is not None:
                if existing.lineage_id != lineage:
                    raise SyntheticCoreBackendError(
                        "synthetic Core identity changed lineage while running"
                    )
                if existing.process.poll() is None:
                    if existing.generation == generation:
                        return CoreProcessObservation.RUNNING
                    raise SyntheticCoreBackendError(
                        "synthetic Core already has a supervised process"
                    )
                self._forget(existing)
            last = self._last_generation.get((core, lineage), 0)
            if generation <= last:
                raise SyntheticCoreBackendError(
                    "synthetic Core start generation is stale"
                )
            self._verify_entrypoint()
            control = self._working_directory / f"core-{core}-g{generation}"
            control.mkdir(parents=True, exist_ok=True)
            assert_no_redirected_components(control, include_leaf=True)
            ready_path = control / "ready.json"
            stop_path = control / "stop"
            for path in (ready_path, stop_path):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            environment = self._child_environment(
                ready_path=ready_path, stop_path=stop_path,
                generation=generation,
            )
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
            try:
                process = subprocess.Popen(
                    list(self._argv),
                    cwd=str(self._working_directory),
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                    close_fds=True,
                    creationflags=creationflags,
                )
            except OSError as exc:
                raise SyntheticCoreBackendError(
                    "synthetic Core entrypoint could not be spawned"
                ) from exc
            record = _ProcessRecord(
                core_id=core,
                lineage_id=lineage,
                generation=generation,
                launcher_pid=process.pid,
                pid=process.pid,
                process=process,
                control_directory=control,
                started_at=datetime.now(timezone.utc),
            )
            self._running[core] = record
            deadline = time.monotonic() + self.readiness_timeout
            while True:
                code = process.poll()
                if code is not None:
                    self._forget(record)
                    raise SyntheticCoreBackendError(
                        "synthetic Core exited before reporting readiness"
                    )
                if ready_path.is_file():
                    try:
                        value = json.loads(ready_path.read_text("utf-8"))
                    except (OSError, ValueError) as exc:
                        self._force_stop(record)
                        self._forget(record)
                        raise SyntheticCoreBackendError(
                            "synthetic Core readiness evidence is invalid"
                        ) from exc
                    reported_pid = (
                        value.get("pid") if isinstance(value, dict) else None
                    )
                    if (
                        not isinstance(value, dict)
                        or type(reported_pid) is not int
                        or reported_pid < 1
                        or value.get("generation") != generation
                        or value.get("state") != "ready"
                    ):
                        self._force_stop(record)
                        self._forget(record)
                        raise SyntheticCoreBackendError(
                            "synthetic Core readiness identity mismatch"
                        )
                    record.pid = reported_pid
                    self._last_generation[(core, lineage)] = generation
                    return CoreProcessObservation.RUNNING
                if time.monotonic() >= deadline:
                    self._force_stop(record)
                    self._forget(record)
                    raise SyntheticCoreBackendError(
                        "synthetic Core readiness deadline expired"
                    )
                time.sleep(self.poll_interval)

    def observe(
        self, *, core_id: str, lineage_id: str, generation: int
    ) -> CoreProcessObservation:
        core = self._require_identifier(core_id, "core_id")
        lineage = self._require_identifier(lineage_id, "lineage_id")
        with self._lock:
            record = self._record_for(core, lineage, generation)
            if record is None:
                return CoreProcessObservation.STOPPED
            if record.process.poll() is None:
                return CoreProcessObservation.RUNNING
            self._forget(record)
            return CoreProcessObservation.STOPPED

    def stop(
        self, *, core_id: str, lineage_id: str, generation: int
    ) -> CoreProcessObservation:
        core = self._require_identifier(core_id, "core_id")
        lineage = self._require_identifier(lineage_id, "lineage_id")
        with self._lock:
            record = self._record_for(core, lineage, generation)
            if record is None:
                return CoreProcessObservation.STOPPED
            if record.process.poll() is not None:
                self._forget(record)
                return CoreProcessObservation.STOPPED
            try:
                record.stop_path.write_text("stop\n", encoding="utf-8")
            except OSError:
                pass
            self._signal_stop(record)
            deadline = time.monotonic() + self.stop_timeout
            while record.process.poll() is None and time.monotonic() < deadline:
                time.sleep(self.poll_interval)
            if record.process.poll() is None:
                record.process.terminate()
                try:
                    record.process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    record.process.kill()
                    try:
                        record.process.wait(timeout=self.stop_timeout)
                    except subprocess.TimeoutExpired:
                        return CoreProcessObservation.UNKNOWN
            self._forget(record)
            return CoreProcessObservation.STOPPED

    def pid_for(self, core_id: str) -> int | None:
        with self._lock:
            record = self._running.get(core_id)
            return None if record is None else record.pid

    def generation_for(self, core_id: str) -> int | None:
        with self._lock:
            record = self._running.get(core_id)
            return None if record is None else record.generation

    def running_pids(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(
                record.pid
                for record in self._running.values()
                if record.process.poll() is None
            )

    def close(self) -> None:
        with self._lock:
            records = tuple(self._running.values())
        for record in records:
            try:
                self.stop(
                    core_id=record.core_id,
                    lineage_id=record.lineage_id,
                    generation=record.generation,
                )
            except Exception:
                try:
                    self._force_stop(record)
                except Exception:
                    pass
                self._forget(record)

    def _force_stop(self, record: _ProcessRecord) -> None:
        if record.process.poll() is not None:
            return
        record.process.terminate()
        try:
            record.process.wait(timeout=self.stop_timeout)
        except subprocess.TimeoutExpired:
            record.process.kill()
            try:
                record.process.wait(timeout=self.stop_timeout)
            except subprocess.TimeoutExpired:
                pass

    @staticmethod
    def _signal_stop(record: _ProcessRecord) -> None:
        if os.name == "nt":
            target = getattr(signal, "CTRL_BREAK_EVENT", None)
        else:
            target = signal.SIGTERM
        if target is None:
            return
        try:
            record.process.send_signal(target)
        except (OSError, ValueError):
            pass

    def _forget(self, record: _ProcessRecord) -> None:
        with self._lock:
            current = self._running.get(record.core_id)
            if current is record:
                self._running.pop(record.core_id, None)
        for path in (record.ready_path, record.stop_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


__all__ = [
    "SyntheticCoreBackendError",
    "SyntheticCoreProcessBackend",
]
