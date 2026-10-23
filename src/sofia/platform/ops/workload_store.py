"""Durable observed Fleet workload-instance state.

This is observation/state evidence only. Recording an instance does not grant
migration, stop, start, or placement authority.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .workload import WorkloadInstance, WorkloadPhase


class WorkloadInstanceStore:
    def __init__(self, state_path: Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_workload_instance (
                    instance_id TEXT PRIMARY KEY,
                    workload_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    host_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    lease_epoch INTEGER,
                    observed_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ops_workload_id
                ON ops_workload_instance(workload_id)
                """
            )

    @staticmethod
    def _moment(at: datetime | None) -> datetime:
        value = at or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workload observation time must be timezone-aware")
        return value.astimezone(timezone.utc)

    def observe(
        self,
        instance: WorkloadInstance,
        *,
        at: datetime | None = None,
    ) -> None:
        if not isinstance(instance, WorkloadInstance):
            raise TypeError("instance must be WorkloadInstance")
        moment = self._moment(at)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO ops_workload_instance(
                    instance_id,workload_id,version,host_id,phase,
                    lease_epoch,observed_at
                )
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    workload_id=excluded.workload_id,
                    version=excluded.version,
                    host_id=excluded.host_id,
                    phase=excluded.phase,
                    lease_epoch=excluded.lease_epoch,
                    observed_at=excluded.observed_at
                """,
                (
                    instance.instance_id,
                    instance.workload_id,
                    instance.version,
                    instance.host_id,
                    instance.phase.value,
                    instance.lease_epoch,
                    moment.isoformat(),
                ),
            )

    def instances(self) -> tuple[WorkloadInstance, ...]:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                """
                SELECT instance_id,workload_id,version,host_id,phase,lease_epoch
                FROM ops_workload_instance
                ORDER BY workload_id,instance_id
                """
            ).fetchall()
        return tuple(
            WorkloadInstance(
                instance_id=str(row[0]),
                workload_id=str(row[1]),
                version=str(row[2]),
                host_id=str(row[3]),
                phase=WorkloadPhase(str(row[4])),
                lease_epoch=None if row[5] is None else int(row[5]),
            )
            for row in rows
        )

    def remove(self, instance_id: str) -> bool:
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("instance_id required")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            changed = db.execute(
                "DELETE FROM ops_workload_instance WHERE instance_id=?",
                (instance_id.strip(),),
            )
            return changed.rowcount == 1
