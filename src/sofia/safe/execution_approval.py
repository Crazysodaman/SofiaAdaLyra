from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from sofia.safe.audit import AuditChain
from sofia.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

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
    # A one-time grant must bind bounded, finite JSON arguments exactly.
    # Python's default NaN/Infinity spellings are NOT portable JSON and
    # must never become a cross-language approval fingerprint.
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > 64_000:
        raise ValueError("approved execution request exceeds 64-KiB bound")
    return sha256(encoded).hexdigest()


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
        # Approval records are operator statements, not a string that can
        # be impersonated by a downstream handler or recovered model output.
        if self.approved_by != "Sparks":
            raise PermissionError(
                "only the independently authenticated owner can approve execution"
            )
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
        self._guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        with closing(self._connect()) as db, db:
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
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS safe_execution_owner_auth_binding (
                    authentication_event_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    bound_at TEXT NOT NULL,
                    FOREIGN KEY(approval_id) REFERENCES safe_execution_approval(approval_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        """Never manufacture a new approval/audit authority after state loss."""
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def record(
        self, approval: ExecutionApproval, *,
        authentication_event_id: str | None = None,
    ) -> None:
        if not isinstance(approval, ExecutionApproval):
            raise TypeError("approval must be an ExecutionApproval")
        if approval.approved_by != "Sparks":
            raise PermissionError("non-owner execution approval denied")
        protected = (
            capability_permission_policy(approval.capability).level
            >= PermissionLevel.PROTECTED
        )
        if protected and not authentication_event_id:
            raise PermissionError(
                "protected execution requires freshly verified owner FIDO2 authentication"
            )
        if authentication_event_id is not None and (
            not isinstance(authentication_event_id, str)
            or not authentication_event_id.startswith("owner-webauthn:")
            or len(authentication_event_id) != len("owner-webauthn:") + 64
        ):
            raise PermissionError("invalid owner authentication event identity")
        with closing(self._connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            if authentication_event_id is not None:
                # A signed assertion was verified through the canonical
                # owner_webauthn path; link it exactly once to this approval.
                # Do not accept a submitted actor label or guessed event ID.
                digest = authentication_event_id.partition(":")[2]
                row = db.execute(
                    "SELECT ch.action_fingerprint,ch.consumed_at,cr.credential_kind "
                    "FROM safe_owner_challenge ch JOIN safe_owner_credential cr "
                    "ON cr.credential_id=ch.credential_id "
                    "JOIN safe_audit_event au ON au.event_id=? "
                    "WHERE ch.challenge_digest=? "
                    "AND au.event_type='owner.webauthn.verified'",
                    (authentication_event_id, digest),
                ).fetchone()
                if row is None or row["consumed_at"] is None:
                    raise PermissionError("owner authentication evidence unavailable")
                if row["action_fingerprint"] != approval.request_fingerprint:
                    raise PermissionError("authenticated action fingerprint mismatch")
                verified_at = datetime.fromisoformat(row["consumed_at"])
                approval_time = approval.approved_at.astimezone(timezone.utc)
                if not verified_at <= approval_time <= verified_at + timedelta(seconds=120):
                    raise PermissionError("owner verification is stale or from the future")
                if protected and row["credential_kind"] != "security_key":
                    raise PermissionError("protected execution requires enrolled security key")
                used = db.execute(
                    "SELECT 1 FROM safe_execution_owner_auth_binding "
                    "WHERE authentication_event_id=?",
                    (authentication_event_id,),
                ).fetchone()
                if used is not None:
                    raise PermissionError("owner authentication already bound to approval")
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
            if authentication_event_id is not None:
                db.execute(
                    "INSERT INTO safe_execution_owner_auth_binding "
                    "(authentication_event_id,approval_id,bound_at) VALUES(?,?,?)",
                    (authentication_event_id, approval.approval_id, approval_time.isoformat()),
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

    def active_capabilities(
        self,
        *,
        now: datetime,
    ) -> tuple[str, ...]:
        """Return active unconsumed Sparks-approved capability names."""
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            rows = db.execute(
                """
                SELECT capability, approved_by, approved_at, expires_at
                FROM safe_execution_approval
                WHERE consumed_at IS NULL
                ORDER BY capability, approved_at
                """
            ).fetchall()
        capabilities = []
        for row in rows:
            if row["approved_by"] != "Sparks":
                continue
            try:
                approved_at = datetime.fromisoformat(row["approved_at"])
                expires_at = datetime.fromisoformat(row["expires_at"])
            except (TypeError, ValueError):
                continue
            if (
                approved_at.tzinfo is None
                or approved_at.utcoffset() is None
                or expires_at.tzinfo is None
                or expires_at.utcoffset() is None
            ):
                continue
            if approved_at.astimezone(timezone.utc) <= moment < expires_at.astimezone(timezone.utc):
                capability = str(row["capability"])
                if capability not in capabilities:
                    capabilities.append(capability)
        return tuple(capabilities)

    def matches_unconsumed(
        self,
        *,
        approval_id: str | None,
        capability: str,
        parameters: dict,
        now: datetime,
    ) -> bool:
        """Check exact operator authorization without consuming its one-use receipt.

        This is a preflight for the host capability gate, not execution
        authority by itself. The effect handler must still atomically consume
        the approval before performing the side effect.
        """
        if not isinstance(approval_id, str) or not approval_id.strip():
            return False
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return False
        try:
            expected = execution_fingerprint(capability, parameters)
        except (TypeError, ValueError):
            return False
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            row = db.execute(
                """
                SELECT capability, request_fingerprint, approved_by,
                       approved_at, expires_at, consumed_at
                FROM safe_execution_approval
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        if row is None or row["consumed_at"] is not None:
            return False
        try:
            approval = ExecutionApproval(
                approval_id=approval_id,
                capability=row["capability"],
                request_fingerprint=row["request_fingerprint"],
                approved_by=row["approved_by"],
                approved_at=datetime.fromisoformat(row["approved_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
            )
        except (PermissionError, TypeError, ValueError):
            return False
        moment = now.astimezone(timezone.utc)
        return (
            approval.capability == capability
            and approval.request_fingerprint == expected
            and approval.approved_at.astimezone(timezone.utc) <= moment
            and moment < approval.expires_at.astimezone(timezone.utc)
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

        with closing(self._connect()) as db, db:
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
            if approval.approved_by != "Sparks":
                raise PermissionError("execution approval was not granted by the owner")
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
