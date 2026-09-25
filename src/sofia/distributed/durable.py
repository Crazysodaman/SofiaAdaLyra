"""Durable local authorization and replay/audit boundary for remote operations.

This is NOT a network transport, peer authentication, or human-approval UI.
The caller must provision grants through a trusted human-controlled path and
supply a transport that independently authenticates its remote peer.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.distributed.authorization import RemoteAuthorization, RemoteGrant
from sofia.distributed.capabilities import _aware
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.operations import (
    DistributedGateway, RemoteOperationDenied, RemoteOperationRequest,
    RemoteOperationResult, RemoteOperationUncertain, RemoteTransport,
)


def _utc(value: datetime) -> str:
    _aware(value, "timestamp")
    return value.astimezone(timezone.utc).isoformat()


def _connect(path: Path | str) -> sqlite3.Connection:
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("An on-disk SQLite path is required.")
    if str(path) == ":memory:":
        raise ValueError("An in-memory database cannot provide durable security state.")
    target = Path(path)
    if not target.parent.exists():
        raise FileNotFoundError("The security database parent directory must exist.")
    connection = sqlite3.connect(target, timeout=3.0)
    connection.execute("PRAGMA busy_timeout = 3000")
    return connection


class DurableRemoteAuthorization(RemoteAuthorization):
    """Explicit exact-scope grants persisted across runtime restarts.

    Creation is an administrative API, NEVER a parser for model/chat text.
    Expired grants remain expired; revoked IDs cannot be reused or renewed.
    """

    def __init__(self, state_path: Path | str) -> None:
        super().__init__()
        self._db = _connect(state_path)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS remote_standing_grant (
                grant_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                operation TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))
            )
        """)
        self._db.commit()

    def add_approved_grant(self, grant: RemoteGrant) -> None:
        if not isinstance(grant, RemoteGrant):
            raise TypeError("grant must be a RemoteGrant.")
        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO remote_standing_grant
                       (grant_id, node_id, capability, operation, approved_by, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(grant.grant_id), str(grant.node_id), grant.capability,
                     grant.operation, grant.approved_by, _utc(grant.expires_at)),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Grant ID already exists; implicit renewal is forbidden.") from exc

    def revoke(self, grant_id: UUID) -> None:
        if not isinstance(grant_id, UUID):
            raise TypeError("grant_id must be a UUID.")
        with self._db:
            self._db.execute(
                "UPDATE remote_standing_grant SET revoked = 1 WHERE grant_id = ?",
                (str(grant_id),),
            )

    def revoke_node(self, node_id: UUID) -> int:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID.")
        with self._db:
            cursor = self._db.execute(
                "UPDATE remote_standing_grant SET revoked = 1 WHERE node_id = ? AND revoked = 0",
                (str(node_id),),
            )
        return cursor.rowcount

    def permits(self, grant_id: UUID, *, node_id: UUID, capability: str,
                operation: str, now: datetime) -> bool:
        _aware(now, "now")
        if not isinstance(grant_id, UUID) or not isinstance(node_id, UUID):
            return False
        row = self._db.execute(
            """SELECT node_id, capability, operation, expires_at, revoked
               FROM remote_standing_grant WHERE grant_id = ?""",
            (str(grant_id),),
        ).fetchone()
        if row is None:
            return False
        saved_node, saved_capability, saved_operation, expiry, revoked = row
        try:
            expires_at = datetime.fromisoformat(expiry)
            _aware(expires_at, "expires_at")
        except (ValueError, TypeError):
            return False
        return (revoked == 0 and saved_node == str(node_id)
                and saved_capability == capability and saved_operation == operation
                and now < expires_at)

    def close(self) -> None:
        self._db.close()


