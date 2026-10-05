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

from sofia.evolve.amendment import AmendmentProposal, ProtectedTarget
from sofia.evolve.approval import (
    AmendmentApproval,
    ApprovalAction,
    ApprovalVerifier,
)
from sofia.safe.audit import AuditChain

from sofia.evolve.revision import (
    RevisionApproval,
    RevisionApprovalVerifier,
    RevisionProposal,
)


def approval_signature_payload(
    approval: AmendmentApproval | RevisionApproval,
) -> bytes:
    """Canonical bytes signed by the independent EVOLVE authority."""

    if isinstance(approval, AmendmentApproval):
        target_kind = "protected"
        target_value = approval.target.value
    elif isinstance(approval, RevisionApproval):
        target_kind = "revision"
        target_value = "*"
    else:
        raise TypeError("EVOLVE approval required")
    document = {
        "approval_id": approval.approval_id,
        "proposal_id": approval.proposal_id,
        "proposal_fingerprint": approval.proposal_fingerprint,
        "target_kind": target_kind,
        "target_value": target_value,
        "action": approval.action.value,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at.astimezone(timezone.utc).isoformat(),
        "expires_at": approval.expires_at.astimezone(timezone.utc).isoformat(),
        "authority_reference": approval.authority_reference,
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def revocation_signature_payload(
    approval_id: str,
    *,
    revoked_at: datetime,
    authority_reference: str,
) -> bytes:
    """Canonical bytes authorizing revocation of one exact approval."""

    if not isinstance(approval_id, str) or not approval_id.strip():
        raise ValueError("approval_id must be nonempty")
    if revoked_at.tzinfo is None or revoked_at.utcoffset() is None:
        raise ValueError("revoked_at must be timezone-aware")
    if not isinstance(authority_reference, str) or not authority_reference.strip():
        raise ValueError("authority_reference must be nonempty")
    document = {
        "approval_id": approval_id,
        "revoked_at": revoked_at.astimezone(timezone.utc).isoformat(),
        "authority_reference": authority_reference,
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def configured_evolution_public_keys() -> dict[str, Path]:
    """Load the explicit external EVOLVE trust root from host configuration."""

    key_id = os.environ.get("SOFIA_EVOLVE_APPROVAL_KEY_ID", "").strip()
    key_path = os.environ.get("SOFIA_EVOLVE_APPROVAL_PUBLIC_KEY", "").strip()
    if not key_id and not key_path:
        return {}
    if not key_id or not key_path:
        raise ValueError(
            "SOFIA_EVOLVE_APPROVAL_KEY_ID and "
            "SOFIA_EVOLVE_APPROVAL_PUBLIC_KEY must be configured together"
        )
    return {key_id: Path(key_path)}


class DurableEvolutionApprovalVerifier(
    ApprovalVerifier,
    RevisionApprovalVerifier,
):
    """
    SAFE-owned durable verifier for exact EVOLVE approvals.

    Approvals are inserted only by an operator-facing path. EVOLVE can verify
    them but cannot mint, widen, or rewrite them.
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
        sources = configured_evolution_public_keys() if trusted_keys is None else trusted_keys
        self._trusted_keys: dict[str, Ed25519PublicKey] = {}
        for key_id, source in sources.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("EVOLVE signer key IDs must be nonempty")
            raw = source.read_bytes() if isinstance(source, Path) else source
            if not isinstance(raw, bytes):
                raise TypeError("EVOLVE trusted keys must be Path or bytes values")
            key = serialization.load_pem_public_key(raw)
            if not isinstance(key, Ed25519PublicKey):
                raise TypeError("EVOLVE trusted approval key must be Ed25519")
            self._trusted_keys[key_id] = key
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS safe_evolve_approval (
                    approval_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    proposal_fingerprint TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_value TEXT NOT NULL,
                    action TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    authority_reference TEXT NOT NULL,
                    signer_key_id TEXT,
                    signature BLOB,
                    signature_sha256 TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    revoked_at TEXT,
                    revocation_authority_reference TEXT,
                    revocation_signer_key_id TEXT,
                    revocation_signature_sha256 TEXT,
                    CHECK(revoked IN (0,1))
                )
                """
            )

            columns = {
                row[1]
                for row in db.execute("PRAGMA table_info(safe_evolve_approval)")
            }
            for name, declaration in (
                ("signer_key_id", "TEXT"),
                ("signature", "BLOB"),
                ("signature_sha256", "TEXT"),
                ("revoked_at", "TEXT"),
                ("revocation_authority_reference", "TEXT"),
                ("revocation_signer_key_id", "TEXT"),
                ("revocation_signature_sha256", "TEXT"),
            ):
                if name not in columns:
                    db.execute(
                        f"ALTER TABLE safe_evolve_approval ADD COLUMN {name} {declaration}"
                    )

    def record_amendment(
        self,
        approval: AmendmentApproval,
        *,
        signer_key_id: str,
        signature: bytes,
    ) -> None:
        if not isinstance(approval, AmendmentApproval):
            raise TypeError("approval must be an AmendmentApproval")
        self._record(
            approval_id=approval.approval_id,
            proposal_id=approval.proposal_id,
            proposal_fingerprint=approval.proposal_fingerprint,
            target_kind="protected",
            target_value=approval.target.value,
            action=approval.action.value,
            approved_by=approval.approved_by,
            approved_at=approval.approved_at,
            expires_at=approval.expires_at,
            authority_reference=approval.authority_reference,
            signer_key_id=signer_key_id,
            signature=signature,
            signed_payload=approval_signature_payload(approval),
        )

    def record_revision(
        self,
        approval: RevisionApproval,
        *,
        signer_key_id: str,
        signature: bytes,
    ) -> None:
        if not isinstance(approval, RevisionApproval):
            raise TypeError("approval must be a RevisionApproval")
        self._record(
            approval_id=approval.approval_id,
            proposal_id=approval.proposal_id,
            proposal_fingerprint=approval.proposal_fingerprint,
            target_kind="revision",
            target_value="*",
            action=approval.action.value,
            approved_by=approval.approved_by,
            approved_at=approval.approved_at,
            expires_at=approval.expires_at,
            authority_reference=approval.authority_reference,
            signer_key_id=signer_key_id,
            signature=signature,
            signed_payload=approval_signature_payload(approval),
        )

    def _record(
        self,
        *,
        approval_id: str,
        proposal_id: str,
        proposal_fingerprint: str,
        target_kind: str,
        target_value: str,
        action: str,
        approved_by: str,
        approved_at: datetime,
        expires_at: datetime,
        authority_reference: str,
        signer_key_id: str,
        signature: bytes,
        signed_payload: bytes,
    ) -> None:
        if approved_by != "Sparks":
            raise PermissionError(
                "current EVOLVE approval authority is explicitly Sparks"
            )
        if not isinstance(signer_key_id, str) or not signer_key_id.strip():
            raise ValueError("signer_key_id must be nonempty")
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("EVOLVE approval signature must be nonempty bytes")
        key = self._trusted_keys.get(signer_key_id)
        if key is None:
            raise PermissionError("EVOLVE approval signer is not trusted")
        try:
            key.verify(signature, signed_payload)
        except InvalidSignature as exc:
            raise PermissionError("EVOLVE approval signature is invalid") from exc
        signature_digest = sha256(signature).hexdigest()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO safe_evolve_approval (
                    approval_id, proposal_id, proposal_fingerprint,
                    target_kind, target_value, action, approved_by,
                    approved_at, expires_at, authority_reference,
                    signer_key_id, signature, signature_sha256, revoked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    approval_id,
                    proposal_id,
                    proposal_fingerprint,
                    target_kind,
                    target_value,
                    action,
                    approved_by,
                    approved_at.astimezone(timezone.utc).isoformat(),
                    expires_at.astimezone(timezone.utc).isoformat(),
                    authority_reference,
                    signer_key_id,
                    signature,
                    signature_digest,
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=approved_by,
                event_type="evolve.approval.recorded",
                payload={
                    "approval_id": approval_id,
                    "proposal_id": proposal_id,
                    "proposal_fingerprint": proposal_fingerprint,
                    "target_kind": target_kind,
                    "target_value": target_value,
                    "action": action,
                    "authority_reference": authority_reference,
                    "signer_key_id": signer_key_id,
                    "signature_sha256": signature_digest,
                    "expires_at": expires_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                },
                occurred_at=approved_at,
                event_id=f"evolve-approval-recorded:{approval_id}",
            )

    def revoke(
        self,
        approval_id: str,
        *,
        signer_key_id: str,
        signature: bytes,
        revoked_at: datetime,
        authority_reference: str,
    ) -> None:
        payload = revocation_signature_payload(
            approval_id,
            revoked_at=revoked_at,
            authority_reference=authority_reference,
        )
        key = self._trusted_keys.get(signer_key_id)
        if key is None:
            raise PermissionError("EVOLVE revocation signer is not trusted")
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("EVOLVE revocation signature must be nonempty bytes")
        try:
            key.verify(signature, payload)
        except InvalidSignature as exc:
            raise PermissionError("EVOLVE revocation signature is invalid") from exc
        signature_digest = sha256(signature).hexdigest()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT approved_by, proposal_id, action
                FROM safe_evolve_approval
                WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
            if row is None:
                raise LookupError("EVOLVE approval does not exist")
            changed = db.execute(
                """
                UPDATE safe_evolve_approval
                SET revoked=1,
                    revoked_at=?,
                    revocation_authority_reference=?,
                    revocation_signer_key_id=?,
                    revocation_signature_sha256=?
                WHERE approval_id=? AND revoked=0
                """,
                (
                    revoked_at.astimezone(timezone.utc).isoformat(),
                    authority_reference,
                    signer_key_id,
                    signature_digest,
                    approval_id,
                ),
            )
            if changed.rowcount == 1:
                self.audit.append_in_transaction(
                    db,
                    actor_id="Sparks",
                    event_type="evolve.approval.revoked",
                    payload={
                        "approval_id": approval_id,
                        "proposal_id": row["proposal_id"],
                        "action": row["action"],
                        "authority_reference": authority_reference,
                        "signer_key_id": signer_key_id,
                        "signature_sha256": signature_digest,
                    },
                    occurred_at=revoked_at,
                    event_id=f"evolve-approval-revoked:{approval_id}",
                )

    def _matches(
        self,
        *,
        approval_id: str,
        proposal_id: str,
        proposal_fingerprint: str,
        target_kind: str,
        target_value: str,
        action: str,
        approved_by: str,
        authority_reference: str,
        now: datetime,
    ) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                """
                SELECT *
                FROM safe_evolve_approval
                WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
        if row is None or row["revoked"] != 0:
            return False
        try:
            approved_at = datetime.fromisoformat(row["approved_at"])
            expires_at = datetime.fromisoformat(row["expires_at"])
        except (TypeError, ValueError):
            return False
        moment = now.astimezone(timezone.utc)
        matches = (
            approved_at <= moment < expires_at
            and row["proposal_id"] == proposal_id
            and row["proposal_fingerprint"] == proposal_fingerprint
            and row["target_kind"] == target_kind
            and row["target_value"] == target_value
            and row["action"] == action
            and row["approved_by"] == approved_by == "Sparks"
            and row["authority_reference"] == authority_reference
        )
        if not matches:
            return False
        signer_key_id = row["signer_key_id"]
        signature = row["signature"]
        key = self._trusted_keys.get(signer_key_id)
        if key is None or not isinstance(signature, bytes) or not signature:
            return False
        try:
            if target_kind == "protected":
                approval = AmendmentApproval(
                    approval_id=approval_id,
                    proposal_id=proposal_id,
                    proposal_fingerprint=proposal_fingerprint,
                    target=ProtectedTarget(target_value),
                    action=ApprovalAction(action),
                    approved_by=approved_by,
                    approved_at=approved_at,
                    expires_at=expires_at,
                    authority_reference=authority_reference,
                )
            else:
                approval = RevisionApproval(
                    approval_id=approval_id,
                    proposal_id=proposal_id,
                    proposal_fingerprint=proposal_fingerprint,
                    action=ApprovalAction(action),
                    approved_by=approved_by,
                    approved_at=approved_at,
                    expires_at=expires_at,
                    authority_reference=authority_reference,
                )
            key.verify(signature, approval_signature_payload(approval))
        except (InvalidSignature, TypeError, ValueError):
            return False
        return sha256(signature).hexdigest() == row["signature_sha256"]

    def load_approval(
        self,
        approval_id: str,
    ) -> AmendmentApproval | RevisionApproval:
        """Reconstruct an approval; verification still occurs at execution time."""

        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("approval_id must be nonempty")
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM safe_evolve_approval WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise LookupError("EVOLVE approval does not exist")
        common = {
            "approval_id": row["approval_id"],
            "proposal_id": row["proposal_id"],
            "proposal_fingerprint": row["proposal_fingerprint"],
            "action": ApprovalAction(row["action"]),
            "approved_by": row["approved_by"],
            "approved_at": datetime.fromisoformat(row["approved_at"]),
            "expires_at": datetime.fromisoformat(row["expires_at"]),
            "authority_reference": row["authority_reference"],
        }
        if row["target_kind"] == "protected":
            return AmendmentApproval(
                **common,
                target=ProtectedTarget(row["target_value"]),
            )
        if row["target_kind"] == "revision":
            return RevisionApproval(**common)
        raise ValueError("EVOLVE approval has unknown target kind")

    def verify(
        self,
        proposal,
        approval,
        *,
        now: datetime,
    ) -> bool:
        if isinstance(proposal, AmendmentProposal):
            if not isinstance(approval, AmendmentApproval):
                return False
            return self._matches(
                approval_id=approval.approval_id,
                proposal_id=proposal.proposal_id,
                proposal_fingerprint=proposal.fingerprint,
                target_kind="protected",
                target_value=proposal.target.value,
                action=approval.action.value,
                approved_by=approval.approved_by,
                authority_reference=approval.authority_reference,
                now=now,
            )

        if isinstance(proposal, RevisionProposal):
            if not isinstance(approval, RevisionApproval):
                return False
            return self._matches(
                approval_id=approval.approval_id,
                proposal_id=proposal.proposal_id,
                proposal_fingerprint=proposal.fingerprint,
                target_kind="revision",
                target_value="*",
                action=approval.action.value,
                approved_by=approval.approved_by,
                authority_reference=approval.authority_reference,
                now=now,
            )

        return False
