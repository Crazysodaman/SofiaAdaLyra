"""Isolated DEV workflow: build/test in a detached worktree, then separately apply/commit."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
from tempfile import TemporaryDirectory
import subprocess
import sys
from .git_workspace import GitWorkspace,GitWorkspaceError,path_in_scope
from .opencode import (
    EngineeringExecutionRequest, OpenCodeAdapter, OpenCodeCommand,
    _run_engineering_process,
)

@dataclass(frozen=True)
class EngineeringCandidate:
    proposal_id:str
    base_sha:str
    patch:str
    changed_paths:tuple[str,...]
    allowed_paths:tuple[str,...]
    tests_passed:bool|None
    iterations:int=1
    tests:tuple[str,...]=()
    verification_output_sha256:str|None=None

class EngineeringWorkflow:
    def __init__(self,workspace:Path,executable:str="opencode",agent:str|None=None)->None:
        self.workspace=workspace.resolve(); self.executable=executable; self.agent=agent
        self.git=GitWorkspace(self.workspace); self._applied_paths:tuple[str,...]=(); self._applied_hashes:dict[str,str|None]={}; self._applied_existed:dict[str,bool]={}

    @staticmethod
    def _verification(
        sandbox:Path,
        request:EngineeringExecutionRequest,
    )->subprocess.CompletedProcess[str]:
        return _run_engineering_process(
            OpenCodeCommand(
                (sys.executable,"-m","pytest","-q",*request.tests), sandbox,
            ),
            timeout_seconds=request.timeout_seconds,
        )

    def build(self,request:EngineeringExecutionRequest)->EngineeringCandidate:
        self.git.require_head(request.base_sha)
        self.git.require_clean_scope(request.allowed_paths)
        with TemporaryDirectory(prefix="sofia-dev-") as td:
            sandbox=Path(td)/"worktree"
            add=subprocess.run(("git","worktree","add","--detach",str(sandbox),request.base_sha),
                cwd=self.workspace,text=True,capture_output=True,check=False)
            if add.returncode: raise GitWorkspaceError(add.stderr.strip() or "unable to create isolated worktree")
            try:
                adapter=OpenCodeAdapter(sandbox,self.executable,self.agent)
                sg=GitWorkspace(sandbox)
                feedback=""
                verification_output=""
                for iteration in range(1,request.max_iterations+1):
                    target_context=(
                        "\n\nThe host will verify these exact pytest targets:\n"+
                        "\n".join(f"- {item}" for item in request.tests)
                        if request.tests else ""
                    )
                    iteration_request=EngineeringExecutionRequest(
                        proposal_id=request.proposal_id,
                        base_sha=request.base_sha,
                        prompt=request.prompt+target_context+feedback,
                        allowed_paths=request.allowed_paths,
                        authorized=True,
                        timeout_seconds=request.timeout_seconds,
                        tests=(),
                        max_iterations=request.max_iterations,
                    )
                    result=adapter.execute(iteration_request)
                    changed=sg.require_changes_within(request.allowed_paths)
                    if not changed:
                        verification_output="OpenCode produced no candidate changes."
                        passed=False
                    elif result.returncode!=0:
                        verification_output=(result.stdout+"\n"+result.stderr)[-8000:]
                        passed=False
                    elif request.tests:
                        verification=self._verification(sandbox,request)
                        verification_output=(verification.stdout+"\n"+verification.stderr)[-8000:]
                        passed=verification.returncode==0
                    else:
                        passed=True
                    if passed:
                        patch=sg.patch()
                        if not patch.strip():
                            raise GitWorkspaceError(
                                "candidate changed paths but produced no reviewable patch"
                            )
                        digest=(
                            sha256(verification_output.encode("utf-8")).hexdigest()
                            if verification_output else None
                        )
                        return EngineeringCandidate(
                            request.proposal_id,request.base_sha,patch,changed,
                            request.allowed_paths,
                            True if request.tests else None,
                            iteration,request.tests,digest,
                        )
                    if iteration<request.max_iterations:
                        feedback=(
                            "\n\nThe host verification attempt failed. Diagnose and repair "
                            "the candidate in the same approved scope, then leave it ready "
                            "for another host-run verification. Failure output:\n"+
                            verification_output
                        )
                raise GitWorkspaceError(
                    f"candidate verification failed after {request.max_iterations} iterations"
                )
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

    def apply(self,candidate:EngineeringCandidate,*,authorized:bool=False)->tuple[str,...]:
        if type(authorized) is not bool: raise TypeError("authorized must be boolean")
        if not authorized: raise PermissionError("candidate apply requires explicit authority")
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

    def rollback_applied(self,*,authorized:bool=False)->None:
        if type(authorized) is not bool: raise TypeError("authorized must be boolean")
        if not authorized: raise PermissionError("candidate rollback requires explicit authority")
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

    def commit(self,message:str,*,authorized:bool=False)->str:
        if type(authorized) is not bool: raise TypeError("authorized must be boolean")
        if not authorized: raise PermissionError("candidate commit requires explicit authority")
        if not message.strip(): raise ValueError("commit message required")
        if not self._applied_paths: raise GitWorkspaceError("no reviewed candidate paths are pending commit")
        self.git.run("add","--",*self._applied_paths)
        self.git.run("commit","-m",message,"--",*self._applied_paths)
        self._applied_paths=(); self._applied_hashes={}; self._applied_existed={}
        return self.git.head_sha()

    def push(self,branch:str,*,remote:str="origin",authorized:bool=False)->None:
        if type(authorized) is not bool: raise TypeError("authorized must be boolean")
        if not authorized: raise PermissionError("candidate push requires explicit authority")
        if not branch.strip() or branch.startswith("-"): raise ValueError("exact branch name required")
        self.git.run("push",remote,f"HEAD:refs/heads/{branch}")
