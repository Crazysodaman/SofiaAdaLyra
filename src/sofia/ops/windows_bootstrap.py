"""Operator-approved Windows Fleet bootstrap for one explicitly named host.

The only remote action exposed here is launching the generated, hash-pinned
Fleet installer through authenticated CIM/DCOM. This is not a generic remote
shell. PowerShell owns the credential prompt; Python never receives the
password.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable
from uuid import UUID, uuid4

from .bootstrap import (
    AgentPackage,
    BootstrapCandidate,
    FleetBootstrapExecutor,
    FleetBootstrapPlanner,
    InstallAuthority,
    InstallReceipt,
)

_REQUIRED = (
    "agent.json",
    "certs/fleet-ca.pem",
    "certs/artemis-server.pem",
    "certs/artemis-server-key.pem",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_host(value: str) -> str:
    value = value.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    if not value or len(value) > 253 or any(ch not in allowed for ch in value):
        raise ValueError("invalid bootstrap host")
    return value


def _safe_windows_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} required")
    if re.fullmatch(r"[A-Za-z]:\\[A-Za-z0-9 _.\\-]+", value) is None:
        raise ValueError(f"{label} contains unsupported characters")
    path = PureWindowsPath(value)
    if not path.is_absolute() or not path.drive:
        raise ValueError(f"{label} must be an absolute Windows drive path")
    return str(path)


@dataclass(frozen=True)
class WindowsBootstrapEvidence:
    host_id: str
    node_id: UUID
    package_sha256: str
    process_id: int
    listen_port: int
    python_version: str


Launcher = Callable[[str, str, str], None]


def powershell_cim_launcher(host: str, credential_user: str, installer_path: str) -> None:
    host = _safe_host(host)
    installer_path = _safe_windows_path(installer_path, "installer path")
    if not credential_user.strip() or any(ch in credential_user for ch in "\r\n\0"):
        raise ValueError("credential user required")

    script = r"""
param(
    [Parameter(Mandatory=$true)][string]$ComputerName,
    [Parameter(Mandatory=$true)][string]$UserName,
    [Parameter(Mandatory=$true)][string]$InstallerPath
)
$ErrorActionPreference = "Stop"
$credential = Get-Credential -UserName $UserName -Message "Authorize Sofia Fleet bootstrap on $ComputerName"
if ($null -eq $credential) { throw "Credential prompt cancelled." }
$option = New-CimSessionOption -Protocol Dcom
$session = New-CimSession -ComputerName $ComputerName -Credential $credential -SessionOption $option -ErrorAction Stop
try {
    $command = 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $InstallerPath + '"'
    $arguments = @{CommandLine=$command}
    $result = Invoke-CimMethod -CimSession $session -ClassName Win32_Process -MethodName Create -Arguments $arguments -ErrorAction Stop
    if ([int]$result.ReturnValue -ne 0) { throw "Remote process creation failed with code $($result.ReturnValue)." }
    Write-Output "Sofia Fleet bootstrap launched on $ComputerName as PID $($result.ProcessId)."
}
finally {
    Remove-CimSession -CimSession $session -ErrorAction SilentlyContinue
}
"""
    with tempfile.TemporaryDirectory(prefix="sofia-fleet-cim-") as tmp:
        launcher = Path(tmp) / "launch.ps1"
        launcher.write_text(script, encoding="utf-8")
        completed = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(launcher),
                "-ComputerName", host,
                "-UserName", credential_user,
                "-InstallerPath", installer_path,
            ],
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"authenticated CIM bootstrap launch failed with exit code {completed.returncode}"
        )


def render_installer(
    *,
    stage_path: str,
    install_root: str,
    wheel_name: str,
    package_sha256: str,
    node_id: UUID,
    listen_port: int,
) -> str:
    stage_path = _safe_windows_path(stage_path, "stage path")
    install_root = _safe_windows_path(install_root, "install root")
    if not wheel_name or any(ch in wheel_name for ch in ('"', "'", "\\", "/", "\r", "\n")):
        raise ValueError("invalid wheel name")
    if len(package_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in package_sha256):
        raise ValueError("invalid package SHA-256")
    if not 1 <= listen_port <= 65535:
        raise ValueError("listen port out of range")

    return f"""$ErrorActionPreference = "Stop"
