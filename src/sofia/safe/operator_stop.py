from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.safe.audit import AuditChain
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


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
        self._guard=CanonicalSQLiteGuard(self.path)
        # Reuse SAFE's append-only hash chain; do not create a competing
        # operator-history ledger or rely on the overwritten current row.
        self.audit = AuditChain(self.path)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            # SQLite DDL alone does not start a Python-managed transaction.
            # Reserve an explicit write transaction before schema creation so
            # a refused recovery cannot leave an empty table behind.
            db.execute("BEGIN IMMEDIATE")
            existed = db.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='safe_operator_stop'"
            ).fetchone() is not None
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
                # A missing row in an already-initialized authority is
                # corruption, not permission to silently clear a STOP. Even
                # a dropped table cannot erase earlier audited STOP history.
                previously_used = db.execute(
                    "SELECT 1 FROM safe_audit_event "
                    "WHERE event_type LIKE 'operator.stop.%' LIMIT 1"
                ).fetchone() is not None
                if existed or previously_used:
                    raise RuntimeError(
                        "operator stop state missing after initialization; "
                        "canonical recovery and owner review required"
                    )
                db.execute("""
                    INSERT INTO safe_operator_stop(
                        singleton,active,updated_at,updated_by,reason
                    ) VALUES(1,0,?,?,?)
                """,(
                    datetime.now(timezone.utc).isoformat(),
                    "system:bootstrap",
                    "initial inactive operator stop",
                ))

    def _connect(self) -> sqlite3.Connection:
        # Failure to find the canonical stop ledger is a STOP condition,
        # not permission to create another unlocked operator authority.
        return self._guard.connect(timeout=10)

    def current(self)->OperatorStopState:
        with closing(self._connect()) as db, db:
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
        approval_id:str|None=None,
        expected_updated_at:str|None=None,
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
        if not active:
            # The emergency PAUSE remains immediate. Only lifting that stop
            # requires a new, exact, FIDO2-authenticated SAFE approval.
            # A username literal or Tk confirmation cannot resume autonomy.
            from sofia.safe.execution_approval import ExecutionApprovalVerifier
            verifier = ExecutionApprovalVerifier(self.path)
            if not approval_id or not expected_updated_at:
                raise PermissionError(
                    "operator resume requires FIDO2 approval bound to exact stop revision"
                )
            # Reject a changed stop even before consuming the one-time owner
            # approval. A second check under BEGIN IMMEDIATE closes the race.
            observed = self.current()
            if observed.updated_at.astimezone(timezone.utc).isoformat() != expected_updated_at:
                raise PermissionError("operator stop changed since resume was requested")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not active:
                # Approval receipt, exact state revision and stop mutation are
                # now one canonical SQLite commit or one shared rollback.
                verifier.consume(
                    approval_id=approval_id,
                    capability="operator.stop.resume",
                    parameters={
                        "active": False, "reason": reason.strip(),
                        "expected_updated_at": expected_updated_at,
                    },
                    now=moment,
                    _transaction_db=db,
                )
            previous = db.execute(
                "SELECT active,updated_at FROM safe_operator_stop WHERE singleton=1"
            ).fetchone()
            if previous is None:
                raise RuntimeError("operator stop row missing; cannot audit transition")
            if not active and previous[1] != expected_updated_at:
                raise PermissionError("new operator stop revision superseded resume approval")
            # The ISO timestamp is also the compare-and-swap revision used
            # by signed resume requests. Two operator STOPs inside one clock
            # tick (or across a backwards host-clock adjustment) must NEVER
            # reuse a revision and revive a stale signed resume.
            # Keep real wall-clock time in the append-only audit event.
            previous_revision = datetime.fromisoformat(previous[1])
            if previous_revision.tzinfo is None or previous_revision.utcoffset() is None:
                raise RuntimeError("invalid operator STOP revision; fail closed")
            previous_revision = previous_revision.astimezone(timezone.utc)
            requested_revision = moment.astimezone(timezone.utc)
            revision = (
                requested_revision
                if requested_revision > previous_revision
                else previous_revision + timedelta(microseconds=1)
            )
            changed = db.execute("""
                UPDATE safe_operator_stop
                SET active=?,updated_at=?,updated_by=?,reason=?
                WHERE singleton=1
            """,(
                1 if active else 0,
                revision.isoformat(),
                updated_by,
                reason.strip(),
            ))
            if changed.rowcount != 1:
                raise RuntimeError("operator stop row missing; refusal to imply a successful stop")
            self.audit.append_in_transaction(
                db,
                actor_id=updated_by,
                event_type=(
                    "operator.stop.activated"
                    if active else "operator.stop.cleared"
                ),
                payload={
                    "previously_active": bool(previous[0]),
                    "active": active,
                    "reason": reason.strip(),
                },
                occurred_at=moment,
                event_id=f"operator-stop:{uuid4()}",
            )
            db.commit()
        return self.current()
