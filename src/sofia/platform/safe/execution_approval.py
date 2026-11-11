from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.owner_webauthn import ensure_owner_webauthn_schema
from sofia.platform.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")

# Existing canonical owner identity, shared with the social principal contract.
# "Sparks" is retained only as the historical approval-record encoding. Neither
# reference is a credential: protected consumers still require durable proof.
OWNER_PRINCIPAL_ID = "person:sparks"
_OWNER_APPROVAL_REFERENCES = frozenset({OWNER_PRINCIPAL_ID, "Sparks"})


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
        # This constrains the owner-reference encoding only. The verifier,
        # not this constructible DTO, authenticates protected approval records.
        if self.approved_by not in _OWNER_APPROVAL_REFERENCES:
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

    @property
    def principal_id(self) -> str:
        """Canonical attribution, not proof that this DTO is authenticated.

        Only a successful verifier consumption authenticates an approval. The
        compatibility alias must never replace its action-bound credential.
        """
        return OWNER_PRINCIPAL_ID


class ExecutionApprovalVerifier:
    """Durable one-time exact approval store for local side-effect capabilities."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            ensure_owner_webauthn_schema(db)
            # Keep ordinary FIDO2 paths working when no owner secret has
            # ever been enrolled. Queries may reference these empty tables.
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_owner_secret (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    windows_sid TEXT NOT NULL,
                    salt BLOB NOT NULL,
                    verifier BLOB NOT NULL,
                    version INTEGER NOT NULL CHECK(version>0),
                    enrolled_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_owner_secret_proof (
                    proof_id TEXT PRIMARY KEY,
                    action_fingerprint TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
            """)
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
        if approval.approved_by not in _OWNER_APPROVAL_REFERENCES:
            raise PermissionError("non-owner execution approval denied")
        level = capability_permission_policy(approval.capability).level
        owner_proof_required = level >= PermissionLevel.REVERSIBLE_SCOPED
        protected = level >= PermissionLevel.PROTECTED
        if owner_proof_required and not authentication_event_id:
            raise PermissionError(
                "level-3+ execution requires freshly verified owner authentication"
            )
        if authentication_event_id is not None and (
            not isinstance(authentication_event_id, str)
            or not (
                (authentication_event_id.startswith("owner-webauthn:")
                 and len(authentication_event_id) == len("owner-webauthn:") + 64)
                or (authentication_event_id.startswith("owner-secret:")
                    and len(authentication_event_id) == len("owner-secret:") + 64)
            )
        ):
            raise PermissionError("invalid owner authentication event identity")
        with closing(self._connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            if authentication_event_id is not None:
                # Accept either independently verified WebAuthn, or an
                # attended Windows owner-secret proof. Both are one-use,
                # exact-action, short-lived and recorded in the SAFE audit.
                digest = authentication_event_id.partition(":")[2]
                if authentication_event_id.startswith("owner-secret:"):
                    row = db.execute(
                        "SELECT p.action_fingerprint,p.verified_at "
                        "FROM safe_owner_secret_proof p "
                        "JOIN safe_owner_secret s ON s.singleton=1 AND p.version=s.version "
                        "JOIN safe_audit_event au ON au.event_id=? "
                        "WHERE p.proof_id=? AND au.event_type='owner.secret.verified'",
                        (authentication_event_id, digest),
                    ).fetchone()
                    if row is None:
                        raise PermissionError("owner software proof unavailable or revoked")
                    verified_at = datetime.fromisoformat(row["verified_at"])
                else:
                    row = db.execute(
                        "SELECT ch.action_fingerprint,ch.consumed_at,cr.credential_kind,cr.revoked_at "
                        "FROM safe_owner_challenge ch JOIN safe_owner_credential cr "
                        "ON cr.credential_id=ch.credential_id "
                        "JOIN safe_audit_event au ON au.event_id=? "
                        "WHERE ch.challenge_digest=? "
                        "AND au.event_type='owner.webauthn.verified'",
                        (authentication_event_id, digest),
                    ).fetchone()
                    if row is None or row["consumed_at"] is None or row["revoked_at"] is not None:
                        raise PermissionError("owner authentication evidence unavailable or revoked")
                    verified_at = datetime.fromisoformat(row["consumed_at"])
                    if protected and row["credential_kind"] != "security_key":
                        raise PermissionError("protected execution requires enrolled security key")
                if row["action_fingerprint"] != approval.request_fingerprint:
                    raise PermissionError("authenticated action fingerprint mismatch")
                approval_time = approval.approved_at.astimezone(timezone.utc)
                if not verified_at <= approval_time <= verified_at + timedelta(seconds=120):
                    raise PermissionError("owner verification is stale or from the future")
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
        """Return active unconsumed owner-approved capability names."""
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
                SELECT capability, approved_by, approved_at, expires_at,
                       EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_challenge ch
                           ON b.authentication_event_id =
                              ('owner-webauthn:' || ch.challenge_digest)
                         JOIN safe_owner_credential cr
                           ON cr.credential_id = ch.credential_id
                         WHERE b.approval_id = a.approval_id
                           AND ch.consumed_at IS NOT NULL
                           AND cr.revoked_at IS NULL
                       ) OR EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_secret_proof p ON b.authentication_event_id =
                           ('owner-secret:' || p.proof_id)
                         JOIN safe_owner_secret s ON s.singleton=1 AND p.version=s.version
                         JOIN safe_audit_event au ON au.event_id=b.authentication_event_id
                         WHERE b.approval_id=a.approval_id
                           AND au.event_type='owner.secret.verified'
                       ) AS owner_proof_bound
                FROM safe_execution_approval a
                WHERE consumed_at IS NULL
                ORDER BY capability, approved_at
                """
            ).fetchall()
        capabilities = []
        for row in rows:
            if row["approved_by"] not in _OWNER_APPROVAL_REFERENCES:
                continue
            if (
                capability_permission_policy(row["capability"]).level >= PermissionLevel.REVERSIBLE_SCOPED
                and not row["owner_proof_bound"]
            ):
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
                       approved_at, expires_at, consumed_at,
                       EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_challenge ch
                           ON b.authentication_event_id =
                              ('owner-webauthn:' || ch.challenge_digest)
                         JOIN safe_owner_credential cr
                           ON cr.credential_id = ch.credential_id
                         WHERE b.approval_id = a.approval_id
                           AND ch.consumed_at IS NOT NULL
                           AND cr.revoked_at IS NULL
                       ) OR EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_secret_proof p ON b.authentication_event_id =
                           ('owner-secret:' || p.proof_id)
                         JOIN safe_owner_secret s ON s.singleton=1 AND p.version=s.version
                         JOIN safe_audit_event au ON au.event_id=b.authentication_event_id
                         WHERE b.approval_id=a.approval_id
                           AND au.event_type='owner.secret.verified'
                       ) AS owner_proof_bound
                FROM safe_execution_approval a
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        if row is None or row["consumed_at"] is not None:
            return False
        if (
            capability_permission_policy(capability).level >= PermissionLevel.REVERSIBLE_SCOPED
            and not row["owner_proof_bound"]
        ):
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

    def consumed_owner_proof_remains_current(
        self, *, approval_id: str, capability: str, parameters: dict,
    ) -> bool:
        """Read-only post-effect owner revocation fence for a consumed approval.

        This is NOT a new grant and cannot authorize another operation.
        It only verifies that the exact consumed approval still has its
        originally authenticated, unrevoked owner binding. A credential
        revoked while the native OS effect ran must force reconciliation.
        """
        if type(approval_id) is not str or not approval_id.strip():
            return False
        try:
            fingerprint = execution_fingerprint(capability, parameters)
        except (TypeError, ValueError):
            return False
        # A still-enrolled credential cannot rescue a broken canonical SAFE
        # audit chain. This verifier is read-only, and an invalid chain
        # must force reconciliation rather than endorsing a completed effect.
        integrity_ok, _ = self.audit.verify()
        if integrity_ok is not True:
            return False
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT
                    a.capability, a.request_fingerprint,
                    a.approved_by, a.consumed_at,
                    EXISTS(
                        SELECT 1 FROM safe_execution_owner_auth_binding b
                        JOIN safe_owner_challenge ch
                          ON b.authentication_event_id =
                            ('owner-webauthn:' || ch.challenge_digest)
                        JOIN safe_owner_credential cr
                          ON cr.credential_id = ch.credential_id
                        WHERE b.approval_id = a.approval_id
                          AND ch.consumed_at IS NOT NULL
                          AND cr.revoked_at IS NULL
                    ) OR EXISTS(
                        SELECT 1 FROM safe_execution_owner_auth_binding b
                        JOIN safe_owner_secret_proof p
                          ON b.authentication_event_id =
                            ('owner-secret:' || p.proof_id)
                        JOIN safe_owner_secret secret
                          ON secret.singleton = 1 AND p.version = secret.version
                        JOIN safe_audit_event au
                          ON au.event_id = b.authentication_event_id
                        WHERE b.approval_id = a.approval_id
                          AND au.event_type = 'owner.secret.verified'
                    ) AS owner_proof_bound
                FROM safe_execution_approval a
                WHERE a.approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        return bool(
            row is not None
            and row[0] == capability
            and row[1] == fingerprint
            and row[2] in _OWNER_APPROVAL_REFERENCES
            and row[3] is not None
            and row[4] == 1
        )

    def consume(
        self,
        *,
        approval_id: str,
        capability: str,
        parameters: dict,
        now: datetime,
        _transaction_db: sqlite3.Connection | None = None,
    ) -> ExecutionApproval:
        """Consume a one-use approval, optionally inside a caller's open write transaction.

        Internal SAFE call sites may pass a canonical BEGIN IMMEDIATE connection
        to atomically commit approval, state mutation and audit together.
        """
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

        from contextlib import nullcontext
        own_connection = _transaction_db is None
        context = closing(self._connect()) if own_connection else nullcontext(_transaction_db)
        with context as db:
            if not own_connection and not db.in_transaction:
                raise RuntimeError("shared SAFE approval consumption requires open transaction")
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            if own_connection:
                db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT capability, request_fingerprint, approved_by,
                       approved_at, expires_at, consumed_at,
                       EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_challenge ch
                           ON b.authentication_event_id =
                              ('owner-webauthn:' || ch.challenge_digest)
                         JOIN safe_owner_credential cr
                           ON cr.credential_id = ch.credential_id
                         WHERE b.approval_id = a.approval_id
                           AND ch.consumed_at IS NOT NULL
                           AND cr.revoked_at IS NULL
                       ) OR EXISTS(
                         SELECT 1 FROM safe_execution_owner_auth_binding b
                         JOIN safe_owner_secret_proof p ON b.authentication_event_id =
                           ('owner-secret:' || p.proof_id)
                         JOIN safe_owner_secret s ON s.singleton=1 AND p.version=s.version
                         JOIN safe_audit_event au ON au.event_id=b.authentication_event_id
                         WHERE b.approval_id=a.approval_id
                           AND au.event_type='owner.secret.verified'
                       ) AS owner_proof_bound
                FROM safe_execution_approval a
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("execution approval does not exist")
            if row["consumed_at"] is not None:
                raise PermissionError("execution approval was already consumed")
            if (
                capability_permission_policy(capability).level >= PermissionLevel.REVERSIBLE_SCOPED
                and not row["owner_proof_bound"]
            ):
                raise PermissionError(
                    "level-3+ execution approval lacks verified owner authentication"
                )

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
            if approval.approved_by not in _OWNER_APPROVAL_REFERENCES:
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
            if own_connection:
                db.commit()
            return approval
