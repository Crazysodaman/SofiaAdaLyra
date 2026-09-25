"""Isolated DEV workflow: build/test in a detached worktree, then separately apply/commit."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
from tempfile import TemporaryDirectory
import subprocess
from .git_workspace import GitWorkspace,GitWorkspaceError,path_in_scope
from .opencode import EngineeringExecutionRequest,OpenCodeAdapter

@dataclass(frozen=True)
class EngineeringCandidate:
    proposal_id:str
    base_sha:str
    patch:str
    changed_paths:tuple[str,...]
    allowed_paths:tuple[str,...]
    tests_passed:bool|None

class EngineeringWorkflow:
    def __init__(self,workspace:Path,executable:str="opencode")->None:
        self.workspace=workspace.resolve(); self.executable=executable
        self.git=GitWorkspace(self.workspace); self._applied_paths:tuple[str,...]=(); self._applied_hashes:dict[str,str|None]={}; self._applied_existed:dict[str,bool]={}

    def build(self,request:EngineeringExecutionRequest)->EngineeringCandidate:
        if not request.authorized: raise PermissionError("build requires independent authorization")
        self.git.require_head(request.base_sha)
        self.git.require_clean_scope(request.allowed_paths)
        with TemporaryDirectory(prefix="sofia-dev-") as td:
            sandbox=Path(td)/"worktree"
            add=subprocess.run(("git","worktree","add","--detach",str(sandbox),request.base_sha),
                cwd=self.workspace,text=True,capture_output=True,check=False)
            if add.returncode: raise GitWorkspaceError(add.stderr.strip() or "unable to create isolated worktree")
            try:
                adapter=OpenCodeAdapter(sandbox,self.executable)
                result=adapter.execute(request)
                sg=GitWorkspace(sandbox)
                changed=sg.require_changes_within(request.allowed_paths)
                patch=sg.patch()
                if result.returncode!=0: raise GitWorkspaceError("OpenCode candidate execution failed")
                if request.tests and result.tests_passed is not True: raise GitWorkspaceError("candidate tests failed")
                return EngineeringCandidate(request.proposal_id,request.base_sha,patch,changed,request.allowed_paths,result.tests_passed)
            finally:
                subprocess.run(("git","worktree","remove","--force",str(sandbox)),
                    cwd=self.workspace,text=True,capture_output=True,check=False)

    @staticmethod
    def _patch_paths(workspace:Path,patch:str)->tuple[str,...]:
        if not patch: return ()
        cp=subprocess.run(("git","apply","--numstat","-"),cwd=workspace,input=patch,text=True,capture_output=True,check=False)
        if cp.returncode: raise GitWorkspaceError(cp.stderr.strip() or "unable to inspect candidate patch")
        paths=[]
        for line in cp.stdout.splitlines():
            parts=line.split("\t")
            if len(parts)>=3: paths.append(parts[-1])
        return tuple(sorted(set(paths)))

    def apply(self,candidate:EngineeringCandidate,*,authorized:bool)->tuple[str,...]:
        if not authorized: raise PermissionError("applying engineering candidate requires separate authorization")
        self.git.require_head(candidate.base_sha)
        self.git.require_clean_scope(candidate.allowed_paths)
        patch_paths=self._patch_paths(self.workspace,candidate.patch)
        if patch_paths!=tuple(sorted(set(candidate.changed_paths))):
            raise GitWorkspaceError("candidate patch paths do not match reviewed changed_paths")
        outside=tuple(p for p in patch_paths if not path_in_scope(p,candidate.allowed_paths))
        if outside: raise GitWorkspaceError("candidate patch escapes approved scope: "+", ".join(outside))
        if not candidate.patch:
            self._applied_paths=(); return ()
        check=subprocess.run(("git","apply","--check","-"),cwd=self.workspace,input=candidate.patch,
            text=True,capture_output=True,check=False)
        if check.returncode: raise GitWorkspaceError(check.stderr.strip() or "candidate patch no longer applies")
        existed={path:(self.workspace/path).exists() for path in patch_paths}
        applied=subprocess.run(("git","apply","-"),cwd=self.workspace,input=candidate.patch,
            text=True,capture_output=True,check=False)
        if applied.returncode: raise GitWorkspaceError(applied.stderr.strip() or "candidate patch failed")
        self._applied_paths=patch_paths
        self._applied_hashes={}; self._applied_existed=existed
        for path in patch_paths:
            target=self.workspace/path
            self._applied_hashes[path]=sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        return self.git.changed_paths()

    def rollback_applied(self,*,authorized:bool)->None:
        if not authorized: raise PermissionError("rollback requires separate authorization")
        if not self._applied_paths: return
        for path,expected in self._applied_hashes.items():
            target=self.workspace/path
            current=sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            if current!=expected: raise GitWorkspaceError(f"refusing rollback because reviewed path changed after apply: {path}")
        tracked=[path for path in self._applied_paths if self._applied_existed.get(path,False)]
        created=[path for path in self._applied_paths if not self._applied_existed.get(path,False)]
        if tracked: self.git.run("restore","--worktree","--staged","--",*tracked)
        for path in created:
            target=self.workspace/path
            if target.is_file(): target.unlink()
            elif target.exists(): raise GitWorkspaceError(f"refusing rollback of non-file candidate path: {path}")
        self._applied_paths=(); self._applied_hashes={}; self._applied_existed={}

    def commit(self,message:str,*,authorized:bool)->str:
        if not authorized: raise PermissionError("commit requires separate authorization")
        if not message.strip(): raise ValueError("commit message required")
        if not self._applied_paths: raise GitWorkspaceError("no reviewed candidate paths are pending commit")
        self.git.run("add","--",*self._applied_paths)
        self.git.run("commit","-m",message,"--",*self._applied_paths)
        self._applied_paths=(); self._applied_hashes={}; self._applied_existed={}
        return self.git.head_sha()

    def push(self,branch:str,*,authorized:bool,remote:str="origin")->None:
        if not authorized: raise PermissionError("push requires separate authorization")
        if not branch.strip() or branch.startswith("-"): raise ValueError("exact branch name required")
        self.git.run("push",remote,f"HEAD:refs/heads/{branch}")
