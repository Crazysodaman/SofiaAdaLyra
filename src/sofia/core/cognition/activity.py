"""Durable, content-free activity state for routed cognitive model roles."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3


class CognitiveActivityState(str, Enum):
    BUSY = "busy"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CognitiveModelActivity:
    role: str
    model: str
    state: CognitiveActivityState
    host: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.role not in {"primary", "secondary"}:
            raise ValueError("cognitive activity role must be primary or secondary")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("cognitive activity model must be nonempty")
        if not isinstance(self.state, CognitiveActivityState):
            raise TypeError("cognitive activity state is invalid")
        if self.host is not None and (
            not isinstance(self.host, str) or not self.host.strip()
        ):
            raise ValueError("cognitive activity host must be None or nonempty")
        if (
            not isinstance(self.updated_at, datetime)
            or self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("cognitive activity timestamp must be timezone-aware")


class CognitiveModelActivityStore:
    """Share transient role activity with diagnostics through canonical state."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS cognition_model_activity (
                    role TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    state TEXT NOT NULL,
                    host TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _moment(at: datetime | None) -> datetime:
        moment = datetime.now(timezone.utc) if at is None else at
        if (
            not isinstance(moment, datetime)
            or moment.tzinfo is None
            or moment.utcoffset() is None
        ):
            raise ValueError("activity time must be timezone-aware")
        return moment.astimezone(timezone.utc)

    @staticmethod
    def _validate(role: str, model: str, host: str | None) -> None:
        if role not in {"primary", "secondary"}:
            raise ValueError("activity role must be primary or secondary")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("activity model must be nonempty")
        if host is not None and (
            not isinstance(host, str) or not host.strip()
        ):
            raise ValueError("activity host must be None or nonempty")

    def _write(
        self,
        *,
        role: str,
        model: str,
        state: CognitiveActivityState,
        host: str | None,
        at: datetime | None,
    ) -> None:
        self._validate(role, model, host)
        moment = self._moment(at)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO cognition_model_activity (
                    role,model,state,host,updated_at
                )
                VALUES (?,?,?,?,?)
                ON CONFLICT(role) DO UPDATE SET
                    model=excluded.model,
                    state=excluded.state,
                    host=excluded.host,
                    updated_at=excluded.updated_at
                """,
                (
                    role,
                    model,
                    state.value,
                    host,
                    moment.isoformat(),
                ),
            )

    def mark_busy(
        self,
        *,
        role: str,
        model: str,
        host: str | None = None,
        at: datetime | None = None,
    ) -> None:
        self._write(
            role=role,
            model=model,
            state=CognitiveActivityState.BUSY,
            host=host,
            at=at,
        )

    def mark_finished(
        self,
        *,
        role: str,
        model: str,
        host: str | None = None,
        succeeded: bool,
        at: datetime | None = None,
    ) -> None:
        if type(succeeded) is not bool:
            raise TypeError("succeeded must be bool")
        self._write(
            role=role,
            model=model,
            state=(
                CognitiveActivityState.READY
                if succeeded
                else CognitiveActivityState.ERROR
            ),
            host=host,
            at=at,
        )

    def clear_stale_busy(self) -> None:
        """A new runtime process cannot inherit a prior process's busy claim."""
        with closing(self._connect()) as db, db:
            db.execute(
                "DELETE FROM cognition_model_activity WHERE state=?",
                (CognitiveActivityState.BUSY.value,),
            )

    def get(self, role: str) -> CognitiveModelActivity | None:
        if role not in {"primary", "secondary"}:
            raise ValueError("activity role must be primary or secondary")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT role,model,state,host,updated_at
                FROM cognition_model_activity
                WHERE role=?
                """,
                (role,),
            ).fetchone()
        if row is None:
            return None
        return CognitiveModelActivity(
            role=row["role"],
            model=row["model"],
            state=CognitiveActivityState(row["state"]),
            host=row["host"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
