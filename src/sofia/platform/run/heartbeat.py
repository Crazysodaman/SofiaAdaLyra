from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("heartbeat time must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ApplicationHeartbeat:
    instance_id: str
    recorded_at: datetime
    ready: bool
    runtime_state: str
    database_writable: bool
    background_running: bool
    detail: str
    generation_epoch: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("instance_id must be nonempty")
        _utc(self.recorded_at)
        for name in ("ready", "database_writable", "background_running"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if not isinstance(self.runtime_state, str) or not self.runtime_state.strip():
            raise ValueError("runtime_state must be nonempty")
        if not isinstance(self.detail, str) or len(self.detail) > 500:
            raise ValueError("detail must be bounded text")
        if self.generation_epoch is not None and (
            type(self.generation_epoch) is not int or self.generation_epoch < 1
        ):
            raise ValueError("generation_epoch must be a positive integer or None")


class ApplicationHeartbeatStore:
    """Durable application-level readiness evidence for RUN supervisors."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_application_heartbeat (
                        instance_id TEXT PRIMARY KEY,
                        recorded_at TEXT NOT NULL,
                        ready INTEGER NOT NULL CHECK(ready IN (0,1)),
                        runtime_state TEXT NOT NULL,
                        database_writable INTEGER NOT NULL CHECK(database_writable IN (0,1)),
                        background_running INTEGER NOT NULL CHECK(background_running IN (0,1)),
                        detail TEXT NOT NULL
                    )
                    """
                )
                columns = {
                    row[1] for row in db.execute(
                        "PRAGMA table_info(run_application_heartbeat)"
                    ).fetchall()
                }
                if "generation_epoch" not in columns:
                    db.execute(
                        "ALTER TABLE run_application_heartbeat "
                        "ADD COLUMN generation_epoch INTEGER"
                    )
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_application_heartbeat_current (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        instance_id TEXT NOT NULL,
                        recorded_at TEXT NOT NULL
                    )
                    """
                )
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_runtime_generation (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        epoch INTEGER NOT NULL CHECK(epoch>=1),
                        bound_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def publish(self, heartbeat: ApplicationHeartbeat) -> None:
        if not isinstance(heartbeat, ApplicationHeartbeat):
            raise TypeError("heartbeat must be ApplicationHeartbeat")
        moment = _utc(heartbeat.recorded_at)
        with closing(self._connect()) as db:
            with db:
                # The write itself is part of readiness evidence.
                db.execute(
                    """
                    INSERT INTO run_application_heartbeat (
                        instance_id, recorded_at, ready, runtime_state,
                        database_writable, background_running, detail,
                        generation_epoch
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(instance_id) DO UPDATE SET
                        recorded_at=excluded.recorded_at,
                        ready=excluded.ready,
                        runtime_state=excluded.runtime_state,
                        database_writable=excluded.database_writable,
                        background_running=excluded.background_running,
                        detail=excluded.detail,
                        generation_epoch=excluded.generation_epoch
                    """,
                    (
                        heartbeat.instance_id,
                        moment.isoformat(),
                        int(heartbeat.ready),
                        heartbeat.runtime_state,
                        int(heartbeat.database_writable),
                        int(heartbeat.background_running),
                        heartbeat.detail,
                        heartbeat.generation_epoch,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO run_application_heartbeat_current (
                        singleton, instance_id, recorded_at
                    )
                    VALUES (1, ?, ?)
                    ON CONFLICT(singleton) DO UPDATE SET
                        instance_id=excluded.instance_id,
                        recorded_at=excluded.recorded_at
                    WHERE excluded.recorded_at >=
                          run_application_heartbeat_current.recorded_at
                    """,
                    (heartbeat.instance_id, moment.isoformat()),
                )

    def current(self) -> ApplicationHeartbeat | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT h.instance_id, h.recorded_at, h.ready, h.runtime_state,
                       h.database_writable, h.background_running, h.detail,
                       h.generation_epoch
                FROM run_application_heartbeat_current c
                JOIN run_application_heartbeat h
                  ON h.instance_id=c.instance_id
                WHERE c.singleton=1
                """
            ).fetchone()
        if row is None:
            return None
        return ApplicationHeartbeat(
            instance_id=row[0],
            recorded_at=datetime.fromisoformat(row[1]),
            ready=bool(row[2]),
            runtime_state=row[3],
            database_writable=bool(row[4]),
            background_running=bool(row[5]),
            detail=row[6],
            generation_epoch=row[7],
        )

    def bind_generation(self, epoch: int, *, now: datetime) -> None:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("epoch must be a positive integer")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """
                INSERT INTO run_runtime_generation(singleton,epoch,bound_at)
                VALUES(1,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    epoch=excluded.epoch,bound_at=excluded.bound_at
                WHERE excluded.epoch >= run_runtime_generation.epoch
                """,
                (epoch, moment.isoformat()),
            )
            if changed.rowcount != 1:
                raise PermissionError(
                    "stale runtime generation cannot replace the active generation"
                )

    def current_generation(self) -> int | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT epoch FROM run_runtime_generation WHERE singleton=1"
            ).fetchone()
        return None if row is None else int(row[0])
