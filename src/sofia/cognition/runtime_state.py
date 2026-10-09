"""Authoritative, content-free runtime projection for cognition diagnostics."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


@dataclass(frozen=True, slots=True)
class CognitionModelRuntimeState:
    role: str
    model: str
    host: str | None
    installed: bool | None
    residency: str
    activity: str
    last_request_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CognitionRuntimeState:
    models: tuple[CognitionModelRuntimeState, ...]
    residency_mode: str
    routing_mode: str
    parallel_workers: int
    latest_route: str | None
    resource_constraints: tuple[str, ...]
    updated_at: datetime


class CognitionRuntimeStateStore:
    """Share the live runtime's projection through canonical ``sofia.db``."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cognition_runtime_model (
                    role TEXT PRIMARY KEY CHECK(role IN ('primary','secondary')),
                    model TEXT NOT NULL,
                    host TEXT,
                    installed INTEGER,
                    residency TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    last_request_at TEXT,
                    last_success_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cognition_runtime_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    residency_mode TEXT NOT NULL,
                    routing_mode TEXT NOT NULL,
                    parallel_workers INTEGER NOT NULL,
                    latest_route TEXT,
                    resource_constraints_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cognition_execution_history (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    model TEXT NOT NULL,
                    host TEXT,
                    route TEXT,
                    succeeded INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _moment(at: datetime | None = None) -> datetime:
        value = at or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("runtime state timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def configure(
        self,
        *,
        models: dict[str, str],
        residency_mode: str,
        routing_mode: str,
        parallel_workers: int,
        at: datetime | None = None,
    ) -> None:
        moment = self._moment(at).isoformat()
        with closing(self._connect()) as db, db:
            for role, model in models.items():
                if role not in {"primary", "secondary"} or not model.strip():
                    raise ValueError("configured cognition role/model is invalid")
                db.execute(
                    """
                    INSERT INTO cognition_runtime_model
                    (role,model,host,installed,residency,activity,updated_at)
                    VALUES (?,?,NULL,NULL,'unknown','idle',?)
                    ON CONFLICT(role) DO UPDATE SET
                        model=excluded.model, updated_at=excluded.updated_at
                    """,
                    (role, model, moment),
                )
            placeholders = tuple(models)
            if "secondary" not in placeholders:
                db.execute("DELETE FROM cognition_runtime_model WHERE role='secondary'")
            db.execute(
                """
                INSERT INTO cognition_runtime_state VALUES (1,?,?,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    residency_mode=excluded.residency_mode,
                    routing_mode=excluded.routing_mode,
                    parallel_workers=excluded.parallel_workers,
                    updated_at=excluded.updated_at
                """,
                (residency_mode, routing_mode, parallel_workers, None, "[]", moment),
            )

    def publish_lifecycle(
        self,
        *,
        role: str,
        model: str,
        host: str | None,
        residency: str,
        installed: bool | None,
        error: str | None = None,
        at: datetime | None = None,
    ) -> None:
        moment = self._moment(at).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                """
                UPDATE cognition_runtime_model SET
                    model=?,host=?,installed=?,residency=?,last_error=?,updated_at=?
                WHERE role=?
                """,
                (
                    model,
                    host,
                    None if installed is None else int(installed),
                    residency,
                    error,
                    moment,
                    role,
                ),
            )

    def publish_decision(
        self,
        *,
        residency_mode: str,
        constraints: tuple[str, ...],
        at: datetime | None = None,
    ) -> None:
        moment = self._moment(at).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                """
                UPDATE cognition_runtime_state SET residency_mode=?,
                    resource_constraints_json=?,updated_at=? WHERE singleton=1
                """,
                (residency_mode, json.dumps(constraints), moment),
            )

    def publish_route(self, route: str, *, at: datetime | None = None) -> None:
        moment = self._moment(at).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE cognition_runtime_state SET latest_route=?,updated_at=? WHERE singleton=1",
                (route, moment),
            )

    def mark_request(
        self, *, role: str, model: str, host: str | None, at: datetime | None = None
    ) -> None:
        moment = self._moment(at).isoformat()
        with closing(self._connect()) as db, db:
            db.execute(
                """
                UPDATE cognition_runtime_model SET model=?,host=?,activity='busy',
                    last_request_at=?,updated_at=? WHERE role=?
                """,
                (model, host, moment, moment, role),
            )

    def mark_result(
        self,
        *,
        role: str,
        model: str,
        host: str | None,
        route: str,
        succeeded: bool,
        error: str | None = None,
        at: datetime | None = None,
    ) -> None:
        moment = self._moment(at).isoformat()
        activity = "ready" if succeeded else "error"
        with closing(self._connect()) as db, db:
            db.execute(
                """
                UPDATE cognition_runtime_model SET model=?,host=?,activity=?,
                    last_success_at=CASE WHEN ? THEN ? ELSE last_success_at END,
                    last_error=?,updated_at=? WHERE role=?
                """,
                (model, host, activity, int(succeeded), moment, error, moment, role),
            )
            db.execute(
                """INSERT INTO cognition_execution_history
                (role,model,host,route,succeeded,occurred_at) VALUES (?,?,?,?,?,?)""",
                (role, model, host, route, int(succeeded), moment),
            )
            db.execute(
                "DELETE FROM cognition_execution_history WHERE sequence NOT IN "
                "(SELECT sequence FROM cognition_execution_history "
                "ORDER BY sequence DESC LIMIT 100)"
            )

    def clear_stale_busy(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE cognition_runtime_model SET activity='idle' WHERE activity='busy'"
            )

    def snapshot(self) -> CognitionRuntimeState | None:
        with closing(self._connect()) as db:
            meta = db.execute(
                "SELECT * FROM cognition_runtime_state WHERE singleton=1"
            ).fetchone()
            rows = db.execute(
                "SELECT * FROM cognition_runtime_model ORDER BY role"
            ).fetchall()
        if meta is None:
            return None
        models = tuple(
            CognitionModelRuntimeState(
                role=row["role"],
                model=row["model"],
                host=row["host"],
                installed=None if row["installed"] is None else bool(row["installed"]),
                residency=row["residency"],
                activity=row["activity"],
                last_request_at=None if row["last_request_at"] is None else datetime.fromisoformat(row["last_request_at"]),
                last_success_at=None if row["last_success_at"] is None else datetime.fromisoformat(row["last_success_at"]),
                last_error=row["last_error"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        )
        active_workers = sum(item.activity == "busy" for item in models)
        return CognitionRuntimeState(
            models=models,
            residency_mode=meta["residency_mode"],
            routing_mode=meta["routing_mode"],
            parallel_workers=active_workers,
            latest_route=meta["latest_route"],
            resource_constraints=tuple(json.loads(meta["resource_constraints_json"])),
            updated_at=datetime.fromisoformat(meta["updated_at"]),
        )

    def history(self, *, limit: int = 20) -> tuple[dict, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("history limit must be in 1..100")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT role,model,host,route,succeeded,occurred_at "
                "FROM cognition_execution_history ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(dict(row) for row in rows)