class DurableRemoteLedger:
    """Append-first request ledger. A reserved ID is never reusable.

    The reservation is committed before any transport operation. A crash can
    leave status='reserved'; this means UNKNOWN, never safe to retry.
    """

    _FINAL = frozenset({"denied_after_reserve", "reported_success",
                        "reported_failure", "reported_unknown", "uncertain"})

    def __init__(self, state_path: Path | str) -> None:
        self._db = _connect(state_path)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS remote_request_ledger (
                request_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                grant_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                operation TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        self._db.commit()

    def _insert(self, request: RemoteOperationRequest, *, now: datetime,
                status: str) -> None:
        if not isinstance(request, RemoteOperationRequest):
            raise TypeError("request must be a RemoteOperationRequest.")
        when = _utc(now)
        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO remote_request_ledger
                       (request_id, node_id, grant_id, capability, operation,
                        observed_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (str(request.request_id), str(request.node_id),
                     str(request.grant_id), request.capability, request.operation,
                     when, status),
                )
        except sqlite3.IntegrityError as exc:
            raise RemoteOperationDenied(
                "Duplicate durable request ID; never replay automatically."
            ) from exc

    def deny(self, request: RemoteOperationRequest, *, now: datetime) -> None:
        self._insert(request, now=now, status="denied")

    def reserve(self, request: RemoteOperationRequest, *, now: datetime) -> None:
        self._insert(request, now=now, status="reserved")

    def finalize(self, request_id: UUID, *, status: str) -> None:
        if not isinstance(request_id, UUID):
            raise TypeError("request_id must be a UUID.")
        if status not in self._FINAL:
            raise ValueError("Invalid final audit status.")
        with self._db:
            cursor = self._db.execute(
                """UPDATE remote_request_ledger SET status = ?
                   WHERE request_id = ? AND status = 'reserved'""",
                (status, str(request_id)),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Request has no pending durable reservation.")

    def status(self, request_id: UUID) -> str | None:
        if not isinstance(request_id, UUID):
            raise TypeError("request_id must be a UUID.")
        row = self._db.execute(
            "SELECT status FROM remote_request_ledger WHERE request_id = ?",
            (str(request_id),),
        ).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        self._db.close()


class DurableDistributedGateway:
    """Durable authorization and replay guard around the existing gateway.

    Supplying an insecure transport is still insecure. This class does not
    create network sockets, enroll nodes, or authorize commands via chat.
    """

    def __init__(self, transport: RemoteTransport,
                 authorization: DurableRemoteAuthorization,
                 ledger: DurableRemoteLedger, *,
                 max_inventory_age: timedelta) -> None:
        if not isinstance(authorization, DurableRemoteAuthorization):
            raise TypeError("Durable authorization is required.")
        if not isinstance(ledger, DurableRemoteLedger):
            raise TypeError("A durable request ledger is required.")
        self._authorization = authorization
        self._ledger = ledger
        self._gateway = DistributedGateway(
            transport, authorization, max_inventory_age=max_inventory_age,
        )

    def invoke(self, enrollment: NodeEnrollment, request: RemoteOperationRequest,
               *, now: datetime) -> RemoteOperationResult:
        _aware(now, "now")
        if not isinstance(enrollment, NodeEnrollment):
            raise TypeError("enrollment must be NodeEnrollment.")
        if not isinstance(request, RemoteOperationRequest):
            raise TypeError("request must be RemoteOperationRequest.")
        if (request.node_id != enrollment.node.node_id
                or not self._authorization.permits(
                    request.grant_id, node_id=request.node_id,
                    capability=request.capability, operation=request.operation,
                    now=now,
                )):
            self._ledger.deny(request, now=now)
            raise RemoteOperationDenied("Node mismatch or no active exact-scope grant.")
        self._ledger.reserve(request, now=now)
        try:
            result = self._gateway.invoke(enrollment, request, now=now)
        except RemoteOperationDenied:
            self._ledger.finalize(request.request_id, status="denied_after_reserve")
            raise
        except RemoteOperationUncertain:
            self._ledger.finalize(request.request_id, status="uncertain")
            raise
        except Exception as exc:
            # A caller may not safely infer that an external operation did not run.
            try:
                self._ledger.finalize(request.request_id, status="uncertain")
            finally:
                raise RemoteOperationUncertain(
                    "Remote outcome unknown; do not retry."
                ) from exc
        try:
            self._ledger.finalize(
                request.request_id, status=f"reported_{result.outcome.value.removeprefix('reported_')}",
            )
        except Exception as exc:
            raise RemoteOperationUncertain(
                "Remote result returned but durable audit update failed; do not retry."
            ) from exc
        return result
