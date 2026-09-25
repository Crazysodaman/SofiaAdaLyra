"""Isolated DEV workflow: build/test in a detached worktree, then separately apply/commit."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from .git_workspace import GitWorkspace, GitWorkspaceError
from .opencode import EngineeringExecutionRequest, OpenCodeAdapter

@dataclass(frozen=True)
class EngineeringCandidate:
    proposal_id: str
    base_sha: str
    patch: str
    changed_paths: tuple[str,...]
    tests_passed: bool | None

class EngineeringWorkflow:
    def __init__(self, workspace: Path, executable: str="opencode") -> None:
        self.workspace=workspace.resolve(); self.executable=executable
        self.git=GitWorkspace(self.workspace)

    def build(self, request: EngineeringExecutionRequest) -> EngineeringCandidate:
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
                return EngineeringCandidate(request.proposal_id,request.base_sha,patch,changed,result.tests_passed)
            finally:
                subprocess.run(("git","worktree","remove","--force",str(sandbox)),
                    cwd=self.workspace,text=True,capture_output=True,check=False)

    def apply(self,candidate: EngineeringCandidate,*,authorized: bool) -> tuple[str,...]:
        if not authorized: raise PermissionError("applying engineering candidate requires separate authorization")
        self.git.require_head(candidate.base_sha)
        if not candidate.patch: return ()
        check=subprocess.run(("git","apply","--check","-"),cwd=self.workspace,input=candidate.patch,
            text=True,capture_output=True,check=False)
        if check.returncode: raise GitWorkspaceError(check.stderr.strip() or "candidate patch no longer applies")
        apply=subprocess.run(("git","apply","-"),cwd=self.workspace,input=candidate.patch,
            text=True,capture_output=True,check=False)
        if apply.returncode: raise GitWorkspaceError(apply.stderr.strip() or "candidate patch failed")
        return self.git.changed_paths()

    def commit(self,message: str,*,authorized: bool) -> str:
        if not authorized: raise PermissionError("commit requires separate authorization")
        if not message.strip(): raise ValueError("commit message required")
        self.git.run("add","-A")
        self.git.run("commit","-m",message)
        return self.git.head_sha()

    def push(self,branch: str,*,authorized: bool,remote: str="origin") -> None:
        if not authorized: raise PermissionError("push requires separate authorization")
        if not branch.strip() or branch.startswith("-"): raise ValueError("exact branch name required")
        self.git.run("push",remote,f"HEAD:refs/heads/{branch}")
