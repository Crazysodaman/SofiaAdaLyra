"""Recovery objectives and backup evidence for fleet operations."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from re import fullmatch

class RecoveryDenied(PermissionError): pass


@dataclass(frozen=True)
class RecoveryObjectives:
    """Declared recovery targets, not proof that live recovery meets them."""

    # Owner-selected CA-3103 Option B targets, not evidence of live recovery.
    rpo_seconds: int = 300
    rto_seconds: int = 3600

    def __post_init__(self) -> None:
        if type(self.rpo_seconds) is not int or self.rpo_seconds <= 0:
            raise ValueError("rpo_seconds must be a positive integer")
        if type(self.rto_seconds) is not int or self.rto_seconds <= 0:
            raise ValueError("rto_seconds must be a positive integer")

    def backup_within_rpo(
        self,
        backup: "BackupEvidence",
        *,
        now: datetime,
    ) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        age = (
            now.astimezone(backup.created_at.tzinfo)
            - backup.created_at
        ).total_seconds()
        return 0.0 <= age <= self.rpo_seconds

    def restore_within_rto(
        self,
        *,
        started_at: datetime,
        verified_at: datetime,
    ) -> bool:
        for value, label in (
            (started_at, "started_at"),
            (verified_at, "verified_at"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        elapsed = (verified_at - started_at).total_seconds()
        return 0.0 <= elapsed <= self.rto_seconds


DEFAULT_RECOVERY_OBJECTIVES = RecoveryObjectives()

@dataclass(frozen=True)
class BackupEvidence:
    backup_id:str; source_host_id:str; failure_domain:str; created_at:datetime; content_digest:str
    def __post_init__(self):
        if self.created_at.tzinfo is None: raise ValueError("backup timestamp must be timezone-aware")
        if not all((self.backup_id.strip(),self.source_host_id.strip(),self.failure_domain.strip(),self.content_digest.strip())):
            raise ValueError("complete backup evidence required")
        if fullmatch(r"[0-9a-f]{64}",self.content_digest) is None: raise ValueError("backup digest must be lowercase SHA-256")

@dataclass(frozen=True)
class RestoreVerification:
    backup_id:str; verified_at:datetime; verifier:str; succeeded:bool
    def __post_init__(self):
        if self.verified_at.tzinfo is None: raise ValueError("restore verification time must be timezone-aware")
        if not self.verifier.strip(): raise ValueError("restore verifier required")

class RecoveryGuard:
    def require(
        self, backup: BackupEvidence, restore: RestoreVerification, *,
        target_failure_domain: str,
    ) -> None:
        if not isinstance(backup, BackupEvidence) or not isinstance(
            restore, RestoreVerification
        ):
            raise TypeError("typed backup and restore evidence required")
        if not isinstance(target_failure_domain, str) or not target_failure_domain.strip():
            raise ValueError("target failure domain must be nonempty")
        if backup.backup_id != restore.backup_id:
            raise RecoveryDenied("restore evidence is for another backup")
        if type(restore.succeeded) is not bool or not restore.succeeded:
            raise RecoveryDenied("backup has not passed independent restore verification")
        # An earlier restore does not verify a newer backup just because its
        # ID and verifier label match. Compare aware instants, not strings.
        if restore.verified_at < backup.created_at:
            raise RecoveryDenied("restore verification predates the backup")
        if backup.failure_domain == target_failure_domain:
            raise RecoveryDenied("backup is not isolated from target failure domain")
