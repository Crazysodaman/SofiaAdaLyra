"""Durable desired Fleet state for reconciliation.

Desired state is declarative intent only. Persisting it does not authorize any
maintenance, migration, or execution.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .desired import DesiredHostState, DesiredWorkloadPlacement
from .model import HostLifecycle


class DesiredFleetStateStore:
    def __init__(self, state_path: Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_desired_host (
                    host_id TEXT PRIMARY KEY,
                    lifecycle TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_desired_workload (
                    workload_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _moment(at: datetime | None) -> datetime:
        value = at or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("desired-state timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def set_host(
        self,
        desired: DesiredHostState,
        *,
        at: datetime | None = None,
    ) -> None:
        if not isinstance(desired, DesiredHostState):
            raise TypeError("desired must be DesiredHostState")
        moment = self._moment(at)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO ops_desired_host(host_id,lifecycle,updated_at)
                VALUES(?,?,?)
                ON CONFLICT(host_id) DO UPDATE SET
                    lifecycle=excluded.lifecycle,
                    updated_at=excluded.updated_at
                """,
                (
                    desired.host_id,
                    desired.lifecycle.value,
                    moment.isoformat(),
                ),
            )

    def set_workload(
        self,
        desired: DesiredWorkloadPlacement,
        *,
        at: datetime | None = None,
    ) -> None:
        if not isinstance(desired, DesiredWorkloadPlacement):
            raise TypeError("desired must be DesiredWorkloadPlacement")
        moment = self._moment(at)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO ops_desired_workload(workload_id,host_id,updated_at)
                VALUES(?,?,?)
                ON CONFLICT(workload_id) DO UPDATE SET
                    host_id=excluded.host_id,
                    updated_at=excluded.updated_at
                """,
                (
                    desired.workload_id,
                    desired.host_id,
                    moment.isoformat(),
                ),
            )

    def hosts(self) -> tuple[DesiredHostState, ...]:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                """
                SELECT host_id,lifecycle
                FROM ops_desired_host
                ORDER BY host_id
                """
            ).fetchall()
        return tuple(
            DesiredHostState(
                host_id=str(row[0]),
                lifecycle=HostLifecycle(str(row[1])),
            )
            for row in rows
        )

    def workloads(self) -> tuple[DesiredWorkloadPlacement, ...]:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                """
                SELECT workload_id,host_id
                FROM ops_desired_workload
                ORDER BY workload_id
                """
            ).fetchall()
        return tuple(
            DesiredWorkloadPlacement(
                workload_id=str(row[0]),
                host_id=str(row[1]),
            )
            for row in rows
        )

    def remove_host(self, host_id: str) -> bool:
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            changed = db.execute(
                "DELETE FROM ops_desired_host WHERE host_id=?",
                (host_id.strip(),),
            )
            return changed.rowcount == 1

    def remove_workload(self, workload_id: str) -> bool:
        if not isinstance(workload_id, str) or not workload_id.strip():
            raise ValueError("workload_id required")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            changed = db.execute(
                "DELETE FROM ops_desired_workload WHERE workload_id=?",
                (workload_id.strip(),),
            )
            return changed.rowcount == 1
