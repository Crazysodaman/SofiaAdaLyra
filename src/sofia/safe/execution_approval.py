from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from sofia.safe.audit import AuditChain

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def execution_fingerprint(
    capability: str,
    parameters: dict,
) -> str:
    if not isinstance(capability, str) or not capability.strip():
        raise ValueError("capability must be nonempty")
    if not isinstance(parameters, dict):
        raise TypeError("parameters must be a dict")
    filtered = {
        key: value
        for key, value in parameters.items()
        if key != "approval_id"
    }
    document = {
        "capability": capability,
        "parameters": filtered,
    }
    return sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionApproval:
    approval_id: str
    capability: str
    request_fingerprint: str
    approved_by: str
    approved_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("approval_id", "approved_by"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be nonempty")
        if re.fullmatch(r"[0-9a-f]{64}", self.request_fingerprint) is None:
            raise ValueError("request_fingerprint must be lowercase SHA-256")
        for name in ("approved_at", "expires_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise TypeError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at <= self.approved_at:
            raise ValueError("approval expiry must follow approval time")


class ExecutionApprovalVerifier:
    """Durable one-time exact approval store for local side-effect capabilities."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = AuditChain(self.path)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS safe_execution_approval (
                    approval_id TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                )
                """
            )

    def record(self, approval: ExecutionApproval) -> None:
        if not isinstance(approval, ExecutionApproval):
            raise TypeError("approval must be an ExecutionApproval")
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO safe_execution_approval (
                    approval_id,
                    capability,
                    request_fingerprint,
                    approved_by,
                    approved_at,
                    expires_at,
                    consumed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    approval.approval_id,
                    approval.capability,
                    approval.request_fingerprint,
                    approval.approved_by,
                    approval.approved_at.astimezone(timezone.utc).isoformat(),
                    approval.expires_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=approval.approved_by,
                event_type="execution.approval.recorded",
                payload={
                    "approval_id": approval.approval_id,
                    "capability": approval.capability,
                    "request_fingerprint": approval.request_fingerprint,
                    "expires_at": approval.expires_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                },
                occurred_at=approval.approved_at,
                event_id=f"execution-approval-recorded:{approval.approval_id}",
            )

    def consume(
        self,
        *,
        approval_id: str,
        capability: str,
        parameters: dict,
        now: datetime,
    ) -> ExecutionApproval:
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise PermissionError("side-effect capability requires approval_id")
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be nonempty")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        expected = execution_fingerprint(capability, parameters)

        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT capability, request_fingerprint, approved_by,
                       approved_at, expires_at, consumed_at
                FROM safe_execution_approval
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("execution approval does not exist")
            if row["consumed_at"] is not None:
                raise PermissionError("execution approval was already consumed")

            approval = ExecutionApproval(
                approval_id=approval_id,
                capability=row["capability"],
                request_fingerprint=row["request_fingerprint"],
                approved_by=row["approved_by"],
                approved_at=datetime.fromisoformat(row["approved_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
            )
            if moment < approval.approved_at.astimezone(timezone.utc):
                raise PermissionError("execution approval is not active yet")
            if moment >= approval.expires_at.astimezone(timezone.utc):
                raise PermissionError("execution approval expired")
            if approval.capability != capability:
                raise PermissionError("execution approval is for another capability")
            if approval.request_fingerprint != expected:
                raise PermissionError("execution approval parameters do not match")

            changed = db.execute(
                """
                UPDATE safe_execution_approval
                SET consumed_at = ?
                WHERE approval_id = ? AND consumed_at IS NULL
                """,
                (moment.isoformat(), approval_id),
            )
            if changed.rowcount != 1:
                raise PermissionError("execution approval could not be consumed")
            self.audit.append_in_transaction(
                db,
                actor_id=approval.approved_by,
                event_type="execution.approval.consumed",
                payload={
                    "approval_id": approval.approval_id,
                    "capability": approval.capability,
                    "request_fingerprint": approval.request_fingerprint,
                },
                occurred_at=moment,
                event_id=f"execution-approval-consumed:{approval.approval_id}",
            )
            db.commit()
            return approval
