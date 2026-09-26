"""Durable PKG-RUN lifecycle truth for one local Sofía runtime.

This state is operational evidence, not authorization. Distributed leadership
and standby promotion remain separate gates. The store records every accepted
transition and detects an unclean restart when a new process finds a prior
nonterminal lifecycle state.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3


class RunLifecycleState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RECOVERING = "recovering"
    READY = "ready"
    DEGRADED = "degraded"
    DRAINING = "draining"
    STOPPING = "stopping"
    FAILED = "failed"
    FENCED = "fenced"


@dataclass(frozen=True, slots=True)
class RunLifecycleSnapshot:
    state: RunLifecycleState
    generation: int
    updated_at: datetime
    detail: str
    owner_id: str | None = None
    epoch: int | None = None


_ALLOWED: dict[RunLifecycleState, frozenset[RunLifecycleState]] = {
    RunLifecycleState.STOPPED: frozenset({
        RunLifecycleState.STARTING,
        RunLifecycleState.RECOVERING,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.STARTING: frozenset({
        RunLifecycleState.RECOVERING,
        RunLifecycleState.READY,
        RunLifecycleState.DEGRADED,
        RunLifecycleState.STOPPING,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.RECOVERING: frozenset({
        RunLifecycleState.READY,
        RunLifecycleState.DEGRADED,
        RunLifecycleState.STOPPING,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.READY: frozenset({
        RunLifecycleState.DEGRADED,
        RunLifecycleState.DRAINING,
        RunLifecycleState.STOPPING,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.DEGRADED: frozenset({
        RunLifecycleState.READY,
        RunLifecycleState.DRAINING,
        RunLifecycleState.STOPPING,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.DRAINING: frozenset({
        RunLifecycleState.READY,
        RunLifecycleState.DEGRADED,
        RunLifecycleState.STOPPING,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.STOPPING: frozenset({
        RunLifecycleState.STOPPED,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.FAILED: frozenset({
        RunLifecycleState.STARTING,
        RunLifecycleState.RECOVERING,
        RunLifecycleState.STOPPING,
        RunLifecycleState.STOPPED,
        RunLifecycleState.FENCED,
    }),
    RunLifecycleState.FENCED: frozenset({
        RunLifecycleState.STOPPED,
    }),
}


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def _detail(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("detail must be a string")
    clean = value.strip()
    if len(clean) > 500:
        raise ValueError("detail must be at most 500 characters")
    return clean


def _authority(
    owner_id: str | None,
    epoch: int | None,
) -> tuple[str | None, int | None]:
    if owner_id is None and epoch is None:
        return None, None
    if (
        not isinstance(owner_id, str)
        or not owner_id.strip()
        or len(owner_id.strip()) > 160
    ):
        raise ValueError("owner_id must be a bounded identifier")
    if type(epoch) is not int or epoch < 1:
        raise ValueError("epoch must be a positive integer")
    return owner_id.strip(), epoch


class RunLifecycleStore:
    """SQLite-backed canonical local runtime lifecycle state."""

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
                    CREATE TABLE IF NOT EXISTS run_lifecycle_state (
                        state_key TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        updated_at TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        owner_id TEXT,
                        epoch INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS run_lifecycle_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        generation INTEGER NOT NULL,
                        from_state TEXT NOT NULL,
                        to_state TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        owner_id TEXT,
                        epoch INTEGER
                    );
                    """
                )
                row = db.execute(
                    "SELECT 1 FROM run_lifecycle_state WHERE state_key='runtime'"
                ).fetchone()
                if row is None:
                    now = datetime.now(timezone.utc).isoformat()
                    db.execute(
                        """
                        INSERT INTO run_lifecycle_state
                        (state_key, state, generation, updated_at, detail,
                         owner_id, epoch)
                        VALUES ('runtime','stopped',0,?,'initialized',NULL,NULL)
                        """,
                        (now,),
                    )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _snapshot(row: tuple) -> RunLifecycleSnapshot:
        return RunLifecycleSnapshot(
            state=RunLifecycleState(row[0]),
            generation=int(row[1]),
            updated_at=datetime.fromisoformat(row[2]).astimezone(timezone.utc),
            detail=row[3],
            owner_id=row[4],
            epoch=int(row[5]) if row[5] is not None else None,
        )

    def current(self) -> RunLifecycleSnapshot:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT state, generation, updated_at, detail, owner_id, epoch
                FROM run_lifecycle_state WHERE state_key='runtime'
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("RUN lifecycle state is missing")
        return self._snapshot(row)

    def transition(
        self,
        *,
        expected: RunLifecycleState | tuple[RunLifecycleState, ...],
        target: RunLifecycleState,
        at: datetime,
        detail: str = "",
        owner_id: str | None = None,
        epoch: int | None = None,
    ) -> RunLifecycleSnapshot:
        if isinstance(expected, RunLifecycleState):
            expected_states = (expected,)
        elif (
            isinstance(expected, tuple)
            and expected
            and all(isinstance(value, RunLifecycleState) for value in expected)
        ):
            expected_states = expected
        else:
            raise TypeError("expected must contain RunLifecycleState values")
        if not isinstance(target, RunLifecycleState):
            raise TypeError("target must be RunLifecycleState")

        moment = _utc(at)
        clean_detail = _detail(detail)
        owner, lease_epoch = _authority(owner_id, epoch)

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT state, generation, updated_at, detail, owner_id, epoch
                FROM run_lifecycle_state WHERE state_key='runtime'
                """
            ).fetchone()
            if row is None:
                raise RuntimeError("RUN lifecycle state is missing")
            current = self._snapshot(row)
            if current.state not in expected_states:
                raise RuntimeError(
                    f"RUN lifecycle expected {[s.value for s in expected_states]!r}; "
                    f"found {current.state.value!r}"
                )
            if target is current.state:
                db.rollback()
                return current
            if target not in _ALLOWED[current.state]:
                raise RuntimeError(
                    f"illegal RUN lifecycle transition "
                    f"{current.state.value}->{target.value}"
                )
            generation = current.generation + 1
            db.execute(
                """
                UPDATE run_lifecycle_state
                SET state=?, generation=?, updated_at=?, detail=?,
                    owner_id=?, epoch=?
                WHERE state_key='runtime' AND generation=?
                """,
                (
                    target.value,
                    generation,
                    moment.isoformat(),
                    clean_detail,
                    owner,
                    lease_epoch,
                    current.generation,
                ),
            )
            db.execute(
                """
                INSERT INTO run_lifecycle_events
                (generation, from_state, to_state, occurred_at, detail,
                 owner_id, epoch)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    generation,
                    current.state.value,
                    target.value,
                    moment.isoformat(),
                    clean_detail,
                    owner,
                    lease_epoch,
                ),
            )
            db.commit()
            return RunLifecycleSnapshot(
                state=target,
                generation=generation,
                updated_at=moment,
                detail=clean_detail,
                owner_id=owner,
                epoch=lease_epoch,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def begin_start(
        self,
        *,
        at: datetime,
        owner_id: str | None = None,
        epoch: int | None = None,
    ) -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.FENCED:
            raise RuntimeError("fenced RUN lifecycle requires explicit operator clear")
        if current.state in (
            RunLifecycleState.STOPPED,
            RunLifecycleState.FAILED,
        ):
            return self.transition(
                expected=current.state,
                target=RunLifecycleState.STARTING,
                at=at,
                detail="startup requested",
                owner_id=owner_id,
                epoch=epoch,
            )
        return self.transition(
            expected=current.state,
            target=RunLifecycleState.RECOVERING,
            at=at,
            detail=f"unclean restart from {current.state.value}",
            owner_id=owner_id,
            epoch=epoch,
        )

    def mark_recovering(self, *, at: datetime, detail: str = "startup recovery") -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.RECOVERING:
            return current
        return self.transition(
            expected=RunLifecycleState.STARTING,
            target=RunLifecycleState.RECOVERING,
            at=at,
            detail=detail,
        )

    def mark_ready(self, *, at: datetime, detail: str = "runtime ready") -> RunLifecycleSnapshot:
        return self.transition(
            expected=(
                RunLifecycleState.STARTING,
                RunLifecycleState.RECOVERING,
                RunLifecycleState.DEGRADED,
            ),
            target=RunLifecycleState.READY,
            at=at,
            detail=detail,
        )

    def mark_degraded(self, *, at: datetime, detail: str) -> RunLifecycleSnapshot:
        return self.transition(
            expected=(
                RunLifecycleState.STARTING,
                RunLifecycleState.RECOVERING,
                RunLifecycleState.READY,
            ),
            target=RunLifecycleState.DEGRADED,
            at=at,
            detail=detail,
        )

    def begin_drain(self, *, at: datetime, detail: str = "shutdown drain") -> RunLifecycleSnapshot:
        return self.transition(
            expected=(RunLifecycleState.READY, RunLifecycleState.DEGRADED),
            target=RunLifecycleState.DRAINING,
            at=at,
            detail=detail,
        )

    def begin_stop(self, *, at: datetime, detail: str = "shutdown requested") -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.STOPPING:
            return current
        return self.transition(
            expected=(
                RunLifecycleState.STARTING,
                RunLifecycleState.RECOVERING,
                RunLifecycleState.READY,
                RunLifecycleState.DEGRADED,
                RunLifecycleState.DRAINING,
                RunLifecycleState.FAILED,
            ),
            target=RunLifecycleState.STOPPING,
            at=at,
            detail=detail,
        )

    def mark_stopped(self, *, at: datetime, detail: str = "runtime stopped") -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.STOPPED:
            return current
        return self.transition(
            expected=(RunLifecycleState.STOPPING, RunLifecycleState.FAILED, RunLifecycleState.FENCED),
            target=RunLifecycleState.STOPPED,
            at=at,
            detail=detail,
        )

    def mark_failed(self, *, at: datetime, detail: str) -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.FAILED:
            return current
        if current.state is RunLifecycleState.FENCED:
            return current
        return self.transition(
            expected=current.state,
            target=RunLifecycleState.FAILED,
            at=at,
            detail=detail,
        )

    def mark_fenced(
        self,
        *,
        at: datetime,
        detail: str,
        owner_id: str | None = None,
        epoch: int | None = None,
    ) -> RunLifecycleSnapshot:
        current = self.current()
        if current.state is RunLifecycleState.FENCED:
            return current
        return self.transition(
            expected=current.state,
            target=RunLifecycleState.FENCED,
            at=at,
            detail=detail,
            owner_id=owner_id,
            epoch=epoch,
        )

    def events(self) -> tuple[tuple[int, str, str, str, str, str | None, int | None], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT generation, from_state, to_state, occurred_at,
                           detail, owner_id, epoch
                    FROM run_lifecycle_events
                    ORDER BY event_id
                    """
                )
            )
