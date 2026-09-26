"""Durable PKG-RUN heartbeat sessions and derived local health truth.

The heartbeat writer is intentionally narrow. A service host starts one session
with a unique session ID and PID, then pulses with the current durable RUN
lifecycle snapshot. Starting a newer session fences the older writer.

Health is derived from durable evidence. A process existing in the OS is not
proof that Sofía is ready or healthy.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from .lifecycle import RunLifecycleSnapshot, RunLifecycleState


class RunHealthState(str, Enum):
    UNKNOWN = "unknown"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    FENCED = "fenced"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class RunHeartbeatSnapshot:
    session_id: str
    process_id: int
    started_at: datetime
    last_beat_at: datetime
    lifecycle_generation: int
    lifecycle_state: RunLifecycleState
    detail: str
    closed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RunHealthObservation:
    state: RunHealthState
    alive: bool
    ready: bool
    healthy: bool
    degraded: bool
    observed_at: datetime
    heartbeat_at: datetime | None
    heartbeat_age: timedelta | None
    lifecycle_state: RunLifecycleState | None
    detail: str


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def _session_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 160
    ):
        raise ValueError("session_id must be a bounded identifier")
    return value.strip()


def _pid(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("process_id must be a positive integer")
    return value


def _detail(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("detail must be a string")
    clean = value.strip()
    if len(clean) > 500:
        raise ValueError("detail must be at most 500 characters")
    return clean


class RunHeartbeatStore:
    """SQLite-backed heartbeat session with stale-writer fencing."""

    def __init__(self, state_path: str | Path) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("state_path required")
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS run_heartbeat_state (
                        heartbeat_key TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        process_id INTEGER NOT NULL,
                        started_at TEXT NOT NULL,
                        last_beat_at TEXT NOT NULL,
                        lifecycle_generation INTEGER NOT NULL,
                        lifecycle_state TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        closed_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS run_heartbeat_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        process_id INTEGER NOT NULL,
                        occurred_at TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        lifecycle_generation INTEGER NOT NULL,
                        lifecycle_state TEXT NOT NULL,
                        detail TEXT NOT NULL
                    );
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _snapshot(row: tuple) -> RunHeartbeatSnapshot:
        return RunHeartbeatSnapshot(
            session_id=row[0],
            process_id=int(row[1]),
            started_at=datetime.fromisoformat(row[2]).astimezone(timezone.utc),
            last_beat_at=datetime.fromisoformat(row[3]).astimezone(timezone.utc),
            lifecycle_generation=int(row[4]),
            lifecycle_state=RunLifecycleState(row[5]),
            detail=row[6],
            closed_at=(
                datetime.fromisoformat(row[7]).astimezone(timezone.utc)
                if row[7] is not None
                else None
            ),
        )

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        *,
        session_id: str,
        process_id: int,
        at: datetime,
        event_type: str,
        lifecycle: RunLifecycleSnapshot,
        detail: str,
    ) -> None:
        db.execute(
            """
            INSERT INTO run_heartbeat_events
            (session_id, process_id, occurred_at, event_type,
             lifecycle_generation, lifecycle_state, detail)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                session_id,
                process_id,
                at.isoformat(),
                event_type,
                lifecycle.generation,
                lifecycle.state.value,
                detail,
            ),
        )

    def current(self) -> RunHeartbeatSnapshot | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT session_id, process_id, started_at, last_beat_at,
                       lifecycle_generation, lifecycle_state, detail, closed_at
                FROM run_heartbeat_state
                WHERE heartbeat_key='runtime'
                """
            ).fetchone()
        return None if row is None else self._snapshot(row)

    def begin(
        self,
        *,
        session_id: str,
        process_id: int,
        at: datetime,
        lifecycle: RunLifecycleSnapshot,
        detail: str = "service heartbeat started",
    ) -> RunHeartbeatSnapshot:
        session = _session_id(session_id)
        pid = _pid(process_id)
        moment = _utc(at)
        clean_detail = _detail(detail)
        if not isinstance(lifecycle, RunLifecycleSnapshot):
            raise TypeError("RunLifecycleSnapshot required")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                """
                SELECT session_id, process_id, started_at, last_beat_at,
                       lifecycle_generation, lifecycle_state, detail, closed_at
                FROM run_heartbeat_state
                WHERE heartbeat_key='runtime'
                """
            ).fetchone()
            if previous is not None:
                old = self._snapshot(previous)
                if (
                    old.session_id == session
                    and old.process_id == pid
                    and old.closed_at is None
                ):
                    db.rollback()
                    return old

            db.execute(
                """
                INSERT INTO run_heartbeat_state
                (heartbeat_key, session_id, process_id, started_at, last_beat_at,
                 lifecycle_generation, lifecycle_state, detail, closed_at)
                VALUES ('runtime',?,?,?,?,?,?,?,NULL)
                ON CONFLICT(heartbeat_key) DO UPDATE SET
                    session_id=excluded.session_id,
                    process_id=excluded.process_id,
                    started_at=excluded.started_at,
                    last_beat_at=excluded.last_beat_at,
                    lifecycle_generation=excluded.lifecycle_generation,
                    lifecycle_state=excluded.lifecycle_state,
                    detail=excluded.detail,
                    closed_at=NULL
                """,
                (
                    session,
                    pid,
                    moment.isoformat(),
                    moment.isoformat(),
                    lifecycle.generation,
                    lifecycle.state.value,
                    clean_detail,
                ),
            )
            self._event(
                db,
                session_id=session,
                process_id=pid,
                at=moment,
                event_type="session_started",
                lifecycle=lifecycle,
                detail=clean_detail,
            )
            db.commit()
            return RunHeartbeatSnapshot(
                session_id=session,
                process_id=pid,
                started_at=moment,
                last_beat_at=moment,
                lifecycle_generation=lifecycle.generation,
                lifecycle_state=lifecycle.state,
                detail=clean_detail,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def pulse(
        self,
        *,
        session_id: str,
        process_id: int,
        at: datetime,
        lifecycle: RunLifecycleSnapshot,
        detail: str = "",
    ) -> RunHeartbeatSnapshot:
        session = _session_id(session_id)
        pid = _pid(process_id)
        moment = _utc(at)
        clean_detail = _detail(detail)
        if not isinstance(lifecycle, RunLifecycleSnapshot):
            raise TypeError("RunLifecycleSnapshot required")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT session_id, process_id, started_at, last_beat_at,
                       lifecycle_generation, lifecycle_state, detail, closed_at
                FROM run_heartbeat_state
                WHERE heartbeat_key='runtime'
                """
            ).fetchone()
            if row is None:
                raise RuntimeError("heartbeat session has not been started")
            current = self._snapshot(row)
            if (
                current.session_id != session
                or current.process_id != pid
                or current.closed_at is not None
            ):
                raise RuntimeError("heartbeat writer is stale or closed")
            if moment < current.last_beat_at:
                raise RuntimeError("heartbeat time moved backwards")
            if lifecycle.generation < current.lifecycle_generation:
                raise RuntimeError("lifecycle generation regressed")

            changed = db.execute(
                """
                UPDATE run_heartbeat_state
                SET last_beat_at=?, lifecycle_generation=?,
                    lifecycle_state=?, detail=?
                WHERE heartbeat_key='runtime'
                  AND session_id=? AND process_id=? AND closed_at IS NULL
                """,
                (
                    moment.isoformat(),
                    lifecycle.generation,
                    lifecycle.state.value,
                    clean_detail,
                    session,
                    pid,
                ),
            )
            if changed.rowcount != 1:
                raise RuntimeError("heartbeat session changed concurrently")
            db.commit()
            return RunHeartbeatSnapshot(
                session_id=session,
                process_id=pid,
                started_at=current.started_at,
                last_beat_at=moment,
                lifecycle_generation=lifecycle.generation,
                lifecycle_state=lifecycle.state,
                detail=clean_detail,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def close(
        self,
        *,
        session_id: str,
        process_id: int,
        at: datetime,
        lifecycle: RunLifecycleSnapshot,
        detail: str = "service heartbeat stopped",
    ) -> RunHeartbeatSnapshot:
        session = _session_id(session_id)
        pid = _pid(process_id)
        moment = _utc(at)
        clean_detail = _detail(detail)
        if not isinstance(lifecycle, RunLifecycleSnapshot):
            raise TypeError("RunLifecycleSnapshot required")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT session_id, process_id, started_at, last_beat_at,
                       lifecycle_generation, lifecycle_state, detail, closed_at
                FROM run_heartbeat_state
                WHERE heartbeat_key='runtime'
                """
            ).fetchone()
            if row is None:
                raise RuntimeError("heartbeat session has not been started")
            current = self._snapshot(row)
            if current.session_id != session or current.process_id != pid:
                raise RuntimeError("heartbeat writer is stale")
            if current.closed_at is not None:
                db.rollback()
                return current
            if moment < current.last_beat_at:
                raise RuntimeError("heartbeat close time moved backwards")

            db.execute(
                """
                UPDATE run_heartbeat_state
                SET last_beat_at=?, lifecycle_generation=?,
                    lifecycle_state=?, detail=?, closed_at=?
                WHERE heartbeat_key='runtime'
                  AND session_id=? AND process_id=? AND closed_at IS NULL
                """,
                (
                    moment.isoformat(),
                    lifecycle.generation,
                    lifecycle.state.value,
                    clean_detail,
                    moment.isoformat(),
                    session,
                    pid,
                ),
            )
            self._event(
                db,
                session_id=session,
                process_id=pid,
                at=moment,
                event_type="session_closed",
                lifecycle=lifecycle,
                detail=clean_detail,
            )
            db.commit()
            return RunHeartbeatSnapshot(
                session_id=session,
                process_id=pid,
                started_at=current.started_at,
                last_beat_at=moment,
                lifecycle_generation=lifecycle.generation,
                lifecycle_state=lifecycle.state,
                detail=clean_detail,
                closed_at=moment,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def assess(
        self,
        *,
        now: datetime,
        stale_after: timedelta = timedelta(seconds=30),
    ) -> RunHealthObservation:
        moment = _utc(now)
        if not isinstance(stale_after, timedelta) or not (
            timedelta(seconds=5) <= stale_after <= timedelta(minutes=10)
        ):
            raise ValueError("stale_after must be between 5 seconds and 10 minutes")

        heartbeat = self.current()
        if heartbeat is None:
            return RunHealthObservation(
                RunHealthState.UNKNOWN,
                False, False, False, False,
                moment, None, None, None,
                "no heartbeat evidence",
            )

        age = moment - heartbeat.last_beat_at
        if age < timedelta(0):
            return RunHealthObservation(
                RunHealthState.UNKNOWN,
                False, False, False, False,
                moment, heartbeat.last_beat_at, age,
                heartbeat.lifecycle_state,
                "heartbeat clock is in the future",
            )
        if heartbeat.closed_at is not None:
            return RunHealthObservation(
                RunHealthState.STOPPED,
                False, False, False, False,
                moment, heartbeat.last_beat_at, age,
                heartbeat.lifecycle_state,
                heartbeat.detail or "heartbeat session closed",
            )
        if age > stale_after:
            return RunHealthObservation(
                RunHealthState.STALE,
                False, False, False, False,
                moment, heartbeat.last_beat_at, age,
                heartbeat.lifecycle_state,
                "heartbeat is stale",
            )

        lifecycle = heartbeat.lifecycle_state
        if lifecycle is RunLifecycleState.READY:
            state = RunHealthState.HEALTHY
            ready, healthy, degraded = True, True, False
        elif lifecycle is RunLifecycleState.DEGRADED:
            state = RunHealthState.DEGRADED
            ready, healthy, degraded = True, False, True
        elif lifecycle in (RunLifecycleState.STARTING, RunLifecycleState.RECOVERING):
            state = RunHealthState.STARTING
            ready, healthy, degraded = False, False, False
        elif lifecycle in (RunLifecycleState.DRAINING, RunLifecycleState.STOPPING):
            state = RunHealthState.STOPPING
            ready, healthy, degraded = False, False, False
        elif lifecycle is RunLifecycleState.FAILED:
            state = RunHealthState.FAILED
            ready, healthy, degraded = False, False, False
        elif lifecycle is RunLifecycleState.FENCED:
            state = RunHealthState.FENCED
            ready, healthy, degraded = False, False, False
        elif lifecycle is RunLifecycleState.STOPPED:
            state = RunHealthState.STOPPED
            ready, healthy, degraded = False, False, False
        else:
            state = RunHealthState.UNKNOWN
            ready, healthy, degraded = False, False, False

        return RunHealthObservation(
            state=state,
            alive=True,
            ready=ready,
            healthy=healthy,
            degraded=degraded,
            observed_at=moment,
            heartbeat_at=heartbeat.last_beat_at,
            heartbeat_age=age,
            lifecycle_state=lifecycle,
            detail=heartbeat.detail,
        )

    def events(self) -> tuple[tuple[str, int, str, str, int, str, str], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT session_id, process_id, occurred_at, event_type,
                           lifecycle_generation, lifecycle_state, detail
                    FROM run_heartbeat_events ORDER BY event_id
                    """
                )
            )