$Stage = '{stage_path}'
$Root = '{install_root}'
$WheelName = '{wheel_name}'
$ExpectedHash = '{package_sha256}'
$NodeId = '{node_id}'
$ListenPort = {listen_port}
$Receipt = Join-Path $Stage "bootstrap-receipt.json"
function Save-Receipt([hashtable]$Payload) {{
    $Payload | ConvertTo-Json -Depth 5 | Set-Content -Path $Receipt -Encoding UTF8
}}

try {{
    $Wheel = Join-Path $Stage $WheelName
    if (-not (Test-Path $Wheel -PathType Leaf)) {{ throw "Approved Fleet wheel missing." }}
    $ActualHash = (Get-FileHash -Algorithm SHA256 $Wheel).Hash.ToLowerInvariant()
    if ($ActualHash -ne $ExpectedHash) {{ throw "Fleet wheel hash mismatch." }}

    foreach ($Relative in @("agent.json","certs\\fleet-ca.pem","certs\\artemis-server.pem","certs\\artemis-server-key.pem")) {{
        if (-not (Test-Path (Join-Path $Stage $Relative) -PathType Leaf)) {{ throw "Required Fleet file missing: $Relative" }}
    }}

    New-Item -ItemType Directory -Force $Root | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $Root "certs") | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $Root "state") | Out-Null

    Copy-Item (Join-Path $Stage "agent.json") (Join-Path $Root "agent.json") -Force
    Copy-Item (Join-Path $Stage "certs\\fleet-ca.pem") (Join-Path $Root "certs\\fleet-ca.pem") -Force
    Copy-Item (Join-Path $Stage "certs\\artemis-server.pem") (Join-Path $Root "certs\\artemis-server.pem") -Force
    Copy-Item (Join-Path $Stage "certs\\artemis-server-key.pem") (Join-Path $Root "certs\\artemis-server-key.pem") -Force
    Copy-Item $Wheel (Join-Path $Root $WheelName) -Force

    $ServerKey = Join-Path $Root "certs\\artemis-server-key.pem"
    & icacls.exe $ServerKey /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw "Failed to restrict Fleet server private-key ACL." }}

    $ServiceName = "SofiaAdaLyraFleetAgent"
    $ManagedPython = Join-Path $Root ".venv\\Scripts\\python.exe"

    # Stop and remove the prior durable service before replacing its venv.
    $ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $ExistingService) {{
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        foreach ($Attempt in 1..15) {{
            Start-Sleep -Milliseconds 500
            $ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
            if ($null -eq $ExistingService -or $ExistingService.Status -eq "Stopped") {{
                break
            }}
        }}
        & sc.exe delete $ServiceName | Out-Null
        if ($LASTEXITCODE -ne 0) {{
            throw "Failed to remove prior Fleet agent service."
        }}
        Start-Sleep -Milliseconds 750
    }}

    # Clean up pre-service bootstrap agents from older releases.
    $ManagedProcesses = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {{
            $_.CommandLine -and
            $_.CommandLine.Contains($Root) -and
            (
                $_.CommandLine.Contains("sofia.distributed.agent_main") -or
                $_.CommandLine.Contains("agent_canary.py")
            )
        }}
    foreach ($ManagedProcess in $ManagedProcesses) {{
        Stop-Process -Id $ManagedProcess.ProcessId -Force -ErrorAction SilentlyContinue
    }}
    if ($ManagedProcesses) {{ Start-Sleep -Milliseconds 750 }}

    $Candidates = @()
    $Command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $Command) {{ $Candidates += $Command.Source }}
    $Candidates += Get-ChildItem "$env:LOCALAPPDATA\\Programs\\Python\\Python*\\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object {{ $_.FullName }}
    $Candidates += Get-ChildItem "$env:ProgramFiles\\Python*\\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object {{ $_.FullName }}
    $Candidates += Get-ChildItem "C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python*\\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object {{ $_.FullName }}
    $BasePython = $Candidates | Where-Object {{ $_ -and (Test-Path $_ -PathType Leaf) }} | Select-Object -First 1
    if (-not $BasePython) {{ throw "Python executable not found for bootstrap account." }}

    $Venv = Join-Path $Root ".venv"
    if (Test-Path $Venv) {{
        $Removed = $false
        foreach ($Attempt in 1..5) {{
            try {{
                Remove-Item -Recurse -Force $Venv -ErrorAction Stop
                $Removed = $true
                break
            }}
            catch {{
                if ($Attempt -eq 5) {{ throw }}
                Start-Sleep -Milliseconds 750
            }}
        }}
        if (-not $Removed -and (Test-Path $Venv)) {{ throw "Fleet venv cleanup failed." }}
    }}
    & $BasePython -m venv $Venv
    if ($LASTEXITCODE -ne 0) {{ throw "venv creation failed." }}

    $AgentPython = Join-Path $Venv "Scripts\\python.exe"
    & $AgentPython -m pip install --disable-pip-version-check --no-deps (Join-Path $Root $WheelName)
    if ($LASTEXITCODE -ne 0) {{ throw "Fleet wheel installation failed." }}
    & $AgentPython -m pip install --disable-pip-version-check cryptography pywin32
    if ($LASTEXITCODE -ne 0) {{ throw "Fleet service dependencies installation failed." }}

    $ConfigPath = Join-Path $Root "agent.json"
    $Config = & $AgentPython -m sofia.distributed.agent_main --config $ConfigPath --check-config 2>&1
    if ($LASTEXITCODE -ne 0) {{ throw "agent config validation failed: $Config" }}
    & $AgentPython -c "import cryptography, win32serviceutil, sofia, sofia.distributed.agent_main, sofia.distributed.agent_tools, sofia.distributed.windows_agent_service, sofia.distributed.windows_agent_service_admin"
    if ($LASTEXITCODE -ne 0) {{ throw "Fleet service import smoke failed." }}
    $PythonVersion = (& $AgentPython --version 2>&1 | Out-String).Trim()

    $FirewallName = "SofiaAdaLyra Fleet Agent $ListenPort"
    Get-NetFirewallRule -DisplayName $FirewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $FirewallName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $ListenPort -RemoteAddress LocalSubnet -Profile Any | Out-Null

    $InstallOutput = & $AgentPython -m sofia.distributed.windows_agent_service_admin install --config $ConfigPath 2>&1
    if ($LASTEXITCODE -ne 0) {{
        throw "Fleet agent service installation failed: $InstallOutput"
    }}
    $StartOutput = & $AgentPython -m sofia.distributed.windows_agent_service_admin start 2>&1
    if ($LASTEXITCODE -ne 0) {{
        throw "Fleet agent service start failed: $StartOutput"
    }}

    $Listener = $null
    $AgentService = $null
    foreach ($Attempt in 1..20) {{
        Start-Sleep -Seconds 1
        $AgentService = Get-CimInstance Win32_Service -Filter ("Name='" + $ServiceName + "'") -ErrorAction SilentlyContinue
        if ($null -eq $AgentService) {{
            continue
        }}
        if ($AgentService.State -eq "Stopped") {{
            throw "Fleet agent service stopped during startup."
        }}
        if (
            $AgentService.State -eq "Running" -and
            [int]$AgentService.ProcessId -gt 0
        ) {{
            $ServicePid = [int]$AgentService.ProcessId
            $Listener = Get-NetTCPConnection -State Listen -LocalPort $ListenPort -ErrorAction SilentlyContinue |
                Where-Object {{ [int]$_.OwningProcess -eq $ServicePid }} |
                Select-Object -First 1
            if ($null -ne $Listener) {{ break }}
        }}
    }}
    if ($null -eq $Listener -or $null -eq $AgentService) {{
        $ObservedState = if ($null -eq $AgentService) {{ "missing" }} else {{ [string]$AgentService.State }}
        throw "Fleet agent service is not listening on the approved port. service_state=$ObservedState"
    }}

    $ValidateOutput = & $AgentPython -m sofia.distributed.windows_agent_service_admin validate --config $ConfigPath 2>&1
    if ($LASTEXITCODE -ne 0) {{
        throw "Fleet agent service registration validation failed: $ValidateOutput"
    }}

    $AgentPid = [int]$AgentService.ProcessId
    Set-Content (Join-Path $Root "agent.pid") ([string]$AgentPid) -Encoding ASCII
    Save-Receipt @{{
        status = "verified"
        host_id = $env:COMPUTERNAME
        node_id = $NodeId
        package_sha256 = $ActualHash
        process_id = $AgentPid
        listen_port = [int]$ListenPort
        python_version = $PythonVersion
        service_name = $ServiceName
        service_state = [string]$AgentService.State
    }}

    # The controller only needs the receipt after success. Scrub the staged
    # server private key and copied payload locally on Artemis so an SMB ACL
    # quirk cannot leave sensitive bootstrap material behind.
    Remove-Item (Join-Path $Stage "certs\\artemis-server-key.pem") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Stage "certs\\artemis-server.pem") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Stage "certs\\fleet-ca.pem") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Stage $WheelName) -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Stage "agent.json") -Force -ErrorAction SilentlyContinue
}}
catch {{
    if (Test-Path $AgentPython -PathType Leaf) {{
        & $AgentPython -m sofia.distributed.windows_agent_service_admin stop 2>$null | Out-Null
        & $AgentPython -m sofia.distributed.windows_agent_service_admin remove 2>$null | Out-Null
    }}
    else {{
        Stop-Service -Name "SofiaAdaLyraFleetAgent" -Force -ErrorAction SilentlyContinue
        & sc.exe delete "SofiaAdaLyraFleetAgent" 2>$null | Out-Null
    }}
    # Also remove any legacy hidden bootstrap process from older installs.
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {{
            $_.CommandLine -and
            $_.CommandLine.Contains($Root) -and
            (
                $_.CommandLine.Contains("sofia.distributed.agent_main") -or
                $_.CommandLine.Contains("agent_canary.py")
            )
        }} |
        ForEach-Object {{
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }}
    Start-Sleep -Milliseconds 500
    Save-Receipt @{{
        status = "failed"
        host_id = $env:COMPUTERNAME
        node_id = $NodeId
        package_sha256 = $ExpectedHash
        error = "$($_.Exception.GetType().Name): $($_.Exception.Message)"
    }}
    exit 1
}}
"""


class WindowsCimBootstrapInstaller:
    def __init__(
        self,
        *,
        host: str,
        credential_user: str,
        bundle_directory: Path,
        wheel_path: Path,
        controller_stage_directory: Path,
        remote_stage_path: str,
        node_id: UUID,
        install_root: str = r"C:\ProgramData\SofiaAdaLyra\FleetAgent",
        listen_port: int = 7443,
        timeout_seconds: float = 300.0,
        launcher: Launcher = powershell_cim_launcher,
    ) -> None:
        self.host = _safe_host(host)
        self.credential_user = credential_user
        self.bundle_directory = Path(bundle_directory)
        self.wheel_path = Path(wheel_path)
        self.controller_stage_directory = Path(controller_stage_directory)
        self.remote_stage_path = _safe_windows_path(remote_stage_path, "remote stage path")
        self.install_root = _safe_windows_path(install_root, "install root")
        self.node_id = node_id
        self.listen_port = listen_port
        self.timeout_seconds = timeout_seconds
        self.launcher = launcher
        self._active_controller_stage_directory: Path | None = None
        self._active_remote_stage_path: str | None = None

    def _new_stage_paths(self) -> tuple[Path, str]:
        suffix = uuid4().hex[:12]
        controller = self.controller_stage_directory.with_name(
            f"{self.controller_stage_directory.name}-{suffix}"
        )
        remote_base = PureWindowsPath(self.remote_stage_path)
        remote = str(remote_base.with_name(f"{remote_base.name}-{suffix}"))
        return controller, remote

    def prepare_stage(self, package: AgentPackage) -> Path:
        if not self.bundle_directory.is_dir():
            raise FileNotFoundError("Fleet bootstrap bundle not found")
        if not self.wheel_path.is_file():
            raise FileNotFoundError("Fleet wheel not found")
        if sha256_file(self.wheel_path) != package.sha256:
            raise RuntimeError("Fleet wheel hash does not match approved package")
        for relative in _REQUIRED:
            if not (self.bundle_directory / Path(relative)).is_file():
                raise FileNotFoundError(f"Fleet bundle missing {relative}")

        stage, remote_stage = self._new_stage_paths()
        self._active_controller_stage_directory = stage
        self._active_remote_stage_path = remote_stage
        (stage / "certs").mkdir(parents=True, exist_ok=False)
        (stage / "state").mkdir(parents=True, exist_ok=True)
        agent_source = self.bundle_directory / "agent.json"
        agent_payload = json.loads(agent_source.read_text(encoding="utf-8-sig"))
        if not isinstance(agent_payload, dict):
            raise ValueError("Fleet agent config must be a JSON object")
        agent_payload["listen_port"] = self.listen_port
        (stage / "agent.json").write_text(
            json.dumps(agent_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for name in ("fleet-ca.pem", "artemis-server.pem", "artemis-server-key.pem"):
            shutil.copy2(self.bundle_directory / "certs" / name, stage / "certs" / name)
        shutil.copy2(self.wheel_path, stage / self.wheel_path.name)

        installer = stage / "install.ps1"
        installer.write_text(
            render_installer(
                stage_path=remote_stage,
                install_root=self.install_root,
                wheel_name=self.wheel_path.name,
                package_sha256=package.sha256,
                node_id=self.node_id,
                listen_port=self.listen_port,
            ),
            encoding="utf-8",
        )
        return installer

    def wait_for_receipt(self) -> WindowsBootstrapEvidence:
        if self._active_controller_stage_directory is None:
            raise RuntimeError("bootstrap stage has not been prepared")
        target = self._active_controller_stage_directory / "bootstrap-receipt.json"
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if target.is_file():
                try:
                    payload = json.loads(target.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError):
                    time.sleep(0.5)
                    continue
                if payload.get("status") == "failed":
                    raise RuntimeError(f"remote bootstrap failed: {payload.get('error', 'unknown')}")
                if payload.get("status") == "verified":
                    return WindowsBootstrapEvidence(
                        host_id=str(payload["host_id"]),
                        node_id=UUID(str(payload["node_id"])),
                        package_sha256=str(payload["package_sha256"]),
                        process_id=int(payload["process_id"]),
                        listen_port=int(payload["listen_port"]),
                        python_version=str(payload["python_version"]),
                    )
            time.sleep(1.0)
        raise TimeoutError("timed out waiting for Windows Fleet bootstrap receipt")

    def install(self, candidate: BootstrapCandidate, package: AgentPackage) -> InstallReceipt:
        if candidate.platform.casefold() != "windows":
            raise ValueError("Windows bootstrap requires a Windows candidate")
        if candidate.host_id.casefold() != self.host.casefold():
            raise ValueError("bootstrap candidate does not match approved host")

        installer = self.prepare_stage(package)
        if self._active_controller_stage_directory is None or self._active_remote_stage_path is None:
            raise RuntimeError("bootstrap stage was not initialized")
        (self._active_controller_stage_directory / "bootstrap-receipt.json").unlink(missing_ok=True)
        remote_installer = str(PureWindowsPath(self._active_remote_stage_path) / installer.name)
        self.launcher(self.host, self.credential_user, remote_installer)
        evidence = self.wait_for_receipt()

        if evidence.host_id.casefold() != self.host.casefold():
            raise RuntimeError("bootstrap host identity mismatch")
        if evidence.node_id != self.node_id:
            raise RuntimeError("bootstrap node identity mismatch")
        if evidence.package_sha256 != package.sha256:
            raise RuntimeError("bootstrap package hash mismatch")

        print(
            f"remote bootstrap verified: host={evidence.host_id} "
            f"pid={evidence.process_id} port={evidence.listen_port} "
            f"python={evidence.python_version}"
        )
        try:
            shutil.rmtree(self._active_controller_stage_directory)
        except OSError as exc:
            print(f"warning: verified bootstrap stage cleanup failed: {exc}")
        return InstallReceipt(
            candidate.host_id,
            package.package_id,
            package.version,
            package.sha256,
            True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.ops.windows_bootstrap")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--host", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--credential-user", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--stage-dir", required=True)
    parser.add_argument("--remote-stage-path", required=True)
    parser.add_argument("--listen-port", type=int, default=7443)
    args = parser.parse_args(argv)

    if not args.approve:
        print("Fleet bootstrap refused: --approve is required.")
        return 2

    try:
        wheel = Path(args.wheel).resolve()
        package = AgentPackage(
            "sofia-fleet-agent",
            "0.1.0",
            sha256_file(wheel),
            str(wheel),
        )
        candidate = BootstrapCandidate(
            host_id=_safe_host(args.host),
            platform="windows",
            architecture="x86_64",
            discovery_source="operator-approved-windows-bootstrap",
            inside_approved_scope=True,
            trusted_bootstrap_available=True,
        )
        plan = FleetBootstrapPlanner().plan(
            candidate,
            package,
            authority=InstallAuthority.OPERATOR_APPROVED,
        )
        installer = WindowsCimBootstrapInstaller(
            host=args.host,
            credential_user=args.credential_user,
            bundle_directory=Path(args.bundle_dir),
            wheel_path=wheel,
            controller_stage_directory=Path(args.stage_dir),
            remote_stage_path=args.remote_stage_path,
            node_id=UUID(args.node_id),
            listen_port=args.listen_port,
        )
        receipt = FleetBootstrapExecutor().execute(plan, installer)
        print(
            f"bootstrap accepted: {receipt.host_id} "
            f"{receipt.package_id} {receipt.version} sha256={receipt.sha256}"
        )
        return 0
    except Exception as exc:
        print(f"Fleet Windows bootstrap failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
