"""Verified, bounded OpenCode engineering executor."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil, subprocess
from .workspace import WorkspaceGuard, WorkspaceViolation

class OpenCodeExecutionError(RuntimeError): pass

@dataclass(frozen=True)
class EngineeringExecutionRequest:
    proposal_id:str; base_sha:str; prompt:str; allowed_paths:tuple[str,...]
    authorized:bool=False; timeout_seconds:int=900; tests:tuple[str,...]=()
    def __post_init__(self):
        if not self.proposal_id.strip() or not self.prompt.strip(): raise ValueError("proposal_id and prompt required")
        if len(self.base_sha)!=40: raise ValueError("base_sha must be a full git SHA")
        if not self.allowed_paths: raise ValueError("allowed_paths required")
        if self.timeout_seconds<1: raise ValueError("timeout_seconds must be positive")

@dataclass(frozen=True)
class OpenCodeCommand: argv:tuple[str,...]; cwd:Path

@dataclass(frozen=True)
class EngineeringExecutionResult:
    proposal_id:str; returncode:int; stdout:str; stderr:str
    base_sha:str=""; changed_paths:tuple[str,...]=(); tests_passed:bool|None=None; rolled_back:bool=False

class OpenCodeAdapter:
    def __init__(self,workspace:Path,executable:str="opencode")->None:
        self.workspace=workspace.resolve(); self.executable=executable
    def _git(self,*args:str)->subprocess.CompletedProcess[str]:
        return subprocess.run(("git",*args),cwd=self.workspace,text=True,capture_output=True,check=False)
    def verify_base(self,request:EngineeringExecutionRequest)->None:
        head=self._git("rev-parse","HEAD")
        if head.returncode or head.stdout.strip()!=request.base_sha:
            raise OpenCodeExecutionError("workspace HEAD does not match authorized base_sha")
    def changed_paths(self)->tuple[str,...]:
        r=self._git("status","--porcelain=v1","--untracked-files=all")
        if r.returncode: raise OpenCodeExecutionError(r.stderr.strip() or "git status failed")
        paths=[]
        for line in r.stdout.splitlines():
            raw=line[3:].strip()
            if " -> " in raw: raw=raw.split(" -> ",1)[1]
            paths.append(raw.strip('"'))
        return tuple(sorted(set(paths)))
    def verify_scope(self,request:EngineeringExecutionRequest,paths:tuple[str,...])->None:
        guard=WorkspaceGuard(self.workspace,request.allowed_paths)
        for path in paths: guard.resolve_allowed(path)
    def command(self,request:EngineeringExecutionRequest)->OpenCodeCommand:
        if not request.authorized: raise PermissionError("engineering execution requires independent authorization")
        WorkspaceGuard(self.workspace,request.allowed_paths)
        exe=shutil.which(self.executable)
        if exe is None: raise OpenCodeExecutionError(f"OpenCode executable not found: {self.executable}")
        return OpenCodeCommand((exe,"run","--agent","sofia-build",request.prompt),self.workspace)
    def execute(self,request:EngineeringExecutionRequest)->EngineeringExecutionResult:
        self.verify_base(request); command=self.command(request)
        before=self.changed_paths()
        if before: self.verify_scope(request,before)
        try:
            completed=subprocess.run(command.argv,cwd=command.cwd,text=True,capture_output=True,timeout=request.timeout_seconds,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc: raise OpenCodeExecutionError(str(exc)) from exc
        changed=self.changed_paths()
        try: self.verify_scope(request,changed)
        except WorkspaceViolation as exc:
            raise OpenCodeExecutionError(f"OpenCode changed path outside approved scope: {exc}") from exc
        tests_passed=None
        if completed.returncode==0 and request.tests:
            test=subprocess.run(("pytest","-q",*request.tests),cwd=self.workspace,text=True,capture_output=True,timeout=request.timeout_seconds,check=False)
            tests_passed=test.returncode==0
            completed=subprocess.CompletedProcess(completed.args,completed.returncode,completed.stdout+"\n"+test.stdout,completed.stderr+"\n"+test.stderr)
        return EngineeringExecutionResult(request.proposal_id,completed.returncode,completed.stdout,completed.stderr,request.base_sha,changed,tests_passed,False)
