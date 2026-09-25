"""Privileged protected-state amendment executor with verified rollback.

This module can mutate only the exact protected paths supplied at construction.
It has no approval UI and no self-approval path. Every apply/rollback requires
an independently verified approval bound to the exact proposal fingerprint.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from uuid import UUID

from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.identity.store import IdentityStore

from .amendment import (
    AmendmentProposal,
    ProposalStatus,
    ProtectedTarget,
    content_digest,
    inspect,
)
from .approval import (
    AmendmentApproval,
    ApprovalAction,
    ApprovalVerifier,
    approval_matches,
)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


class AmendmentExecutionStatus(str, Enum):
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class ProtectedPaths:
    identity_path: Path
    constitution_path: Path
    constitution_hash_path: Path
    backup_dir: Path

    def __post_init__(self) -> None:
        for name, value in (
            ("identity_path", self.identity_path),
            ("constitution_path", self.constitution_path),
            ("constitution_hash_path", self.constitution_hash_path),
            ("backup_dir", self.backup_dir),
        ):
            if not isinstance(value, Path):
                raise TypeError(f"{name} must be a Path")
        if self.identity_path == self.constitution_path:
            raise ValueError("identity and Constitution paths must be distinct")
        if self.constitution_hash_path == self.constitution_path:
            raise ValueError("Constitution content and trusted hash must be distinct")


@dataclass(frozen=True)
class AmendmentExecution:
    proposal_id: str
    target: ProtectedTarget
    status: AmendmentExecutionStatus
    from_digest: str
    to_digest: str
    apply_approval_id: str
    applied_at: datetime
    backup_path: Path
    hash_backup_path: Path | None
    rollback_approval_id: str | None = None
    rolled_back_at: datetime | None = None


class ProtectedAmendmentError(RuntimeError):
    pass


class ProtectedAmendmentExecutor:
    """Apply or roll back an exact reviewed identity/Constitution revision."""

    def __init__(
        self,
        *,
        state_path: Path,
        paths: ProtectedPaths,
        verifier: ApprovalVerifier,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        if not state_path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(paths, ProtectedPaths):
            raise TypeError("ProtectedPaths required")
        if not isinstance(verifier, ApprovalVerifier):
            raise TypeError("independent ApprovalVerifier required")
        self.state_path = state_path
        self.paths = paths
        self.verifier = verifier
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evolve_protected_amendments (
                        proposal_id TEXT PRIMARY KEY,
                        target TEXT NOT NULL,
                        proposal_fingerprint TEXT NOT NULL,
                        from_digest TEXT NOT NULL,
                        to_digest TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('applied','rolled_back')),
                        apply_approval_id TEXT NOT NULL,
                        applied_at TEXT NOT NULL,
                        backup_path TEXT NOT NULL,
                        hash_backup_path TEXT,
                        rollback_approval_id TEXT,
                        rolled_back_at TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _target_path(self, target: ProtectedTarget) -> Path:
        if target is ProtectedTarget.IDENTITY:
            return self.paths.identity_path
        if target is ProtectedTarget.CONSTITUTION:
            return self.paths.constitution_path
        raise TypeError("unknown protected target")

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProtectedAmendmentError(f"cannot read protected file: {path}") from exc

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    @staticmethod
    def _validate_identity_content(content: str) -> None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProtectedAmendmentError("proposed identity is not valid JSON") from exc
        if not isinstance(data, dict):
            raise ProtectedAmendmentError("proposed identity must be a JSON object")
        name = data.get("name")
        instance_id = data.get("instance_id")
        if not isinstance(name, str) or not name.strip():
            raise ProtectedAmendmentError("proposed identity requires a nonempty name")
        if not isinstance(instance_id, str):
            raise ProtectedAmendmentError("proposed identity requires an instance_id")
        try:
            UUID(instance_id)
        except ValueError as exc:
            raise ProtectedAmendmentError("proposed identity instance_id must be a UUID") from exc

    @staticmethod
    def _validate_constitution_content(content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise ProtectedAmendmentError("proposed Constitution cannot be empty")

    def _validate_proposed_content(
        self,
        target: ProtectedTarget,
        content: str,
    ) -> None:
        if target is ProtectedTarget.IDENTITY:
            self._validate_identity_content(content)
        elif target is ProtectedTarget.CONSTITUTION:
            self._validate_constitution_content(content)
        else:
            raise TypeError("unknown protected target")

    def _verify_persisted_target(
        self,
        target: ProtectedTarget,
        expected_digest: str,
    ) -> None:
        target_path = self._target_path(target)
        observed = content_digest(self._read_text(target_path))
        if observed != expected_digest:
            raise ProtectedAmendmentError("persisted protected content digest mismatch")
        if target is ProtectedTarget.IDENTITY:
            IdentityStore(target_path).load()
        else:
            ConstitutionIntegrityVerifier(
                str(self.paths.constitution_hash_path)
            ).verify(ConstitutionStore(target_path).load())

    def _backup_paths(
        self,
        proposal: AmendmentProposal,
    ) -> tuple[Path, Path | None]:
        base = f"{proposal.proposal_id}.{proposal.target.value}.before"
        content_backup = self.paths.backup_dir / base
        hash_backup = (
            self.paths.backup_dir / f"{base}.sha256"
            if proposal.target is ProtectedTarget.CONSTITUTION
            else None
        )
        return content_backup, hash_backup

    def _create_backups(
        self,
        proposal: AmendmentProposal,
    ) -> tuple[Path, Path | None]:
        self.paths.backup_dir.mkdir(parents=True, exist_ok=True)
        content_backup, hash_backup = self._backup_paths(proposal)
        if content_backup.exists() or (hash_backup is not None and hash_backup.exists()):
            raise ProtectedAmendmentError("backup path already exists for this proposal")
        try:
            shutil.copy2(self._target_path(proposal.target), content_backup)
            if hash_backup is not None:
                shutil.copy2(self.paths.constitution_hash_path, hash_backup)
        except Exception as exc:
            content_backup.unlink(missing_ok=True)
            if hash_backup is not None:
                hash_backup.unlink(missing_ok=True)
            raise ProtectedAmendmentError("protected backup could not be created") from exc
        return content_backup, hash_backup

    def _restore_backups(
        self,
        *,
        target: ProtectedTarget,
        content_backup: Path,
        hash_backup: Path | None,
    ) -> None:
        original = self._read_text(content_backup)
        self._atomic_write(self._target_path(target), original)
        if target is ProtectedTarget.CONSTITUTION:
            if hash_backup is None:
                raise ProtectedAmendmentError("Constitution hash backup is missing")
            self._atomic_write(
                self.paths.constitution_hash_path,
                self._read_text(hash_backup),
            )

    def _require_approval(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        action: ApprovalAction,
        now: datetime,
    ) -> None:
        if not approval_matches(proposal, approval, action=action, now=now):
            raise PermissionError("approval is not bound to this exact proposal/action")
        if not self.verifier.verify(proposal, approval, now=now):
            raise PermissionError("independent approval verification failed")

    @staticmethod
    def _execution_from_row(row: tuple) -> AmendmentExecution:
        return AmendmentExecution(
            proposal_id=row[0],
            target=ProtectedTarget(row[1]),
            status=AmendmentExecutionStatus(row[5]),
            from_digest=row[3],
            to_digest=row[4],
            apply_approval_id=row[6],
            applied_at=datetime.fromisoformat(row[7]).astimezone(timezone.utc),
            backup_path=Path(row[8]),
            hash_backup_path=Path(row[9]) if row[9] is not None else None,
            rollback_approval_id=row[10],
            rolled_back_at=(
                datetime.fromisoformat(row[11]).astimezone(timezone.utc)
                if row[11] is not None
                else None
            ),
        )

    def get(self, proposal_id: str) -> AmendmentExecution | None:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM evolve_protected_amendments WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        return self._execution_from_row(row) if row is not None else None

    def apply(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        proposed_content: str,
        now: datetime,
    ) -> AmendmentExecution:
        """Apply exactly one reviewed protected revision, atomically or restore."""

        if not isinstance(proposal, AmendmentProposal):
            raise TypeError("AmendmentProposal required")
        moment = _utc(now)
        target_path = self._target_path(proposal.target)
        current_content = self._read_text(target_path)
        observed_digest = content_digest(current_content)
        if not isinstance(proposed_content, str):
            raise TypeError("proposed_content must be text")
        if content_digest(proposed_content) != proposal.proposed_digest:
            raise ProtectedAmendmentError("proposed content does not match proposal digest")
        self._validate_proposed_content(proposal.target, proposed_content)
        self._require_approval(
            proposal,
            approval,
            action=ApprovalAction.APPLY,
            now=moment,
        )

        existing = self.get(proposal.proposal_id)
        if existing is not None:
            if (
                existing.status is AmendmentExecutionStatus.APPLIED
                and existing.to_digest == proposal.proposed_digest
                and observed_digest == proposal.proposed_digest
            ):
                return existing
            raise ProtectedAmendmentError("proposal already has a terminal execution record")

        status = inspect(proposal, moment, observed_digest=observed_digest)
        if status is not ProposalStatus.REQUIRES_EXPLICIT_REVIEW:
            raise ProtectedAmendmentError(
                f"proposal is not applicable: {status.value}"
            )

        content_backup, hash_backup = self._create_backups(proposal)
        try:
            self._atomic_write(target_path, proposed_content)
            if proposal.target is ProtectedTarget.CONSTITUTION:
                self._atomic_write(
                    self.paths.constitution_hash_path,
                    f"{proposal.proposed_digest}\n",
                )
            self._verify_persisted_target(
                proposal.target,
                proposal.proposed_digest,
            )
            with closing(self._connect()) as db:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        """
                        INSERT INTO evolve_protected_amendments
                        (proposal_id, target, proposal_fingerprint, from_digest, to_digest,
                         status, apply_approval_id, applied_at, backup_path,
                         hash_backup_path, rollback_approval_id, rolled_back_at)
                        VALUES (?,?,?,?,?,'applied',?,?,?,?,NULL,NULL)
                        """,
                        (
                            proposal.proposal_id,
                            proposal.target.value,
                            proposal.fingerprint,
                            proposal.expected_digest,
                            proposal.proposed_digest,
                            approval.approval_id,
                            moment.isoformat(),
                            str(content_backup),
                            str(hash_backup) if hash_backup is not None else None,
                        ),
                    )
        except Exception as exc:
            try:
                self._restore_backups(
                    target=proposal.target,
                    content_backup=content_backup,
                    hash_backup=hash_backup,
                )
                self._verify_persisted_target(
                    proposal.target,
                    proposal.expected_digest,
                )
            except Exception as rollback_exc:
                raise ProtectedAmendmentError(
                    "protected amendment failed and automatic restore also failed"
                ) from rollback_exc
            if isinstance(exc, ProtectedAmendmentError):
                raise
            raise ProtectedAmendmentError(
                "protected amendment failed; original state restored"
            ) from exc

        execution = self.get(proposal.proposal_id)
        if execution is None:
            raise ProtectedAmendmentError("applied amendment lacks durable audit record")
        return execution

    def rollback(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        now: datetime,
    ) -> AmendmentExecution:
        """Restore the exact recorded pre-change state with separate approval."""

        if not isinstance(proposal, AmendmentProposal):
            raise TypeError("AmendmentProposal required")
        moment = _utc(now)
        self._require_approval(
            proposal,
            approval,
            action=ApprovalAction.ROLLBACK,
            now=moment,
        )
        existing = self.get(proposal.proposal_id)
        if existing is None:
            raise ProtectedAmendmentError("proposal was never applied")
        if existing.status is AmendmentExecutionStatus.ROLLED_BACK:
            return existing
        if existing.to_digest != proposal.proposed_digest:
            raise ProtectedAmendmentError("audit record does not match proposal revision")
        current_digest = content_digest(
            self._read_text(self._target_path(proposal.target))
        )
        if current_digest != proposal.proposed_digest:
            raise ProtectedAmendmentError(
                "current protected state changed since this proposal; refusing rollback"
            )

        self._restore_backups(
            target=proposal.target,
            content_backup=existing.backup_path,
            hash_backup=existing.hash_backup_path,
        )
        self._verify_persisted_target(
            proposal.target,
            proposal.expected_digest,
        )
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute(
                    """
                    UPDATE evolve_protected_amendments
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
                    raise ProtectedAmendmentError("amendment audit changed concurrently")
        execution = self.get(proposal.proposal_id)
        if execution is None:
            raise ProtectedAmendmentError("rollback audit record missing")
        return execution
