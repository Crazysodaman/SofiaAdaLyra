from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3


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


class ApplicationHeartbeatStore:
    """Durable application-level readiness evidence for RUN supervisors."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_application_heartbeat_current (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        instance_id TEXT NOT NULL,
                        recorded_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
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
                        database_writable, background_running, detail
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(instance_id) DO UPDATE SET
                        recorded_at=excluded.recorded_at,
                        ready=excluded.ready,
                        runtime_state=excluded.runtime_state,
                        database_writable=excluded.database_writable,
                        background_running=excluded.background_running,
                        detail=excluded.detail
                    """,
                    (
                        heartbeat.instance_id,
                        moment.isoformat(),
                        int(heartbeat.ready),
                        heartbeat.runtime_state,
                        int(heartbeat.database_writable),
                        int(heartbeat.background_running),
                        heartbeat.detail,
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
                       h.database_writable, h.background_running, h.detail
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
        )

    def is_fresh_ready(
        self,
        *,
        now: datetime,
        max_age: timedelta = timedelta(minutes=3),
    ) -> bool:
        current = self.current()
        if current is None:
            return False
        moment = _utc(now)
        if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        age = moment - current.recorded_at.astimezone(timezone.utc)
        if age < timedelta(0) or age > max_age:
            return False
        return (
            current.ready
            and current.database_writable
            and current.runtime_state.casefold() == "ready"
        )
