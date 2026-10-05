from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.dev.approval import DevApproval, DevOperation, dev_request_fingerprint
from sofia.safe.audit import AuditChain


def dev_approval_signature_payload(approval: DevApproval) -> bytes:
    """Canonical bytes signed by the independent DEV operator."""

    if not isinstance(approval, DevApproval):
        raise TypeError("approval must be a DevApproval")
    return json.dumps(
        {
            "approval_id": approval.approval_id,
            "operation": approval.operation.value,
            "proposal_id": approval.proposal_id,
            "request_fingerprint": approval.request_fingerprint,
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.astimezone(timezone.utc).isoformat(),
            "expires_at": approval.expires_at.astimezone(timezone.utc).isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def configured_dev_public_keys() -> dict[str, Path]:
    key_id = os.environ.get("SOFIA_DEV_APPROVAL_KEY_ID", "").strip()
    key_path = os.environ.get("SOFIA_DEV_APPROVAL_PUBLIC_KEY", "").strip()
    if not key_id and not key_path:
        return {}
    if not key_id or not key_path:
        raise ValueError(
            "SOFIA_DEV_APPROVAL_KEY_ID and SOFIA_DEV_APPROVAL_PUBLIC_KEY "
            "must be configured together"
        )
    return {key_id: Path(key_path)}


class DevApprovalVerifier:
    """
    Durable, exact-parameter DEV authorization verifier.

    The approval store is populated only by an operator-facing path. Cognition
    can reference an approval_id but cannot mint or widen an approval.
    """

    def __init__(
        self,
        state_path: Path | str,
        *,
        trusted_keys: dict[str, Path | bytes] | None = None,
    ) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = AuditChain(self.path)
        sources = configured_dev_public_keys() if trusted_keys is None else trusted_keys
        self._trusted_keys: dict[str, Ed25519PublicKey] = {}
        for key_id, source in sources.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("DEV signer key IDs must be nonempty")
            raw = source.read_bytes() if isinstance(source, Path) else source
            if not isinstance(raw, bytes):
                raise TypeError("DEV trusted keys must be Path or bytes values")
            key = serialization.load_pem_public_key(raw)
            if not isinstance(key, Ed25519PublicKey):
                raise TypeError("DEV trusted approval key must be Ed25519")
            self._trusted_keys[key_id] = key
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
                        signer_key_id TEXT,
                        signature BLOB,
                        signature_sha256 TEXT,
                        consumed_at TEXT
                    )
                    """
                )
                columns = {
                    row[1]
                    for row in db.execute("PRAGMA table_info(safe_dev_approval)")
                }
                for name, declaration in (
                    ("signer_key_id", "TEXT"),
                    ("signature", "BLOB"),
                    ("signature_sha256", "TEXT"),
                ):
                    if name not in columns:
                        db.execute(
                            f"ALTER TABLE safe_dev_approval ADD COLUMN {name} {declaration}"
                        )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(
        self,
        approval: DevApproval,
        *,
        signer_key_id: str,
        signature: bytes,
    ) -> None:
        if not isinstance(approval, DevApproval):
            raise TypeError("approval must be a DevApproval")
        if approval.approved_by != "Sparks":
            raise PermissionError("current DEV approval authority is explicitly Sparks")
        key = self._trusted_keys.get(signer_key_id)
        if key is None:
            raise PermissionError("DEV approval signer is not trusted")
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("DEV approval signature must be nonempty bytes")
        try:
            key.verify(signature, dev_approval_signature_payload(approval))
        except InvalidSignature as exc:
            raise PermissionError("DEV approval signature is invalid") from exc
        signature_digest = sha256(signature).hexdigest()
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO safe_dev_approval (
                        approval_id, operation, proposal_id,
                        request_fingerprint, approved_by,
                        approved_at, expires_at, signer_key_id,
                        signature, signature_sha256, consumed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        approval.approval_id,
                        approval.operation.value,
                        approval.proposal_id,
                        approval.request_fingerprint,
                        approval.approved_by,
                        approval.approved_at.astimezone(timezone.utc).isoformat(),
                        approval.expires_at.astimezone(timezone.utc).isoformat(),
                        signer_key_id,
                        signature,
                        signature_digest,
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
                        "signer_key_id": signer_key_id,
                        "signature_sha256": signature_digest,
                    },
                    occurred_at=approval.approved_at,
                    event_id=f"dev-approval-recorded:{approval.approval_id}",
                )

    def active_capabilities(
        self,
        *,
        now: datetime,
    ) -> tuple[str, ...]:
        """Return live DEV capability names backed by active Sparks approvals."""
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT approval_id, operation, proposal_id, request_fingerprint,
                       approved_by, approved_at, expires_at, signer_key_id,
                       signature, signature_sha256
                FROM safe_dev_approval
                WHERE consumed_at IS NULL
                ORDER BY operation, approved_at
                """
            ).fetchall()
        values = []
        for row in rows:
            (
                approval_id,
                operation,
                proposal_id,
                request_fingerprint,
                approved_by,
                approved_at_raw,
                expires_at_raw,
                signer_key_id,
                signature,
                signature_digest,
            ) = row
            if approved_by != "Sparks":
                continue
            try:
                approved_at = datetime.fromisoformat(approved_at_raw)
                expires_at = datetime.fromisoformat(expires_at_raw)
                parsed = DevOperation(operation)
            except (TypeError, ValueError):
                continue
            if (
                approved_at.tzinfo is None
                or approved_at.utcoffset() is None
                or expires_at.tzinfo is None
                or expires_at.utcoffset() is None
            ):
                continue
            if not (
                approved_at.astimezone(timezone.utc)
                <= moment
                < expires_at.astimezone(timezone.utc)
            ):
                continue
            approval = DevApproval(
                approval_id=approval_id,
                operation=parsed,
                proposal_id=proposal_id,
                request_fingerprint=request_fingerprint,
                approved_by=approved_by,
                approved_at=approved_at,
                expires_at=expires_at,
            )
            if not self._valid_signature(
                approval,
                signer_key_id=signer_key_id,
                signature=signature,
                signature_digest=signature_digest,
            ):
                continue
            if parsed is DevOperation.BUILD:
                continue
            capability = f"dev.{parsed.value}"
            if capability not in values:
                values.append(capability)
        return tuple(values)

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
                           approved_by, approved_at, expires_at, consumed_at,
                           signer_key_id, signature, signature_sha256
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
                if not self._valid_signature(
                    approval,
                    signer_key_id=row[7],
                    signature=row[8],
                    signature_digest=row[9],
                ):
                    raise PermissionError("DEV approval signature is invalid")
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

    def _valid_signature(
        self,
        approval: DevApproval,
        *,
        signer_key_id,
        signature,
        signature_digest,
    ) -> bool:
        key = self._trusted_keys.get(signer_key_id)
        if key is None or not isinstance(signature, bytes) or not signature:
            return False
        if sha256(signature).hexdigest() != signature_digest:
            return False
        try:
            key.verify(signature, dev_approval_signature_payload(approval))
        except (InvalidSignature, TypeError, ValueError):
            return False
        return True
