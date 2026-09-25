"""Bounded OpenCode adapter.

The adapter builds and optionally executes a fixed OpenCode invocation. Authority
must be established by the caller; this module cannot approve its own request.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil, subprocess
from .workspace import WorkspaceGuard

class OpenCodeExecutionError(RuntimeError): pass

@dataclass(frozen=True)
class EngineeringExecutionRequest:
    proposal_id: str
    base_sha: str
    prompt: str
    allowed_paths: tuple[str, ...]
    authorized: bool = False
    timeout_seconds: int = 900
    def __post_init__(self):
        if not self.proposal_id.strip() or not self.prompt.strip(): raise ValueError("proposal_id and prompt required")
        if not self.allowed_paths: raise ValueError("allowed_paths required")
        if self.timeout_seconds < 1: raise ValueError("timeout_seconds must be positive")

@dataclass(frozen=True)
class OpenCodeCommand:
    argv: tuple[str, ...]
    cwd: Path

@dataclass(frozen=True)
class EngineeringExecutionResult:
    proposal_id: str
    returncode: int
    stdout: str
    stderr: str

class OpenCodeAdapter:
    def __init__(self, workspace: Path, executable: str = "opencode") -> None:
        self.workspace=workspace.resolve()
        self.executable=executable

    def command(self, request: EngineeringExecutionRequest) -> OpenCodeCommand:
        if not request.authorized: raise PermissionError("engineering execution requires independent authorization")
        WorkspaceGuard(self.workspace, request.allowed_paths)
        exe=shutil.which(self.executable)
        if exe is None: raise OpenCodeExecutionError(f"OpenCode executable not found: {self.executable}")
        return OpenCodeCommand((exe,"run","--agent","sofia-build",request.prompt),self.workspace)

    def execute(self, request: EngineeringExecutionRequest) -> EngineeringExecutionResult:
        command=self.command(request)
        try:
            completed=subprocess.run(command.argv,cwd=command.cwd,text=True,capture_output=True,timeout=request.timeout_seconds,check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OpenCodeExecutionError(str(exc)) from exc
        return EngineeringExecutionResult(request.proposal_id,completed.returncode,completed.stdout,completed.stderr)
