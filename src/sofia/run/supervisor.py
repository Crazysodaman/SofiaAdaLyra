"""Host-neutral local runtime supervisor with bounded restart/backoff.

The supervisor owns no OS service installation and no distributed leadership.
A host adapter supplies observed process state plus start/stop operations. The
supervisor may act only while the exact local singleton lease remains valid.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from .lease import LocalRunLeaseStore, RunLease


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


class ProcessState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuntimeObservation:
    state: ProcessState
    ready: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, ProcessState):
            raise TypeError("state must be a ProcessState")
        if not isinstance(self.ready, bool):
            raise TypeError("ready must be boolean")
        if self.ready and self.state is not ProcessState.RUNNING:
            raise ValueError("only a running runtime may be ready")
        if not isinstance(self.detail, str) or len(self.detail) > 500:
            raise ValueError("detail must be bounded text")


class ManagedRuntimeBackend(ABC):
    """Narrow process-control boundary. No shell command is exposed to cognition."""

    @abstractmethod
    def observe(self) -> RuntimeObservation:
        raise NotImplementedError

    @abstractmethod
    def start(self, *, epoch: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class SupervisorPolicy:
    max_restarts_in_window: int = 5
    restart_window: timedelta = timedelta(minutes=10)
    initial_backoff: timedelta = timedelta(seconds=5)
    max_backoff: timedelta = timedelta(minutes=5)
    readiness_grace: timedelta = timedelta(seconds=90)

    def __post_init__(self) -> None:
        if type(self.max_restarts_in_window) is not int or not 1 <= self.max_restarts_in_window <= 50:
            raise ValueError("max_restarts_in_window must be in 1..50")
        for label, value in (
            ("restart_window", self.restart_window),
            ("initial_backoff", self.initial_backoff),
            ("max_backoff", self.max_backoff),
            ("readiness_grace", self.readiness_grace),
        ):
            if not isinstance(value, timedelta) or value <= timedelta(0):
                raise ValueError(f"{label} must be a positive timedelta")
        if self.initial_backoff > self.max_backoff:
            raise ValueError("initial_backoff cannot exceed max_backoff")


@dataclass(frozen=True)
class SupervisorResult:
    action: str
    observation: RuntimeObservation
    backoff_until: datetime | None = None
    detail: str = ""


class LocalRuntimeSupervisor:
    """Deterministic reconcile loop for one locally fenced runtime."""

    def __init__(
        self,
        *,
        state_path: Path,
        lease_store: LocalRunLeaseStore,
        backend: ManagedRuntimeBackend,
        policy: SupervisorPolicy = SupervisorPolicy(),
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        if not state_path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(lease_store, LocalRunLeaseStore):
            raise TypeError("LocalRunLeaseStore required")
        if lease_store.path.resolve() != state_path.resolve():
            raise ValueError("supervisor and lease store must use the same state database")
        if not isinstance(backend, ManagedRuntimeBackend):
            raise TypeError("ManagedRuntimeBackend required")
        if not isinstance(policy, SupervisorPolicy):
            raise TypeError("SupervisorPolicy required")
        self.state_path = state_path
        self.lease_store = lease_store
        self.backend = backend
        self.policy = policy
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS run_supervisor_state (
                        owner_id TEXT PRIMARY KEY,
                        epoch INTEGER NOT NULL,
                        consecutive_failures INTEGER NOT NULL,
                        last_start_at TEXT,
                        backoff_until TEXT,
                        readiness_deadline TEXT,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS run_supervisor_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        occurred_at TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        detail TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS run_supervisor_event_time
                        ON run_supervisor_events(owner_id, epoch, occurred_at);
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        lease: RunLease,
        now: datetime,
        event_type: str,
        detail: str,
    ) -> None:
        db.execute(
            """
            INSERT INTO run_supervisor_events
            (owner_id, epoch, occurred_at, event_type, detail)
            VALUES (?,?,?,?,?)
            """,
            (lease.owner_id, lease.epoch, now.isoformat(), event_type, detail[:500]),
        )

    def _state(self, db: sqlite3.Connection, lease: RunLease, now: datetime) -> dict:
        row = db.execute(
            """
            SELECT epoch, consecutive_failures, last_start_at, backoff_until,
                   readiness_deadline, updated_at
            FROM run_supervisor_state WHERE owner_id=?
            """,
            (lease.owner_id,),
        ).fetchone()
        if row is None or row[0] != lease.epoch:
            db.execute(
                """
                INSERT INTO run_supervisor_state
                (owner_id, epoch, consecutive_failures, last_start_at,
                 backoff_until, readiness_deadline, updated_at)
                VALUES (?,?,0,NULL,NULL,NULL,?)
                ON CONFLICT(owner_id) DO UPDATE SET
                    epoch=excluded.epoch,
                    consecutive_failures=0,
                    last_start_at=NULL,
                    backoff_until=NULL,
                    readiness_deadline=NULL,
                    updated_at=excluded.updated_at
                """,
                (lease.owner_id, lease.epoch, now.isoformat()),
            )
            return {
                "consecutive_failures": 0,
                "last_start_at": None,
                "backoff_until": None,
                "readiness_deadline": None,
            }
        return {
            "consecutive_failures": row[1],
            "last_start_at": (
                datetime.fromisoformat(row[2]).astimezone(timezone.utc)
                if row[2] is not None
                else None
            ),
            "backoff_until": (
                datetime.fromisoformat(row[3]).astimezone(timezone.utc)
                if row[3] is not None
                else None
            ),
            "readiness_deadline": (
                datetime.fromisoformat(row[4]).astimezone(timezone.utc)
                if row[4] is not None
                else None
            ),
        }

    def _write_state(
        self,
        db: sqlite3.Connection,
        lease: RunLease,
        now: datetime,
        *,
        failures: int,
        last_start_at: datetime | None,
        backoff_until: datetime | None,
        readiness_deadline: datetime | None,
    ) -> None:
        db.execute(
            """
            UPDATE run_supervisor_state
            SET consecutive_failures=?, last_start_at=?, backoff_until=?,
                readiness_deadline=?, updated_at=?
            WHERE owner_id=? AND epoch=?
            """,
            (
                failures,
                last_start_at.isoformat() if last_start_at is not None else None,
                backoff_until.isoformat() if backoff_until is not None else None,
                readiness_deadline.isoformat() if readiness_deadline is not None else None,
                now.isoformat(),
                lease.owner_id,
                lease.epoch,
            ),
        )

    def _backoff(self, failures: int) -> timedelta:
        exponent = max(0, failures - 1)
        seconds = self.policy.initial_backoff.total_seconds() * (2 ** exponent)
        return timedelta(
            seconds=min(seconds, self.policy.max_backoff.total_seconds())
        )

    def _restart_count(
        self,
        db: sqlite3.Connection,
        lease: RunLease,
        now: datetime,
    ) -> int:
        cutoff = now - self.policy.restart_window
        return db.execute(
            """
            SELECT COUNT(*) FROM run_supervisor_events
            WHERE owner_id=? AND epoch=? AND event_type='start_requested'
              AND occurred_at>=?
            """,
            (lease.owner_id, lease.epoch, cutoff.isoformat()),
        ).fetchone()[0]

    def reconcile(
        self,
        lease: RunLease,
        *,
        now: datetime,
        desired_running: bool = True,
        stop_requested: bool = False,
    ) -> SupervisorResult:
        if not isinstance(lease, RunLease):
            raise TypeError("RunLease required")
        if not isinstance(desired_running, bool) or not isinstance(stop_requested, bool):
            raise TypeError("desired_running and stop_requested must be booleans")
        moment = _utc(now)
        observation = self.backend.observe()
        if not isinstance(observation, RuntimeObservation):
            raise TypeError("backend.observe must return RuntimeObservation")

        if not self.lease_store.holds(lease, now=moment):
            if observation.state in (ProcessState.RUNNING, ProcessState.STARTING):
                self.backend.stop()
                with closing(self._connect()) as db:
                    with db:
                        self._event(
                            db,
                            lease,
                            moment,
                            "fenced_stop",
                            "runtime stopped because exact local lease was lost",
                        )
                return SupervisorResult(
                    "fenced_stopped",
                    observation,
                    detail="exact local lease is not held",
                )
            return SupervisorResult(
                "no_authority",
                observation,
                detail="exact local lease is not held",
            )

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                state = self._state(db, lease, moment)

                if stop_requested or not desired_running:
                    if observation.state in (ProcessState.RUNNING, ProcessState.STARTING):
                        try:
                            self.backend.stop()
                        except Exception as exc:
                            self._event(
                                db,
                                lease,
                                moment,
                                "stop_failed",
                                type(exc).__name__,
                            )
                            raise
                        self._event(
                            db,
                            lease,
                            moment,
                            "stop_requested",
                            "operator/policy requested runtime stop",
                        )
                        self._write_state(
                            db,
                            lease,
                            moment,
                            failures=0,
                            last_start_at=state["last_start_at"],
                            backoff_until=None,
                            readiness_deadline=None,
                        )
                        return SupervisorResult("stopped", observation)
                    return SupervisorResult("already_stopped", observation)

                if observation.state is ProcessState.RUNNING and observation.ready:
                    self._write_state(
                        db,
                        lease,
                        moment,
                        failures=0,
                        last_start_at=state["last_start_at"],
                        backoff_until=None,
                        readiness_deadline=None,
                    )
                    return SupervisorResult("healthy", observation)

                if observation.state in (ProcessState.RUNNING, ProcessState.STARTING):
                    deadline = state["readiness_deadline"]
                    if deadline is None:
                        deadline = moment + self.policy.readiness_grace
                        self._write_state(
                            db,
                            lease,
                            moment,
                            failures=state["consecutive_failures"],
                            last_start_at=state["last_start_at"],
                            backoff_until=state["backoff_until"],
                            readiness_deadline=deadline,
                        )
                    if moment < deadline:
                        return SupervisorResult(
                            "waiting_readiness",
                            observation,
                            detail="runtime has not yet become ready",
                        )

                    try:
                        self.backend.stop()
                    except Exception as exc:
                        self._event(
                            db,
                            lease,
                            moment,
                            "stop_failed",
                            f"readiness-timeout:{type(exc).__name__}",
                        )
                        raise
                    failures = state["consecutive_failures"] + 1
                    backoff_until = moment + self._backoff(failures)
                    self._event(
                        db,
                        lease,
                        moment,
                        "readiness_timeout",
                        observation.detail or "runtime did not become ready",
                    )
                    self._write_state(
                        db,
                        lease,
                        moment,
                        failures=failures,
                        last_start_at=state["last_start_at"],
                        backoff_until=backoff_until,
                        readiness_deadline=None,
                    )
                    return SupervisorResult(
                        "readiness_timeout",
                        observation,
                        backoff_until=backoff_until,
                    )

                if observation.state is ProcessState.UNKNOWN:
                    self._event(
                        db,
                        lease,
                        moment,
                        "unknown_process_state",
                        observation.detail or "backend could not establish process state",
                    )
                    return SupervisorResult(
                        "unknown_state",
                        observation,
                        detail="refusing to start while process state is unknown",
                    )

                backoff_until = state["backoff_until"]
                if backoff_until is not None:
                    if moment < backoff_until:
                        return SupervisorResult(
                            "backoff",
                            observation,
                            backoff_until=backoff_until,
                        )
                    backoff_until = None

                if self._restart_count(db, lease, moment) >= self.policy.max_restarts_in_window:
                    self._event(
                        db,
                        lease,
                        moment,
                        "restart_limit",
                        "restart window limit reached",
                    )
                    return SupervisorResult(
                        "restart_limit",
                        observation,
                        detail="manual/operator review required",
                    )

                failures = state["consecutive_failures"]
                if observation.state is ProcessState.FAILED:
                    failures += 1

                self._event(
                    db,
                    lease,
                    moment,
                    "start_requested",
                    f"observed:{observation.state.value}",
                )
                try:
                    self.backend.start(epoch=lease.epoch)
                except Exception as exc:
                    failures += 1
                    backoff_until = moment + self._backoff(failures)
                    self._event(
                        db,
                        lease,
                        moment,
                        "start_failed",
                        type(exc).__name__,
                    )
                    self._write_state(
                        db,
                        lease,
                        moment,
                        failures=failures,
                        last_start_at=moment,
                        backoff_until=backoff_until,
                        readiness_deadline=None,
                    )
                    return SupervisorResult(
                        "start_failed",
                        observation,
                        backoff_until=backoff_until,
                        detail=type(exc).__name__,
                    )

                deadline = moment + self.policy.readiness_grace
                self._write_state(
                    db,
                    lease,
                    moment,
                    failures=failures,
                    last_start_at=moment,
                    backoff_until=None,
                    readiness_deadline=deadline,
                )
                return SupervisorResult(
                    "started",
                    observation,
                    detail=f"epoch:{lease.epoch}",
                )

    def events(self) -> tuple[tuple[str, int, str, str, str], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT owner_id, epoch, occurred_at, event_type, detail
                    FROM run_supervisor_events ORDER BY event_id
                    """
                )
            )
