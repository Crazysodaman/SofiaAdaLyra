from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.evolve.amendment import AmendmentProposal
from sofia.evolve.approval import (
    AmendmentApproval,
    ApprovalVerifier,
)
from sofia.evolve.revision import (
    RevisionApproval,
    RevisionApprovalVerifier,
    RevisionProposal,
)


class DurableEvolutionApprovalVerifier(
    ApprovalVerifier,
    RevisionApprovalVerifier,
):
    """
    SAFE-owned durable verifier for exact EVOLVE approvals.

    Approvals are inserted only by an operator-facing path. EVOLVE can verify
    them but cannot mint, widen, or rewrite them.
    """

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=10) as db:
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
                    revoked INTEGER NOT NULL DEFAULT 0
                        CHECK(revoked IN (0,1))
                )
                """
            )

    def record_amendment(self, approval: AmendmentApproval) -> None:
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
        )

    def record_revision(self, approval: RevisionApproval) -> None:
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
    ) -> None:
        if approved_by != "Sparks":
            raise PermissionError(
                "current EVOLVE approval authority is explicitly Sparks"
            )
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                INSERT INTO safe_evolve_approval (
                    approval_id, proposal_id, proposal_fingerprint,
                    target_kind, target_value, action, approved_by,
                    approved_at, expires_at, authority_reference, revoked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
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
                ),
            )

    def revoke(self, approval_id: str) -> None:
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("approval_id must be nonempty")
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute(
                """
                UPDATE safe_evolve_approval
                SET revoked=1
                WHERE approval_id=?
                """,
                (approval_id,),
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
        with sqlite3.connect(self.path, timeout=10) as db:
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
        return (
            approved_at <= moment < expires_at
            and row["proposal_id"] == proposal_id
            and row["proposal_fingerprint"] == proposal_fingerprint
            and row["target_kind"] == target_kind
            and row["target_value"] == target_value
            and row["action"] == action
            and row["approved_by"] == approved_by == "Sparks"
            and row["authority_reference"] == authority_reference
        )

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
