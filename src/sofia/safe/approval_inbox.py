"""Durable SAFE request inbox. A queued request is never an owner approval.

Only the existing supervised, user-verified WebAuthn browser can create an
execution receipt. Notification delivery and recovery never execute effects.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Callable
from uuid import uuid4

from sofia.safe.audit import AuditChain
from sofia.safe.execution_approval import ExecutionApprovalVerifier, execution_fingerprint
from sofia.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

REQUEST_TTL = timedelta(hours=24)
CHALLENGE_SECONDS = 90
SIGNED_APPROVAL_SECONDS = 600
REVIEW_LEASE = timedelta(minutes=3)

_TERMINAL = frozenset({"denied", "expired", "cancelled"})


def _time(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return moment.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class InboxRequest:
    request_id: str
    capability: str
    parameters: dict
    fingerprint: str
    status: str
    created_at: datetime
    expires_at: datetime
    approval_id: str | None
    approval_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class InboxNotification:
    event_id: int
    request_id: str
    event_type: str
    capability: str
    created_at: datetime


class ApprovalInbox:
    """Canonical-state inbox; no signer, autonomous executor, or new DB writer."""

    def __init__(self, state_path: Path | str):
        self.path = Path(state_path)
        self.guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        self.approvals = ExecutionApprovalVerifier(self.path)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_async_approval_request (
                    request_id TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                      ('pending','reviewing','approved','denied','cancelled','expired')),
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    review_token TEXT,
                    review_expires_at TEXT,
                    approval_id TEXT UNIQUE,
                    approval_expires_at TEXT,
                    CHECK ((approval_id IS NULL AND approval_expires_at IS NULL)
                           OR (approval_id IS NOT NULL AND approval_expires_at IS NOT NULL))
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_async_approval_notification (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT,
                    FOREIGN KEY(request_id) REFERENCES safe_async_approval_request(request_id)
                )
            """)
        # Startup reconciliation is safe: it changes only inbox metadata,
        # never replays an approved external operation.
        self.recover()

    def _connect(self) -> sqlite3.Connection:
        db = self.guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _event(self, db: sqlite3.Connection, row: sqlite3.Row, kind: str,
               now: datetime, actor: str = "system:approval-inbox") -> None:
        db.execute(
            "INSERT INTO safe_async_approval_notification "
            "(request_id,event_type,capability,created_at) VALUES(?,?,?,?)",
            (row["request_id"], kind, row["capability"], now.isoformat()),
        )
        self.audit.append_in_transaction(
            db, actor_id=actor, event_type="owner.approval_inbox." + kind,
            payload={"request_id": row["request_id"], "capability": row["capability"],
                     "fingerprint": row["fingerprint"]},
            occurred_at=now, event_id="approval-inbox:" + str(uuid4()),
        )

    @staticmethod
    def _as_request(row: sqlite3.Row) -> InboxRequest:
        return InboxRequest(
            request_id=row["request_id"], capability=row["capability"],
            parameters=json.loads(row["parameters_json"]),
            fingerprint=row["fingerprint"], status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            approval_id=row["approval_id"],
            approval_expires_at=(datetime.fromisoformat(row["approval_expires_at"])
                                 if row["approval_expires_at"] else None),
        )

    def create(self, capability: str, parameters: dict, *,
               now: datetime | None = None) -> InboxRequest:
        """Request permission, never grant it. Unknown actions fail closed as protected."""
        moment = _time(now)
        if capability_permission_policy(capability).level < PermissionLevel.REVERSIBLE_SCOPED:
            raise ValueError("low-risk actions do not need queued owner FIDO2 authorization")
        if isinstance(parameters, dict) and "approval_id" in parameters:
            raise ValueError("approval_id cannot be supplied inside queued parameters")
        fingerprint = execution_fingerprint(capability, parameters)
        # Round-trip the exact immutable JSON value, not mutable caller-owned data.
        encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 64000:
            raise ValueError("approval parameters exceed size limit")
        identifier = str(uuid4())
        until = moment + REQUEST_TTL
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            active_count = db.execute(
                "SELECT count(*) FROM safe_async_approval_request "
                "WHERE status IN ('pending','reviewing') AND expires_at > ?",
                (moment.isoformat(),),
            ).fetchone()[0]
            if active_count >= 256:
                raise PermissionError("owner approval inbox is full; review existing requests")
            db.execute(
                "INSERT INTO safe_async_approval_request "
                "(request_id,capability,parameters_json,fingerprint,status,created_at,expires_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (identifier, capability, encoded, fingerprint, "pending",
                 moment.isoformat(), until.isoformat()),
            )
            row = db.execute("SELECT * FROM safe_async_approval_request WHERE request_id=?",
                             (identifier,)).fetchone()
            self._event(db, row, "requested", moment)
        return self._as_request(row)

    def get(self, request_id: str) -> InboxRequest:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM safe_async_approval_request WHERE request_id=?",
                             (request_id,)).fetchone()
        if row is None:
            raise KeyError("approval inbox request not found")
        return self._as_request(row)

    def list_requests(self, *, status: str | None = None,
                      limit: int = 100) -> tuple[InboxRequest, ...]:
        if status is not None and status not in (
            "pending", "reviewing", "approved", "denied", "cancelled", "expired"
        ):
            raise ValueError("invalid inbox status")
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        with closing(self._connect()) as db:
            if status is None:
                rows = db.execute(
                    "SELECT * FROM safe_async_approval_request "
                    "ORDER BY created_at DESC,request_id DESC LIMIT ?", (limit,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM safe_async_approval_request WHERE status=? "
                    "ORDER BY created_at DESC,request_id DESC LIMIT ?", (status, limit),
                ).fetchall()
        return tuple(self._as_request(r) for r in rows)

    def recover(self, *, now: datetime | None = None) -> int:
        """Reconcile expired requests and crashed reviews; NEVER replay effects."""
        moment = _time(now)
        changed = 0
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM safe_async_approval_request WHERE status IN "
                "('pending','reviewing','approved') ORDER BY created_at,request_id"
            ).fetchall()
            for row in rows:
                if row["expires_at"] <= moment.isoformat() and row["status"] != "approved":
                    next_status = "expired"
                elif row["status"] == "reviewing" and (
                    row["review_expires_at"] is None
                    or row["review_expires_at"] <= moment.isoformat()
                ):
                    next_status = "pending"
                elif row["status"] == "approved" and (
                    not row["approval_expires_at"]
                    or row["approval_expires_at"] <= moment.isoformat()
                ):
                    next_status = "expired"
                else:
                    continue
                db.execute(
                    "UPDATE safe_async_approval_request SET status=?,"
                    "review_token=NULL,review_expires_at=NULL WHERE request_id=?",
                    (next_status, row["request_id"]),
                )
                self._event(db, row, "review_recovered" if next_status == "pending"
                            else "expired", moment)
                changed += 1
        return changed

    def _claim(self, request_id: str, *, now: datetime) -> tuple[InboxRequest, str]:
        token = secrets.token_urlsafe(32)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM safe_async_approval_request WHERE request_id=?",
                             (request_id,)).fetchone()
            if row is None or row["status"] != "pending":
                raise PermissionError("request not pending; recovery or new request required")
            if row["expires_at"] <= now.isoformat():
                raise PermissionError("request expired")
            updated = db.execute(
                "UPDATE safe_async_approval_request SET status='reviewing',"
                "review_token=?,review_expires_at=? "
                "WHERE request_id=? AND status='pending'",
                (token, (now + REVIEW_LEASE).isoformat(), request_id),
            )
            if updated.rowcount != 1:
                raise PermissionError("another reviewer claimed the request")
        return self._as_request(row), token

    def _release_failed_review(self, request_id: str, token: str) -> None:
        # Never resurrect a denied/cancelled/expired or newer review.
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE safe_async_approval_request SET status='pending',"
                "review_token=NULL,review_expires_at=NULL "
                "WHERE request_id=? AND status='reviewing' AND review_token=?",
                (request_id, token),
            )

    def approve_attended(self, request_id: str, *, credential_id: str,
                         open_browser=None) -> InboxRequest:
        """Explicit interactive Windows owner call, not available as a model tool.

        The existing browser verifies Windows SID, owner presence, user
        verification, exact action and physical key for protected capabilities.
        A new 90-second challenge is issued only after the owner starts review.
        """
        from sofia.safe.owner_enroll_browser import require_owner_windows_account
        from sofia.safe.owner_browser import authorize_exact_action

        require_owner_windows_account(self.path)
        claimed, token = self._claim(request_id, now=_time())
        approval = None
        try:
            approval = authorize_exact_action(
                self.path, capability=claimed.capability,
                parameters=claimed.parameters, credential_id=credential_id,
                expires_seconds=SIGNED_APPROVAL_SECONDS,
                timeout_seconds=CHALLENGE_SECONDS,
                open_browser=open_browser,
            )
            moment = _time()
            if (approval.request_fingerprint != claimed.fingerprint
                or approval.capability != claimed.capability
                or approval.expires_at > approval.approved_at
                   + timedelta(seconds=SIGNED_APPROVAL_SECONDS)
                or not self.approvals.matches_unconsumed(
                    approval_id=approval.approval_id, capability=claimed.capability,
                    parameters=claimed.parameters, now=moment
                )):
                raise PermissionError("signed receipt does not match inbox action")
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM safe_async_approval_request WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if (row is None or row["status"] != "reviewing"
                    or row["review_token"] != token
                    or row["review_expires_at"] <= moment.isoformat()
                    or row["expires_at"] <= moment.isoformat()):
                    raise PermissionError("review cancelled, superseded or expired")
                db.execute(
                    "UPDATE safe_async_approval_request SET status='approved',"
                    "review_token=NULL,review_expires_at=NULL,"
                    "approval_id=?,approval_expires_at=? WHERE request_id=?",
                    (approval.approval_id, approval.expires_at.isoformat(), request_id),
                )
                self._event(db, row, "approved", moment, actor="Sparks")
            return self.get(request_id)
        except BaseException:
            # If a legitimate signed receipt was created but the review lease
            # was denied, expired, or lost, invalidate it rather than leaving
            # an unattached unconsumed approval reachable in SAFE.
            if approval is not None:
                try:
                    self.approvals.consume(
                        approval_id=approval.approval_id,
                        capability=claimed.capability,
                        parameters=claimed.parameters, now=_time(),
                    )
                except (OSError, RuntimeError, PermissionError, ValueError):
                    # It may already be consumed or past expiry. Never turn
                    # a failed inbox finalization into execution authority.
                    pass
            self._release_failed_review(request_id, token)
            raise

    def deny_attended(self, request_id: str) -> InboxRequest:
        """Owner may reject pending or in-flight review without granting a key."""
        from sofia.safe.owner_enroll_browser import require_owner_windows_account
        require_owner_windows_account(self.path)
        moment = _time()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM safe_async_approval_request WHERE request_id=?",
                             (request_id,)).fetchone()
            if row is None or row["status"] not in ("pending", "reviewing"):
                raise PermissionError("only unapproved requests may be denied")
            db.execute(
                "UPDATE safe_async_approval_request SET status='denied',"
                "review_token=NULL,review_expires_at=NULL WHERE request_id=?",
                (request_id,),
            )
            self._event(db, row, "denied", moment, actor="Sparks")
        return self.get(request_id)

    def approved_receipt(self, request_id: str, *, capability: str,
                         parameters: dict, now: datetime | None = None) -> str:
        """Return only an authenticated, live, exact receipt for host preflight.

        Does not execute or consume the receipt; host effect code must still call
        ExecutionApprovalVerifier.consume with its ordinary safety gates.
        """
        moment = _time(now)
        item = self.get(request_id)
        if item.status != "approved" or item.approval_expires_at is None:
            raise PermissionError("request has no live signed approval")
        if moment >= item.approval_expires_at:
            raise PermissionError("signed approval expired")
        if isinstance(parameters, dict) and "approval_id" in parameters:
            raise PermissionError("caller cannot substitute an approval_id parameter")
        if item.capability != capability or item.fingerprint != execution_fingerprint(
            capability, parameters
        ):
            raise PermissionError("requested action differs from signed action")
        if not self.approvals.matches_unconsumed(
            approval_id=item.approval_id, capability=capability,
            parameters=parameters, now=moment,
        ):
            raise PermissionError("signed owner receipt invalid or consumed")
        return item.approval_id

    def notifications(self, *, limit: int = 50) -> tuple[InboxNotification, ...]:
        """Trusted local owner-channel adapter reads an at-least-once outbox."""
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("notification limit must be 1..100")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM safe_async_approval_notification "
                "WHERE delivered_at IS NULL ORDER BY event_id LIMIT ?", (limit,),
            ).fetchall()
        return tuple(InboxNotification(
            event_id=r["event_id"], request_id=r["request_id"],
            event_type=r["event_type"], capability=r["capability"],
            created_at=datetime.fromisoformat(r["created_at"])
        ) for r in rows)

    def deliver_notifications(self, send: Callable[[InboxNotification], None], *,
                              limit: int = 50) -> int:
        """Owner-scoped sender supplied by host, never a model-picked URL/user.

        Crash between sending and ack may redeliver: receivers must de-duplicate
        by event_id. No notifications are marked delivered on transport error.
        """
        if not callable(send):
            raise TypeError("trusted notification sender required")
        count = 0
        for note in self.notifications(limit=limit):
            send(note)
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute(
                    "UPDATE safe_async_approval_notification SET delivered_at=? "
                    "WHERE event_id=? AND delivered_at IS NULL",
                    (_time().isoformat(), note.event_id),
                )
                count += changed.rowcount
        return count
