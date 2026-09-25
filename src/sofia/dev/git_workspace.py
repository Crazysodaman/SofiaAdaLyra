"""Git-backed engineering isolation and exact-scope change control."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess

class GitWorkspaceError(RuntimeError): pass
class DirtyScopeError(GitWorkspaceError): pass
class ChangeScopeError(GitWorkspaceError): pass

@dataclass(frozen=True)
class GitSnapshot:
    head_sha: str
    changed_paths: tuple[str, ...]

def _normalise(path: str) -> str:
    return Path(path.replace("\\", "/")).as_posix().lstrip("./")

def path_in_scope(path: str, scopes: tuple[str, ...]) -> bool:
    p=_normalise(path)
    for scope in scopes:
        s=_normalise(scope).rstrip("/")
        if p==s or p.startswith(s+"/"):
            return True
    return False

class GitWorkspace:
    def __init__(self, root: Path) -> None:
        self.root=root.resolve()
        if not self.root.is_dir(): raise ValueError("workspace root must exist")

    def run(self,*args: str, check: bool=True) -> subprocess.CompletedProcess[str]:
        cp=subprocess.run(("git",*args),cwd=self.root,text=True,capture_output=True,check=False)
        if check and cp.returncode:
            raise GitWorkspaceError(cp.stderr.strip() or f"git {' '.join(args)} failed")
        return cp

    def head_sha(self) -> str:
        return self.run("rev-parse","HEAD").stdout.strip()

    def changed_paths(self) -> tuple[str,...]:
        out=self.run("status","--porcelain=v1","--untracked-files=all").stdout
        paths=[]
        for line in out.splitlines():
            raw=line[3:].strip()
            if " -> " in raw: raw=raw.split(" -> ",1)[1]
            paths.append(_normalise(raw.strip('"')))
        return tuple(sorted(set(paths)))

    def snapshot(self) -> GitSnapshot:
        return GitSnapshot(self.head_sha(),self.changed_paths())

    def require_head(self, expected_sha: str) -> None:
        actual=self.head_sha()
        if actual!=expected_sha:
            raise GitWorkspaceError(f"HEAD mismatch: expected {expected_sha}, got {actual}")

    def require_clean_scope(self, scopes: tuple[str,...]) -> None:
        dirty=tuple(p for p in self.changed_paths() if path_in_scope(p,scopes))
        if dirty: raise DirtyScopeError("approved scope already contains local changes: "+", ".join(dirty))

    def require_changes_within(self, scopes: tuple[str,...]) -> tuple[str,...]:
        changed=self.changed_paths()
        outside=tuple(p for p in changed if not path_in_scope(p,scopes))
        if outside: raise ChangeScopeError("changes outside approved scope: "+", ".join(outside))
        return changed

    def patch(self) -> str:
        # Intent-to-add makes new files visible to diff without staging content.
        untracked=[p for p in self.changed_paths() if self.run("ls-files","--error-unmatch","--",p,check=False).returncode!=0]
        if untracked: self.run("add","-N","--",*untracked)
        return self.run("diff","--binary","HEAD").stdout
