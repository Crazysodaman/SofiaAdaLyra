"""Reviewed, reversible non-protected preference/config evolution.

The executor is storage-neutral. A trusted adapter owns the real target store,
compare-and-swap behavior, validation, and rollback material. EVOLVE records
only revision evidence, digests, approvals, and an opaque rollback token.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .approval import ApprovalAction

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def revision_content_digest(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("revision content must be text")
    return sha256(content.encode("utf-8")).hexdigest()


class RevisionScope(str, Enum):
    PREFERENCE = "preference"
    CONFIG = "config"


class RevisionStatus(str, Enum):
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class RevisionProposal:
    proposal_id: str
    scope: RevisionScope
    key: str
    expected_digest: str
    proposed_digest: str
    evidence_ids: tuple[str, ...]
    reason: str
    rollback_plan: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _id(self.proposal_id, "proposal_id")
        if not isinstance(self.scope, RevisionScope):
            raise TypeError("scope must be a RevisionScope")
        _id(self.key, "key")
        _digest(self.expected_digest, "expected_digest")
        _digest(self.proposed_digest, "proposed_digest")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or len(self.evidence_ids) > 32
        ):
            raise ValueError("bounded evidence IDs required")
        for item in self.evidence_ids:
            _id(item, "evidence_id")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be distinct")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 1000:
            raise ValueError("bounded reason required")
        if not isinstance(self.rollback_plan, str) or not self.rollback_plan.strip() or len(self.rollback_plan) > 1000:
            raise ValueError("bounded rollback plan required")
        if _utc(self.expires_at) <= _utc(self.created_at):
            raise ValueError("expiry must follow creation")

    @property
    def fingerprint(self) -> str:
        document = {
            "proposal_id": self.proposal_id,
            "scope": self.scope.value,
            "key": self.key,
            "expected_digest": self.expected_digest,
            "proposed_digest": self.proposed_digest,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "rollback_plan": self.rollback_plan,
            "created_at": _utc(self.created_at).isoformat(),
            "expires_at": _utc(self.expires_at).isoformat(),
        }
        return sha256(
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class RevisionApproval:
    approval_id: str
    proposal_id: str
    proposal_fingerprint: str
    action: ApprovalAction
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    authority_reference: str

    def __post_init__(self) -> None:
        _id(self.approval_id, "approval_id")
        _id(self.proposal_id, "proposal_id")
        _digest(self.proposal_fingerprint, "proposal_fingerprint")
        if not isinstance(self.action, ApprovalAction):
            raise TypeError("action must be ApprovalAction")
        _id(self.approved_by, "approved_by")
        _id(self.authority_reference, "authority_reference")
        if _utc(self.expires_at) <= _utc(self.approved_at):
            raise ValueError("approval expiry must follow approval time")


class RevisionApprovalVerifier(ABC):
    @abstractmethod
    def verify(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        now: datetime,
    ) -> bool:
        raise NotImplementedError


class RevisionAdapter(ABC):
    """Trusted store-specific compare-and-swap/rollback boundary."""

    @abstractmethod
    def read_digest(self, scope: RevisionScope, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def validate(
        self,
        scope: RevisionScope,
        key: str,
        proposed_content: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        scope: RevisionScope,
        key: str,
        *,
        expected_digest: str,
        proposed_content: str,
    ) -> str:
        """Atomically apply exact expected revision and return opaque rollback token."""
        raise NotImplementedError

    @abstractmethod
    def rollback(
        self,
        scope: RevisionScope,
        key: str,
        *,
        expected_current_digest: str,
        rollback_token: str,
    ) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class RevisionExecution:
    proposal_id: str
    scope: RevisionScope
    key: str
    status: RevisionStatus
    from_digest: str
    to_digest: str
    apply_approval_id: str
    applied_at: datetime
    rollback_token: str
    rollback_approval_id: str | None = None
    rolled_back_at: datetime | None = None


class RevisionExecutionError(RuntimeError):
    pass


class ReviewedRevisionExecutor:
    def __init__(
        self,
        *,
        state_path: Path,
        adapter: RevisionAdapter,
        verifier: RevisionApprovalVerifier,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        if not state_path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(adapter, RevisionAdapter):
            raise TypeError("RevisionAdapter required")
        if not isinstance(verifier, RevisionApprovalVerifier):
            raise TypeError("RevisionApprovalVerifier required")
        self.state_path = state_path
        self.adapter = adapter
        self.verifier = verifier
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evolve_reviewed_revisions (
                        proposal_id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL,
                        revision_key TEXT NOT NULL,
                        proposal_fingerprint TEXT NOT NULL,
                        from_digest TEXT NOT NULL,
                        to_digest TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('applied','rolled_back')),
                        apply_approval_id TEXT NOT NULL,
                        applied_at TEXT NOT NULL,
                        rollback_token TEXT NOT NULL,
                        rollback_approval_id TEXT,
                        rolled_back_at TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _approval_matches(
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        action: ApprovalAction,
        now: datetime,
    ) -> bool:
        moment = _utc(now)
        return (
            moment >= _utc(approval.approved_at)
            and moment < _utc(approval.expires_at)
            and approval.proposal_id == proposal.proposal_id
            and approval.proposal_fingerprint == proposal.fingerprint
            and approval.action is action
        )

    def _require_approval(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        action: ApprovalAction,
        now: datetime,
    ) -> None:
        if not isinstance(approval, RevisionApproval):
            raise TypeError("RevisionApproval required")
        if not self._approval_matches(
            proposal,
            approval,
            action=action,
            now=now,
        ):
            raise PermissionError("approval is not bound to exact revision/action")
        if not self.verifier.verify(proposal, approval, now=now):
            raise PermissionError("independent revision approval verification failed")

    @staticmethod
    def _from_row(row: tuple) -> RevisionExecution:
        return RevisionExecution(
            proposal_id=row[0],
            scope=RevisionScope(row[1]),
            key=row[2],
            status=RevisionStatus(row[6]),
            from_digest=row[4],
            to_digest=row[5],
            apply_approval_id=row[7],
            applied_at=datetime.fromisoformat(row[8]).astimezone(timezone.utc),
            rollback_token=row[9],
            rollback_approval_id=row[10],
            rolled_back_at=(
                datetime.fromisoformat(row[11]).astimezone(timezone.utc)
                if row[11] is not None
                else None
            ),
        )

    def get(self, proposal_id: str) -> RevisionExecution | None:
        _id(proposal_id, "proposal_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM evolve_reviewed_revisions WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def apply(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        proposed_content: str,
        now: datetime,
    ) -> RevisionExecution:
        if not isinstance(proposal, RevisionProposal):
            raise TypeError("RevisionProposal required")
        moment = _utc(now)
        if moment < _utc(proposal.created_at):
            raise RevisionExecutionError("proposal clock is uncertain")
        if moment >= _utc(proposal.expires_at):
            raise RevisionExecutionError("proposal expired")
        if proposal.expected_digest == proposal.proposed_digest:
            raise RevisionExecutionError("proposal does not change the revision")
        if revision_content_digest(proposed_content) != proposal.proposed_digest:
            raise RevisionExecutionError("proposed content does not match proposal digest")
        self.adapter.validate(proposal.scope, proposal.key, proposed_content)
        self._require_approval(
            proposal,
            approval,
            action=ApprovalAction.APPLY,
            now=moment,
        )

        observed = self.adapter.read_digest(proposal.scope, proposal.key)
        _digest(observed, "adapter observed digest")
        existing = self.get(proposal.proposal_id)
        if existing is not None:
            if (
                existing.status is RevisionStatus.APPLIED
                and existing.to_digest == proposal.proposed_digest
                and observed == proposal.proposed_digest
            ):
                return existing
            raise RevisionExecutionError("proposal already has a terminal revision record")
        if observed != proposal.expected_digest:
            raise RevisionExecutionError("source revision changed before apply")

        token = self.adapter.apply(
            proposal.scope,
            proposal.key,
            expected_digest=proposal.expected_digest,
            proposed_content=proposed_content,
        )
        _id(token, "rollback_token")
        after = self.adapter.read_digest(proposal.scope, proposal.key)
        if after != proposal.proposed_digest:
            try:
                self.adapter.rollback(
                    proposal.scope,
                    proposal.key,
                    expected_current_digest=after,
                    rollback_token=token,
                )
            finally:
                raise RevisionExecutionError("adapter did not persist proposed digest")

        try:
            with closing(self._connect()) as db:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        """
                        INSERT INTO evolve_reviewed_revisions
                        (proposal_id, scope, revision_key, proposal_fingerprint,
                         from_digest, to_digest, status, apply_approval_id,
                         applied_at, rollback_token, rollback_approval_id, rolled_back_at)
                        VALUES (?,?,?,?,?,?,'applied',?,?,?,NULL,NULL)
                        """,
                        (
                            proposal.proposal_id,
                            proposal.scope.value,
                            proposal.key,
                            proposal.fingerprint,
                            proposal.expected_digest,
                            proposal.proposed_digest,
                            approval.approval_id,
                            moment.isoformat(),
                            token,
                        ),
                    )
        except Exception as exc:
            try:
                self.adapter.rollback(
                    proposal.scope,
                    proposal.key,
                    expected_current_digest=proposal.proposed_digest,
                    rollback_token=token,
                )
            except Exception as rollback_exc:
                raise RevisionExecutionError(
                    "revision audit failed and automatic rollback failed"
                ) from rollback_exc
            raise RevisionExecutionError(
                "revision audit failed; applied value was rolled back"
            ) from exc

        result = self.get(proposal.proposal_id)
        if result is None:
            raise RevisionExecutionError("applied revision lacks audit record")
        return result

    def rollback(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        now: datetime,
    ) -> RevisionExecution:
        if not isinstance(proposal, RevisionProposal):
            raise TypeError("RevisionProposal required")
        moment = _utc(now)
        self._require_approval(
            proposal,
            approval,
            action=ApprovalAction.ROLLBACK,
            now=moment,
        )
        existing = self.get(proposal.proposal_id)
        if existing is None:
            raise RevisionExecutionError("proposal was never applied")
        if existing.status is RevisionStatus.ROLLED_BACK:
            return existing

        observed = self.adapter.read_digest(proposal.scope, proposal.key)
        if observed != proposal.proposed_digest:
            raise RevisionExecutionError(
                "current revision changed after apply; refusing rollback"
            )
        self.adapter.rollback(
            proposal.scope,
            proposal.key,
            expected_current_digest=proposal.proposed_digest,
            rollback_token=existing.rollback_token,
        )
        if self.adapter.read_digest(proposal.scope, proposal.key) != proposal.expected_digest:
            raise RevisionExecutionError("adapter rollback did not restore expected digest")

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute(
                    """
                    UPDATE evolve_reviewed_revisions
                    SET status='rolled_back', rollback_approval_id=?, rolled_back_at=?
                    WHERE proposal_id=? AND status='applied'
                    """,
                    (
                        approval.approval_id,
                        moment.isoformat(),
                        proposal.proposal_id,
                    ),
                )
                if changed.rowcount != 1:
                    raise RevisionExecutionError("revision audit changed concurrently")

        result = self.get(proposal.proposal_id)
        if result is None:
            raise RevisionExecutionError("rollback audit record missing")
        return result
