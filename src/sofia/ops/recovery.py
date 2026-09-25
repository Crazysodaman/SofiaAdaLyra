"""Recovery, backup evidence and staged update policy for fleet operations."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class RecoveryDenied(PermissionError): pass

@dataclass(frozen=True)
class BackupEvidence:
    backup_id:str; source_host_id:str; failure_domain:str; created_at:datetime; content_digest:str
    def __post_init__(self):
        if self.created_at.tzinfo is None: raise ValueError("backup timestamp must be timezone-aware")
        if not all((self.backup_id.strip(),self.source_host_id.strip(),self.failure_domain.strip(),self.content_digest.strip())):
            raise ValueError("complete backup evidence required")

@dataclass(frozen=True)
class RestoreVerification:
    backup_id:str; verified_at:datetime; verifier:str; succeeded:bool
    def __post_init__(self):
        if self.verified_at.tzinfo is None: raise ValueError("restore verification time must be timezone-aware")
        if not self.verifier.strip(): raise ValueError("restore verifier required")

class RecoveryGuard:
    def require(self,backup:BackupEvidence,restore:RestoreVerification,*,target_failure_domain:str)->None:
        if backup.backup_id!=restore.backup_id: raise RecoveryDenied("restore evidence is for another backup")
        if not restore.succeeded: raise RecoveryDenied("backup has not passed independent restore verification")
        if backup.failure_domain==target_failure_domain: raise RecoveryDenied("backup is not isolated from target failure domain")

class UpdateRing(str,Enum):
    CANARY="canary"; EARLY="early"; GENERAL="general"

@dataclass(frozen=True)
class HostUpdateAssignment:
    host_id:str; ring:UpdateRing

class UpdatePlanner:
    def order(self,assignments:tuple[HostUpdateAssignment,...])->tuple[HostUpdateAssignment,...]:
        rank={UpdateRing.CANARY:0,UpdateRing.EARLY:1,UpdateRing.GENERAL:2}
        return tuple(sorted(assignments,key=lambda a:(rank[a.ring],a.host_id)))
    def next_ring_allowed(self,completed_ring:UpdateRing,*,health_verified:bool,rollback_ready:bool)->bool:
        return health_verified and rollback_ready and completed_ring in (UpdateRing.CANARY,UpdateRing.EARLY)
