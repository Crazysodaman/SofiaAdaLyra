from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.dev.approval import DevApproval, DevOperation, dev_request_fingerprint
from sofia.safe.audit import AuditChain


class DevApprovalVerifier:
    """
    Durable, exact-parameter DEV authorization verifier.

    The approval store is populated only by an operator-facing path. Cognition
    can reference an approval_id but cannot mint or widen an approval.
    """

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = AuditChain(self.path)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS safe_dev_approval (
                        approval_id TEXT PRIMARY KEY,
                        operation TEXT NOT NULL,
                        proposal_id TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        approved_by TEXT NOT NULL,
                        approved_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        consumed_at TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, approval: DevApproval) -> None:
        if not isinstance(approval, DevApproval):
            raise TypeError("approval must be a DevApproval")
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO safe_dev_approval (
                        approval_id, operation, proposal_id,
                        request_fingerprint, approved_by,
                        approved_at, expires_at, consumed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        approval.approval_id,
                        approval.operation.value,
                        approval.proposal_id,
                        approval.request_fingerprint,
                        approval.approved_by,
                        approval.approved_at.astimezone(timezone.utc).isoformat(),
                        approval.expires_at.astimezone(timezone.utc).isoformat(),
                    ),
                )
                self.audit.append_in_transaction(
                    db,
                    actor_id=approval.approved_by,
                    event_type="dev.approval.recorded",
                    payload={
                        "approval_id": approval.approval_id,
                        "operation": approval.operation.value,
                        "proposal_id": approval.proposal_id,
                        "request_fingerprint": approval.request_fingerprint,
                        "expires_at": approval.expires_at.astimezone(
                            timezone.utc
                        ).isoformat(),
                    },
                    occurred_at=approval.approved_at,
                    event_id=f"dev-approval-recorded:{approval.approval_id}",
                )

    def consume(
        self,
        *,
        approval_id: str,
        operation: DevOperation,
        proposal_id: str,
        parameters: dict,
        now: datetime,
    ) -> DevApproval:
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise PermissionError("DEV mutation requires approval_id")
        if not isinstance(operation, DevOperation):
            raise TypeError("operation must be a DevOperation")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be nonempty")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        expected = dev_request_fingerprint(operation, parameters)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT operation, proposal_id, request_fingerprint,
                           approved_by, approved_at, expires_at, consumed_at
                    FROM safe_dev_approval
                    WHERE approval_id = ?
                    """,
                    (approval_id,),
                ).fetchone()
                if row is None:
                    raise PermissionError("DEV approval does not exist")
                if row[6] is not None:
                    raise PermissionError("DEV approval was already consumed")

                approval = DevApproval(
                    approval_id=approval_id,
                    operation=DevOperation(row[0]),
                    proposal_id=row[1],
                    request_fingerprint=row[2],
                    approved_by=row[3],
                    approved_at=datetime.fromisoformat(row[4]),
                    expires_at=datetime.fromisoformat(row[5]),
                )
                if moment < approval.approved_at.astimezone(timezone.utc):
                    raise PermissionError("DEV approval is not active yet")
                if moment >= approval.expires_at.astimezone(timezone.utc):
                    raise PermissionError("DEV approval expired")
                if approval.operation is not operation:
                    raise PermissionError("DEV approval is for another operation")
                if approval.proposal_id != proposal_id:
                    raise PermissionError("DEV approval is for another proposal")
                if approval.request_fingerprint != expected:
                    raise PermissionError("DEV approval parameters do not match")

                changed = db.execute(
                    """
                    UPDATE safe_dev_approval
                    SET consumed_at = ?
                    WHERE approval_id = ? AND consumed_at IS NULL
                    """,
                    (moment.isoformat(), approval_id),
                )
                if changed.rowcount != 1:
                    raise PermissionError("DEV approval could not be consumed")
                self.audit.append_in_transaction(
                    db,
                    actor_id=approval.approved_by,
                    event_type="dev.approval.consumed",
                    payload={
                        "approval_id": approval.approval_id,
                        "operation": approval.operation.value,
                        "proposal_id": approval.proposal_id,
                        "request_fingerprint": approval.request_fingerprint,
                    },
                    occurred_at=moment,
                    event_id=f"dev-approval-consumed:{approval.approval_id}",
                )
                return approval
