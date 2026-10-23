"""Verified, bounded OpenCode engineering executor."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os, re, shutil, signal, subprocess, sys


class WorkspaceViolation(RuntimeError): pass

class WorkspaceGuard:
    def __init__(self, root: Path, allowed_paths: tuple[str, ...]) -> None:
        self.root=root.resolve()
        for item in allowed_paths:
            path=Path(item.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise WorkspaceViolation("approved write scope must remain inside workspace")
        self.allowed=frozenset(
            Path(item.replace("\\", "/")).as_posix().lstrip("./").rstrip("/")
            for item in allowed_paths
        )
        if not self.root.is_dir(): raise ValueError("workspace root must exist")
        if not self.allowed: raise ValueError("allowed_paths required")

    def resolve_allowed(self, relative_path: str) -> Path:
        raw=Path(relative_path.replace("\\", "/"))
        if raw.is_absolute() or ".." in raw.parts:
            raise WorkspaceViolation("path escapes workspace")
        normalized=raw.as_posix().lstrip("./")
        if not any(normalized==scope or normalized.startswith(scope+"/") for scope in self.allowed):
            raise WorkspaceViolation(f"path outside approved change scope: {relative_path}")
        candidate=(self.root / normalized).resolve(strict=False)
        try: candidate.relative_to(self.root)
        except ValueError as exc: raise WorkspaceViolation("path escapes workspace") from exc
        # Existing symlinks/reparse-like links are never accepted as write targets.
        current=self.root
        for part in Path(normalized).parts:
            current=current / part
            if current.exists() and current.is_symlink(): raise WorkspaceViolation(f"symlink write target denied: {relative_path}")
        return candidate

class OpenCodeExecutionError(RuntimeError): pass
class OpenCodeConfigurationError(OpenCodeExecutionError): pass
class OpenCodeMissingExecutableError(OpenCodeExecutionError): pass
class OpenCodeTimeoutError(OpenCodeExecutionError): pass
class OpenCodeScopeError(OpenCodeExecutionError): pass


def engineering_worker_environment() -> dict[str, str]:
    """Minimal environment: omit tokens, cloud credentials, and app secrets."""
    allowed = (
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
        "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "PYTHONUTF8",
    )
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    result["SOFIA_ENGINEERING_WORKER"] = "1"
    return result


def _run_engineering_process(
    command: OpenCodeCommand, *, timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command.argv, cwd=command.cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=engineering_worker_environment(), stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.communicate()
        raise OpenCodeTimeoutError(
            f"OpenCode exceeded {timeout_seconds}s"
        ) from exc
    return subprocess.CompletedProcess(
        command.argv, process.returncode, stdout, stderr,
    )

@dataclass(frozen=True)
class EngineeringExecutionRequest:
    proposal_id:str; base_sha:str; prompt:str; allowed_paths:tuple[str,...]
    authorized:bool=False; timeout_seconds:int=900; tests:tuple[str,...]=()
    max_iterations:int=3
    def __post_init__(self):
        if not isinstance(self.proposal_id,str) or not isinstance(self.prompt,str):
            raise TypeError("proposal_id and prompt must be strings")
        if not self.proposal_id.strip() or not self.prompt.strip(): raise ValueError("proposal_id and prompt required")
        if len(self.prompt)>20000: raise ValueError("engineering prompt is too large")
        if len(self.base_sha)!=40: raise ValueError("base_sha must be a full git SHA")
        if not self.allowed_paths: raise ValueError("allowed_paths required")
        if type(self.authorized) is not bool: raise TypeError("authorized must be boolean")
        if type(self.timeout_seconds) is not int or not 30<=self.timeout_seconds<=3600:
            raise ValueError("timeout_seconds must be in 30..3600")
        if type(self.max_iterations) is not int or not 1<=self.max_iterations<=5:
            raise ValueError("max_iterations must be in 1..5")
        if len(self.allowed_paths)>128 or len(set(self.allowed_paths))!=len(self.allowed_paths):
            raise ValueError("allowed_paths must be unique and bounded")
        for scope in self.allowed_paths:
            if not isinstance(scope,str) or not scope.strip() or len(scope)>512:
                raise ValueError("approved write scopes must be bounded nonempty paths")
            path=Path(scope.replace("\\","/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("approved write scopes must remain inside workspace")
        for target in self.tests:
            if not isinstance(target,str) or not target.strip() or len(target)>512:
                raise ValueError("test targets must be bounded nonempty strings")
            path=target.split("::",1)[0].replace("\\","/")
            if target.startswith("-") or Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("test targets must be relative selectors, not options")

@dataclass(frozen=True)
class OpenCodeCommand: argv:tuple[str,...]; cwd:Path

@dataclass(frozen=True)
class EngineeringExecutionResult:
    proposal_id:str; returncode:int; stdout:str; stderr:str
    base_sha:str=""; changed_paths:tuple[str,...]=(); tests_passed:bool|None=None; rolled_back:bool=False

class OpenCodeAdapter:
    def __init__(self,workspace:Path,executable:str="opencode",agent:str|None=None)->None:
        self.workspace=workspace.resolve()
        if not isinstance(executable,str) or not executable.strip() or len(executable)>512:
            raise OpenCodeConfigurationError("OpenCode executable configuration is invalid")
        self.executable=executable.strip()
        if agent is not None and re.fullmatch(r"[A-Za-z0-9_-]{1,64}",agent) is None:
            raise ValueError("OpenCode agent name is invalid")
        self.agent=agent
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
        if not request.authorized:
            raise PermissionError("OpenCode execution requires explicit authority")
        WorkspaceGuard(self.workspace,request.allowed_paths)
        exe=shutil.which(self.executable)
        if exe is None: raise OpenCodeMissingExecutableError(f"OpenCode executable not found: {self.executable}")
        scope="\n".join(f"- {item}" for item in request.allowed_paths)
        tests="\n".join(f"- {item}" for item in request.tests) or "- none supplied"
        engineering_prompt=(
            "You are the implementation engine for a governed Sofía DEV task.\n"
            "Inspect the repository, implement the task completely, and repair any "
            "relevant failures. You may read the repository, but write only inside "
            "the approved paths below. Do not commit, push, modify Git configuration, "
            "or touch runtime state/secrets.\n\nTASK\n"+request.prompt+
            "\n\nAPPROVED WRITE SCOPE\n"+scope+
            "\n\nHOST-RUN VERIFICATION TARGETS\n"+tests
        )
        agent_args=() if self.agent is None else ("--agent",self.agent)
        return OpenCodeCommand((exe,"run",*agent_args,engineering_prompt),self.workspace)
    def execute(self,request:EngineeringExecutionRequest)->EngineeringExecutionResult:
        self.verify_base(request); command=self.command(request)
        before=self.changed_paths()
        if before: self.verify_scope(request,before)
        try:
            completed=_run_engineering_process(
                command, timeout_seconds=request.timeout_seconds,
            )
        except OSError as exc:
            raise OpenCodeExecutionError(str(exc)) from exc
        changed=self.changed_paths()
        try: self.verify_scope(request,changed)
        except WorkspaceViolation as exc:
            raise OpenCodeScopeError(f"OpenCode changed path outside approved scope: {exc}") from exc
        total_bytes=0
        for relative in changed:
            target=(self.workspace/relative)
            if target.is_file(): total_bytes+=target.stat().st_size
        if total_bytes>64*1024*1024:
            raise OpenCodeScopeError("OpenCode candidate exceeds the 64 MiB changed-file budget")
        stdout=completed.stdout[-262144:]
        stderr=completed.stderr[-262144:]
        completed=subprocess.CompletedProcess(completed.args,completed.returncode,stdout,stderr)
        tests_passed=None
        if completed.returncode==0 and request.tests:
            test=_run_engineering_process(
                OpenCodeCommand(
                    (sys.executable,"-m","pytest","-q",*request.tests),
                    self.workspace,
                ),
                timeout_seconds=request.timeout_seconds,
            )
            tests_passed=test.returncode==0
            completed=subprocess.CompletedProcess(
                completed.args,completed.returncode,
                (completed.stdout+"\n"+test.stdout)[-262144:],
                (completed.stderr+"\n"+test.stderr)[-262144:],
            )
        return EngineeringExecutionResult(request.proposal_id,completed.returncode,completed.stdout,completed.stderr,request.base_sha,changed,tests_passed,False)
