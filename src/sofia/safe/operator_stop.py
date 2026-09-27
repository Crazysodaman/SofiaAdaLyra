from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True,slots=True)
class OperatorStopState:
    active: bool
    updated_at: datetime
    updated_by: str
    reason: str

    def __post_init__(self)->None:
        if not isinstance(self.active,bool):
            raise TypeError("active must be boolean")
        if not isinstance(self.updated_at,datetime):
            raise TypeError("updated_at must be a datetime")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        if not isinstance(self.updated_by,str) or not self.updated_by.strip():
            raise ValueError("updated_by must be nonempty")
        if not isinstance(self.reason,str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")


class OperatorStopStore:
    """Durable independently enforced operator stop for side effects."""

    def __init__(self,state_path:Path|str)->None:
        self.path=Path(state_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_operator_stop (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
            """)
            row=db.execute(
                "SELECT 1 FROM safe_operator_stop WHERE singleton=1"
            ).fetchone()
            if row is None:
                db.execute("""
                    INSERT INTO safe_operator_stop(
                        singleton,active,updated_at,updated_by,reason
                    ) VALUES(1,0,?,?,?)
                """,(
                    datetime.now(timezone.utc).isoformat(),
                    "system:bootstrap",
                    "initial inactive operator stop",
                ))

    def current(self)->OperatorStopState:
        with sqlite3.connect(self.path,timeout=10) as db:
            row=db.execute("""
                SELECT active,updated_at,updated_by,reason
                FROM safe_operator_stop WHERE singleton=1
            """).fetchone()
        if row is None:
            raise RuntimeError("operator stop state is missing")
        return OperatorStopState(
            active=bool(row[0]),
            updated_at=datetime.fromisoformat(row[1]),
            updated_by=row[2],
            reason=row[3],
        )

    def set(
        self,
        *,
        active:bool,
        updated_by:str,
        reason:str,
        at:datetime|None=None,
    )->OperatorStopState:
        if not isinstance(active,bool):
            raise TypeError("active must be boolean")
        if updated_by!="Sparks":
            raise PermissionError(
                "current operator stop authority is explicitly Sparks"
            )
        if not isinstance(reason,str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        moment=at or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                UPDATE safe_operator_stop
                SET active=?,updated_at=?,updated_by=?,reason=?
                WHERE singleton=1
            """,(
                1 if active else 0,
                moment.astimezone(timezone.utc).isoformat(),
                updated_by,
                reason.strip(),
            ))
            db.commit()
        return self.current()
