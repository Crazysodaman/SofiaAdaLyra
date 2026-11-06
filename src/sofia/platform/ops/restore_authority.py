"""Operator-owned single-use authority for protected restore replacement.

Overwriting an existing protected state home is among the most consequential
operations in this codebase.  A boolean callback is not acceptable proof of
owner intent: it can be supplied, guessed or derived by any code path that
already holds the process.  Replacement authorization must instead be an
exact, single-use receipt that

- binds independently authenticated exact SAFE owner proof in this ledger,
- binds the exact destination pathname, backup id and manifest digest,
- expires on a bounded owner-declared window,
- can be revoked before publication,
- is consumed exactly once, immediately before publication, and
- is stored in an operator-held ledger that survives the replacement of the
  canonical state it authorizes.

The ledger mirrors the external memory-deletion journal's trust position: it
lives outside the restored state home and the backup snapshots, is
provisioned explicitly by the owner, and is never manufactured by the
engine itself.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier, OWNER_PRINCIPAL_ID, execution_fingerprint,
)
from sofia.platform.state.sqlite_uri import sqlite_file_uri


RESTORE_REPLACEMENT_CAPABILITY = "ops.restore.replace_protected"
"""SAFE capability name protecting an existing state replacement."""

RESTORE_AUTHORITY_APPLICATION_ID = 0x5253544C
"""'RSTL' marker, distinct from canonical 0x534F4649 and local 0x4C4F434C."""

RESTORE_REVOCATION_CAPABILITY = "ops.restore.receipt.revoke"
RESTORE_AUTHORITY_SCHEMA = "sofia.platform.ops.restore-authority-v2"
_LEGACY_SCHEMA = "sofia.platform.ops.restore-authority-v1"
_OWNER_BINDING_SQL = """CREATE TABLE IF NOT EXISTS ops_restore_owner_binding (
    restore_approval_id TEXT PRIMARY KEY,
    execution_approval_id TEXT NOT NULL UNIQUE
)"""

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class RestoreAuthorityUnavailable(RuntimeError):
    """The protected restore authority ledger is absent or refused ownership."""


def restore_revocation_parameters(approval_id: str, reason: str) -> dict:
    if not isinstance(approval_id, str) or _IDENTIFIER.fullmatch(approval_id) is None:
        raise ValueError("approval_id must be a bounded identifier")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4096:
        raise ValueError("revocation reason must be nonempty and bounded")
    return {"restore_receipt_id": approval_id, "reason": reason.strip()}


def replacement_parameters(
    target_state_path: Path | str,
    manifest,
) -> dict:
    """The exact bounded parameters a replacement receipt must authorize.

    Shared helper so the approval CLI, the ledger and the restore engine can
    never invent divergent binding formats for the same operation.
    """
    backup_id = getattr(manifest, "backup_id", None)
    digest = getattr(manifest, "digest", None)
    if not isinstance(backup_id, str) or not backup_id.strip():
        raise TypeError("authenticated BackupManifest with backup_id is required")
    if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
        raise TypeError("authenticated BackupManifest with sha256 digest is required")
    if isinstance(target_state_path, (Path, str)):
        target = str(Path(target_state_path).absolute())
    else:
        raise TypeError("target_state_path must be a Path or string")
    if not target:
        raise ValueError("target_state_path must be nonempty")
    return {
        "backup_id": backup_id,
        "backup_manifest_digest": digest,
        "target_state_path": target,
    }


@dataclass(frozen=True, slots=True)
class ProtectedRestoreReplacementApproval:
    """One owner-minted replacement receipt before it is consumed."""

    approval_id: str
    target_state_path: str
    backup_id: str
    manifest_digest: str
    approved_by: str
    approved_at: datetime
    expires_at: datetime

    def target_path(self) -> Path:
        return Path(self.target_state_path)

    def __post_init__(self) -> None:
        if not isinstance(self.approval_id, str) or _IDENTIFIER.fullmatch(
            self.approval_id
        ) is None:
            raise ValueError("approval_id must be a bounded identifier")
        if not isinstance(self.target_state_path, str) or not (
            self.target_state_path
            and Path(self.target_state_path).is_absolute()
        ):
            raise ValueError("target_state_path must be an absolute pathname")
        if not isinstance(self.backup_id, str) or _IDENTIFIER.fullmatch(
            self.backup_id
        ) is None:
            raise ValueError("backup_id must be a bounded identifier")
        if not isinstance(self.manifest_digest, str) or _HEX64.fullmatch(
            self.manifest_digest
        ) is None:
            raise ValueError("manifest_digest must be lowercase SHA-256")
        # These are compatible metadata encodings, never authentication.
        # The ledger independently verifies and binds exact SAFE owner proof.
        if self.approved_by not in (OWNER_PRINCIPAL_ID, "Sparks"):
            raise PermissionError("unsupported restore owner reference encoding")
        for name in ("approved_at", "expires_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise TypeError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at <= self.approved_at:
            raise ValueError("approval expiry must follow approval time")


class ProtectedRestoreLedger:
    """Durable receipt store for protected restore replacements.

    One single SQLite file holds the operator's replacement receipts and an
    append-only audit chain of recorded, denied, revoked and consumed
    decisions.  The file is created only by explicit owner provisioning and
    its identity is pinned so a substituted file cannot silently serve.
    """

    AUDIT_RECORDED = "ops.restore.replacement.recorded"
    AUDIT_DENIED = "ops.restore.replacement.denied"
    AUDIT_CONSUMED = "ops.restore.replacement.consumed"
    AUDIT_REVOKED = "ops.restore.replacement.revoked"

    def __init__(self, path: Path | str) -> None:
        if not isinstance(path, (Path, str)):
            raise TypeError("restore authority ledger path must be a Path")
        self.path = Path(path).absolute()
        self._identity = self._open_existing()
        self.audit = AuditChain(self.path)
        self._approvals = ExecutionApprovalVerifier(self.path)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            schema = db.execute(
                "SELECT value FROM ops_restore_authority_meta WHERE key='schema'"
            ).fetchone()[0]
            if schema == _LEGACY_SCHEMA:
                db.execute(_OWNER_BINDING_SQL)
                migration_time = datetime.now(timezone.utc)
                blocked = db.execute(
                    "UPDATE ops_restore_replacement_approval SET revoked_at=?,revocation_reason=? "
                    "WHERE consumed_at IS NULL AND revoked_at IS NULL",
                    (migration_time.isoformat(), "legacy name-only receipt requires fresh authenticated owner approval"),
                ).rowcount
                db.execute(
                    "UPDATE ops_restore_authority_meta SET value=? WHERE key='schema'",
                    (RESTORE_AUTHORITY_SCHEMA,),
                )
                self.audit.append_in_transaction(
                    db, actor_id="system:restore-authority",
                    event_type="ops.restore.authority.owner-proof-required",
                    payload={"schema": RESTORE_AUTHORITY_SCHEMA,
                             "legacy_receipts_promoted": False,
                             "blocked_legacy_receipts": blocked},
                    occurred_at=migration_time,
                    event_id="restore-authority-owner-proof-v2",
                )
            elif db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ops_restore_owner_binding'"
            ).fetchone() is None:
                raise RestoreAuthorityUnavailable("restore owner-proof bindings are missing")

    # ---- provisioning and validation ---------------------------------------

    @classmethod
    def initialize(cls, path: Path | str) -> "ProtectedRestoreLedger":
        """Explicit operator provisioning; the engine never creates a ledger."""
        if not isinstance(path, (Path, str)):
            raise TypeError("restore authority ledger path must be a Path")
        absolute = Path(path).absolute()
        if not absolute.is_absolute():
            raise ValueError("absolute external restore authority path required")
        cls._check_path(absolute)
        if absolute.exists() or absolute.is_symlink():
            return cls(absolute)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{absolute.name}.", suffix=".bootstrap", dir=absolute.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with closing(sqlite3.connect(str(temporary), timeout=10)) as database:
                database.execute(
                    f"PRAGMA application_id = {RESTORE_AUTHORITY_APPLICATION_ID}"
                )
                database.execute("BEGIN IMMEDIATE")
                database.execute(
                    """
                    CREATE TABLE ops_restore_authority_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                database.execute(
                    """
                    INSERT INTO ops_restore_authority_meta
                        VALUES('schema', ?)
                    """,
                    (RESTORE_AUTHORITY_SCHEMA,),
                )
                database.execute(
                    """
                    CREATE TABLE ops_restore_replacement_approval (
                        approval_id TEXT PRIMARY KEY,
                        target_state_path TEXT NOT NULL,
                        backup_id TEXT NOT NULL,
                        manifest_digest TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        approved_by TEXT NOT NULL,
                        approved_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        consumed_at TEXT,
                        revoked_at TEXT,
                        revocation_reason TEXT
                    )
                    """
                )
                database.execute(_OWNER_BINDING_SQL)
                database.commit()
            try:
                with temporary.open("r+b") as persisted:
                    persisted.flush()
                    os.fsync(persisted.fileno())
            except OSError:
                pass
            try:
                os.link(temporary, absolute)
            except FileExistsError:
                return cls(absolute)
        finally:
            temporary.unlink(missing_ok=True)
        return cls(absolute)

    def _open_existing(self) -> tuple[int, int]:
        self._check_path(self.path)
        try:
            details = self.path.stat(follow_symlinks=False)
        except FileNotFoundError as exc:
            raise RestoreAuthorityUnavailable(
                f"restore authority ledger is absent: {self.path}"
            ) from exc
        if not stat.S_ISREG(details.st_mode):
            raise RestoreAuthorityUnavailable(
                "restore authority ledger is not a regular file"
            )
        identity = (int(details.st_dev), int(details.st_ino))
        with closing(sqlite3.connect(
            sqlite_file_uri(self.path, read_only=True), uri=True, timeout=10,
        )) as db:
            try:
                application = int(db.execute("PRAGMA application_id").fetchone()[0])
                row = db.execute(
                    "SELECT value FROM ops_restore_authority_meta WHERE key='schema'"
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise RestoreAuthorityUnavailable(
                    "restore authority ledger is not a valid protected ledger"
                ) from exc
            if (application != RESTORE_AUTHORITY_APPLICATION_ID or row is None
                    or row[0] not in (RESTORE_AUTHORITY_SCHEMA, _LEGACY_SCHEMA)):
                raise RestoreAuthorityUnavailable(
                    "restore authority ledger does not carry the protected "
                    "restore authority identity"
                )
            if row[0] == RESTORE_AUTHORITY_SCHEMA and db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ops_restore_owner_binding'"
            ).fetchone() is None:
                raise RestoreAuthorityUnavailable("restore owner-proof bindings are missing")
        return identity

    def _validate_identity(self) -> None:
        self._check_path(self.path)
        try:
            details = self.path.stat(follow_symlinks=False)
        except FileNotFoundError as exc:
            raise RestoreAuthorityUnavailable(
                "restore authority ledger disappeared while it owned replacement"
            ) from exc
        if (int(details.st_dev), int(details.st_ino)) != self._identity:
            raise RestoreAuthorityUnavailable(
                "restore authority ledger was replaced after this owner started"
            )

    @staticmethod
    def _check_path(target: Path) -> None:
        for part in (target, *target.parents):
            if part.is_symlink() or getattr(
                part, "is_junction", lambda: False
            )():
                raise RestoreAuthorityUnavailable(
                    f"redirected restore authority ledger is forbidden: {part}"
                )

    def _connect(self) -> sqlite3.Connection:
        self._validate_identity()
        db = sqlite3.connect(
            sqlite_file_uri(self.path), uri=True, timeout=10,
        )
        try:
            self._validate_identity()
            db.execute("PRAGMA busy_timeout=10000")
        except BaseException:
            db.close()
            raise
        return db

    # ---- receipts ------------------------------------------------------------

    def record(
        self, approval: ProtectedRestoreReplacementApproval,
        *, owner_approval_id: str | None = None, now: datetime | None = None,
    ) -> str:
        """Bind a pending receipt to exact, currently unconsumed owner proof.

        The proof is rechecked and consumed with the receipt at publication.
        Caller metadata cannot widen its principal, scope or validity window.
        """
        if not isinstance(approval, ProtectedRestoreReplacementApproval):
            raise TypeError("approval must be a ProtectedRestoreReplacementApproval")
        if not isinstance(owner_approval_id, str) or not owner_approval_id.strip():
            raise PermissionError("exact authenticated owner approval is required")
        moment = datetime.now(timezone.utc) if now is None else now
        if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = moment.astimezone(timezone.utc)
        parameters = {
            "backup_id": approval.backup_id,
            "backup_manifest_digest": approval.manifest_digest,
            "target_state_path": approval.target_state_path,
        }
        fingerprint = execution_fingerprint(
            RESTORE_REPLACEMENT_CAPABILITY,
            {
                "backup_id": approval.backup_id,
                "backup_manifest_digest": approval.manifest_digest,
                "target_state_path": approval.target_state_path,
            },
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not self._approvals.matches_unconsumed(
                approval_id=owner_approval_id,
                capability=RESTORE_REPLACEMENT_CAPABILITY,
                parameters=parameters, now=moment,
            ):
                raise PermissionError("no current exact authenticated owner approval")
            row = db.execute(
                """
                SELECT approval_id
                FROM ops_restore_replacement_approval
                WHERE approval_id = ?
                """,
                (approval.approval_id,),
            ).fetchone()
            if row is not None:
                raise PermissionError(
                    "restore approval receipt is immutable: "
                    f"{approval.approval_id} already exists"
                )
            if db.execute(
                "SELECT 1 FROM ops_restore_owner_binding WHERE execution_approval_id=?",
                (owner_approval_id,),
            ).fetchone() is not None:
                raise PermissionError("owner approval is already bound to a restore receipt")
            proof = db.execute(
                "SELECT approved_at,expires_at FROM safe_execution_approval WHERE approval_id=?",
                (owner_approval_id,),
            ).fetchone()
            approval = replace(
                approval, approved_by=OWNER_PRINCIPAL_ID,
                approved_at=max(approval.approved_at, datetime.fromisoformat(proof[0])),
                expires_at=min(approval.expires_at, datetime.fromisoformat(proof[1])),
            )
            db.execute(
                """
                INSERT INTO ops_restore_replacement_approval (
                    approval_id,
                    target_state_path,
                    backup_id,
                    manifest_digest,
                    request_fingerprint,
                    approved_by,
                    approved_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.target_state_path,
                    approval.backup_id,
                    approval.manifest_digest,
                    fingerprint,
                    approval.approved_by,
                    approval.approved_at.astimezone(timezone.utc).isoformat(),
                    approval.expires_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=approval.approved_by,
                event_type=self.AUDIT_RECORDED,
                payload={
                    "approval_id": approval.approval_id,
                    "target_state_path": approval.target_state_path,
                    "backup_id": approval.backup_id,
                    "manifest_digest": approval.manifest_digest,
                    "owner_approval_id": owner_approval_id,
                    "expires_at": approval.expires_at
                        .astimezone(timezone.utc)
                        .isoformat(),
                },
                occurred_at=approval.approved_at,
                event_id=f"restore-replacement-recorded:{approval.approval_id}",
            )
            db.execute("INSERT INTO ops_restore_owner_binding VALUES(?,?)",
                       (approval.approval_id, owner_approval_id))
        return approval.approval_id

    def revoke(
        self,
        approval_id: str,
        *,
        reason: str,
        at: datetime,
        revoked_by: str | None = None,
        owner_approval_id: str | None = None,
    ) -> None:
        """Revoke an unconsumed receipt; receipt identity is reused exactly."""
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("approval_id must be nonempty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("revocation reason must be nonempty")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        if not isinstance(owner_approval_id, str) or not owner_approval_id.strip():
            raise PermissionError("exact authenticated owner revocation approval is required")
        if revoked_by is not None and (not isinstance(revoked_by, str) or len(revoked_by) > 160):
            raise ValueError("revoked_by compatibility metadata must be bounded text")
        parameters = restore_revocation_parameters(approval_id, reason)
        moment = at.astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            verified = self._approvals.consume(
                approval_id=owner_approval_id, capability=RESTORE_REVOCATION_CAPABILITY,
                parameters=parameters, now=moment, _transaction_db=db,
            )
            row = db.execute(
                """
                SELECT consumed_at, revoked_at
                FROM ops_restore_replacement_approval
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise PermissionError(
                    f"unknown restore approval receipt: {approval_id}"
                )
            if row["revoked_at"] is not None:
                raise PermissionError("restore approval receipt was already revoked")
            if row["consumed_at"] is not None:
                raise PermissionError(
                    "restore approval receipt was already consumed"
                )
            db.execute(
                """
                UPDATE ops_restore_replacement_approval
                SET revoked_at = ?, revocation_reason = ?
                WHERE approval_id = ?
                """,
                (moment.isoformat(), reason, approval_id),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=verified.principal_id,
                event_type=self.AUDIT_REVOKED,
                payload={
                    "approval_id": approval_id,
                    "reason": reason,
                },
                occurred_at=moment,
                event_id=f"restore-replacement-revoked:{approval_id}",
            )

    def require_replacement(
        self,
        target_state_path: Path | str,
        manifest,
        *,
        now: datetime,
    ) -> str:
        """Non-consuming preflight authorization bound to the exact request."""
        return self._evaluate(target_state_path, manifest, now=now)

    def consume_replacement(
        self,
        target_state_path: Path | str,
        manifest,
        *,
        now: datetime,
    ) -> str:
        """Consume the one-use receipt immediately before publication."""
        return self._evaluate(target_state_path, manifest, now=now, consume=True)

    def active_receipts(self, *, now: datetime) -> tuple[
        ProtectedRestoreReplacementApproval, ...,
    ]:
        """List unconsumed, unrevoked receipts currently inside their window."""
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """
                SELECT a.*, b.execution_approval_id AS owner_approval_id
                FROM ops_restore_replacement_approval a
                LEFT JOIN ops_restore_owner_binding b ON b.restore_approval_id=a.approval_id
                WHERE a.consumed_at IS NULL AND a.revoked_at IS NULL
                ORDER BY a.approved_at ASC
                """
            ).fetchall()
        receipts = []
        for row in rows:
            try:
                receipt = ProtectedRestoreReplacementApproval(
                    approval_id=row["approval_id"],
                    target_state_path=row["target_state_path"],
                    backup_id=row["backup_id"],
                    manifest_digest=row["manifest_digest"],
                    approved_by=row["approved_by"],
                    approved_at=datetime.fromisoformat(row["approved_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]),
                )
            except (PermissionError, TypeError, ValueError):
                continue
            if not (
                receipt.approved_at.astimezone(tz=timezone.utc) <= moment
                < receipt.expires_at.astimezone(tz=timezone.utc)
            ):
                continue
            if row["owner_approval_id"] is None or not self._approvals.matches_unconsumed(
                approval_id=row["owner_approval_id"],
                capability=RESTORE_REPLACEMENT_CAPABILITY,
                parameters={"backup_id": receipt.backup_id,
                            "backup_manifest_digest": receipt.manifest_digest,
                            "target_state_path": receipt.target_state_path},
                now=moment,
            ):
                continue
            receipts.append(receipt)
        return tuple(receipts)

    # ---- internal evaluation ---------------------------------------------------

    def _evaluate(
        self,
        target_state_path: Path | str,
        manifest,
        *,
        now: datetime,
        consume: bool = False,
    ) -> str:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        target = Path(target_state_path).absolute()
        try:
            parameters = replacement_parameters(target, manifest)
        except (TypeError, ValueError) as exc:
            raise PermissionError(
                "replacement request is not authenticable: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        allowed = None
        denial_reason = None
        with closing(self._connect()) as db, db:
            db.row_factory = sqlite3.Row
            # Evaluate and consume under one IMMEDIATE transaction so a
            # concurrent revoke or consume cannot interleave with the
            # one-use transition, even across processes sharing the ledger.
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                """
                SELECT a.*, b.execution_approval_id AS owner_approval_id
                FROM ops_restore_replacement_approval a
                LEFT JOIN ops_restore_owner_binding b ON b.restore_approval_id=a.approval_id
                WHERE a.target_state_path = ?
                  AND a.backup_id = ?
                  AND a.manifest_digest = ?
                ORDER BY a.approved_at DESC, a.rowid DESC
                """,
                (
                    parameters["target_state_path"],
                    parameters["backup_id"],
                    parameters["backup_manifest_digest"],
                ),
            ).fetchall()
            # One exact, unconsumed, unrevoked, in-window receipt wins. Any
            # narrower fingerprint binding is rejected before any scope row
            # would be trusted, so a different manifest can never slip
            # through a receipt minted for another candidate.
            expected_fingerprint = execution_fingerprint(
                RESTORE_REPLACEMENT_CAPABILITY, parameters,
            )
            for row in rows:
                if row["request_fingerprint"] != expected_fingerprint:
                    denial_reason = (
                        "recorded receipt does not bind this exact replacement"
                    )
                    continue
                # The newest exact-binding receipt is the decisive candidate.
                # Older receipts must not replace its verdict, so attribution
                # of a refusal stays deterministic.
                if row["owner_approval_id"] is None:
                    # Historical name-only documents remain audit data. They
                    # cannot confer authority or supersede a verified receipt.
                    denial_reason = "receipt has no authenticated owner proof"
                    continue
                try:
                    approval = ProtectedRestoreReplacementApproval(
                        approval_id=row["approval_id"],
                        target_state_path=parameters["target_state_path"],
                        backup_id=parameters["backup_id"],
                        manifest_digest=parameters["backup_manifest_digest"],
                        approved_by=row["approved_by"],
                        approved_at=datetime.fromisoformat(row["approved_at"]),
                        expires_at=datetime.fromisoformat(row["expires_at"]),
                    )
                except (PermissionError, TypeError, ValueError):
                    denial_reason = "recorded receipt is no longer well-formed"
                    break
                if moment < approval.approved_at:
                    denial_reason = "receipt window has not opened"
                    break
                if moment >= approval.expires_at:
                    denial_reason = "receipt window has expired"
                    break
                if row["revoked_at"] is not None:
                    denial_reason = "receipt was revoked"
                    break
                if row["consumed_at"] is not None:
                    denial_reason = "receipt was already consumed"
                    break
                if not self._approvals.matches_unconsumed(
                    approval_id=row["owner_approval_id"],
                    capability=RESTORE_REPLACEMENT_CAPABILITY,
                    parameters=parameters, now=moment,
                ):
                    denial_reason = "owner approval expired, revoked, consumed, or mismatched"
                    break
                if consume:
                    verified = self._approvals.consume(
                        approval_id=row["owner_approval_id"],
                        capability=RESTORE_REPLACEMENT_CAPABILITY,
                        parameters=parameters, now=moment, _transaction_db=db,
                    )
                    update = db.execute(
                        """
                        UPDATE ops_restore_replacement_approval
                        SET consumed_at = ?
                        WHERE approval_id = ?
                          AND consumed_at IS NULL
                          AND revoked_at IS NULL
                        """,
                        (moment.isoformat(), approval.approval_id),
                    )
                    if update.rowcount != 1:
                        raise PermissionError("receipt was revoked or consumed concurrently")
                    self.audit.append_in_transaction(
                        db,
                        actor_id=verified.principal_id,
                        event_type=self.AUDIT_CONSUMED,
                        payload={
                            "approval_id": approval.approval_id,
                            "target_state_path": approval.target_state_path,
                            "backup_id": approval.backup_id,
                            "manifest_digest": approval.manifest_digest,
                        },
                        occurred_at=moment,
                        event_id=f"restore-replacement-consumed:{approval.approval_id}",
                    )
                allowed = approval.approval_id
                break
        if allowed is None:
            reason = denial_reason or (
                "no receipt was recorded for this exact replacement"
            )
            # Record every refusal as append-only owner evidence except
            # structural ledger refusals, which surfaced already.
            self.audit.append(
                actor_id="system:restore-authority",
                event_type=self.AUDIT_DENIED,
                payload={
                    "target_state_path": parameters["target_state_path"],
                    "backup_id": parameters["backup_id"],
                    "manifest_digest": parameters["backup_manifest_digest"],
                    "reason": reason,
                },
                occurred_at=moment,
            )
            raise PermissionError(
                f"protected restore replacement is not authorized: {reason}"
            )
        return allowed
