from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True,slots=True)
class CleanupCandidate:
    path:Path
    reason:str
    protected:bool=False


@dataclass(frozen=True,slots=True)
class CleanupPlan:
    keep:tuple[CleanupCandidate,...]
    delete:tuple[CleanupCandidate,...]

    @property
    def safe_to_apply(self)->bool:
        return all(not item.protected for item in self.delete)


class ReleaseCleanupPlanner:
    """Plan release cleanup without touching active or rollback releases."""

    def __init__(self,releases_root:Path)->None:
        if not isinstance(releases_root,Path):
            raise TypeError("releases_root must be a Path")
        self.root=releases_root

    def plan(
        self,
        *,
        active_release_id:str|None,
        previous_release_id:str|None,
        retain_additional:int=2,
    )->CleanupPlan:
        if type(retain_additional) is not int or retain_additional<0:
            raise ValueError("retain_additional must be nonnegative")
        if not self.root.exists():
            return CleanupPlan((),())
        dirs=tuple(
            sorted(
                (p for p in self.root.iterdir() if p.is_dir()),
                key=lambda p:p.stat().st_mtime,
                reverse=True,
            )
        )
        protected_ids={
            value for value in (active_release_id,previous_release_id)
            if isinstance(value,str) and value
        }
        keep=[]; delete=[]; extras_kept=0
        for path in dirs:
            if path.name in protected_ids:
                keep.append(CleanupCandidate(path,"active-or-rollback",True))
                continue
            if extras_kept<retain_additional:
                keep.append(CleanupCandidate(path,"retained-recent-release",False))
                extras_kept+=1
            else:
                delete.append(CleanupCandidate(path,"superseded-release",False))
        return CleanupPlan(tuple(keep),tuple(delete))

    @staticmethod
    def apply(
        plan:CleanupPlan,
        *,
        recovery_verified:bool,
    )->tuple[Path,...]:
        if not isinstance(plan,CleanupPlan):
            raise TypeError("plan must be CleanupPlan")
        if recovery_verified is not True:
            raise PermissionError(
                "cleanup requires independently verified recovery evidence"
            )
        if not plan.safe_to_apply:
            raise PermissionError("cleanup plan contains protected paths")
        removed=[]
        for item in plan.delete:
            path=item.path
            if path.is_symlink():
                raise PermissionError("cleanup refuses symlinked release paths")
            if not path.is_dir():
                continue
            import shutil
            shutil.rmtree(path)
            removed.append(path)
        return tuple(removed)
