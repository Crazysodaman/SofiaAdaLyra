"""Guided one-step installer launcher contract.

Static assertions protect the default guided path, elevation, trust-anchor
requirement and the absence of bypass/manual approval flags. Disposable fixtures
exercise only a fake bundled runtime; no test elevates, installs a service or
invokes the guided Python module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = ROOT / "packaging" / "installers"
BASH = INSTALLERS / "install-aegis.sh"
WINDOWS = INSTALLERS / "Install-Aegis.ps1"
FALLBACK = INSTALLERS / "Start-AegisSetup.ps1"
BUILD = INSTALLERS / "build-aegis-setup.ps1"
LAUNCHER_SOURCE = INSTALLERS / "AegisSetupLauncher.cs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _windows_runtime_available() -> bool:
    return os.name == "nt"


def _linux_runtime_available() -> bool:
    return os.name != "nt" and platform.system() == "Linux" and \
        platform.machine().lower() in ("x86_64", "amd64")


def _compile_echo_exe(path: Path) -> None:
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
    ]
    compiler = next((item for item in candidates if item.is_file()), None)
    if compiler is None:
        pytest.skip("C# compiler unavailable for disposable runtime fixture")
    source = path.parent / "echo-args.cs"
    path.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "using System; public static class EchoArgs {"
        " public static int Main(string[] args) {"
        " foreach (var item in args) Console.WriteLine(item); return 0; } }",
        encoding="ascii",
    )
    result = subprocess.run(
        [str(compiler), "/nologo", "/target:exe", f"/out:{path}", str(source)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0 or not path.is_file():
        pytest.skip(f"native echo executable could not be built: {result.stderr}")


def _python_echo_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="ascii")
    path.chmod(0o755)


def _write_trust(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "trusted-publisher.pem").write_text(
        "-----BEGIN PUBLIC KEY-----\n"
        "ZGlzcG9zYWJsZS10ZXN0LW9ubHktcHVibGlzaGVyLWtleQ==\n"
        "-----END PUBLIC KEY-----\n",
        encoding="ascii",
    )
    (directory / "trust.json").write_text(
        '{"schema":"aegis.installer.trust.v1","publisher":"disposable-test-only"}\n',
        encoding="ascii",
    )


def test_default_path_is_guided_not_preview_only():
    bash = _text(BASH)
    windows = _text(WINDOWS)
    for source in (bash, windows):
        assert "platform_installer_guided" in source
        assert "platform_installer_cli" not in source
        assert "trusted-publisher.pem" in source
        assert "trust.json" in source
        assert "out of band" in source
        assert "--wired" not in source and "$Wired" not in source
        assert "PREVIEW ONLY" not in source
        assert "MODE=INSTALL" in source
    assert "-Check" in windows and "--check" in bash
    assert "-Operation" in windows and "--operation" in bash
    assert "-Json" in windows and "--json" in bash
    assert "-NoColor" in windows and "--no-color" in bash


def test_default_guided_argument_block_has_no_manual_trust_or_approval_inputs():
    bash = _text(BASH)
    windows = _text(WINDOWS)
    windows_block = windows.split("function Invoke-AegisGuidedInstaller", 1)[1] \
        .split("if ($VerifySeed)", 1)[0]
    bash_block = bash.split("run_guided() {", 1)[1] \
        .split('if [[ "$MODE" == help ]]', 1)[0]
    for block in (windows_block, bash_block):
        assert "platform_installer_guided" in block
        assert "--bundle-root" in block
        assert "--check" in block
        assert "--operation" in block
        assert "--json" in block
        assert "--no-color" in block
        for forbidden in (
            "approval-id", "ApprovalId", "safe-state", "SafeState",
            "bundled-python", "BundledPython", "trusted-seed",
            "TrustedSeed", "trusted-bootstrap", "TrustedBootstrap",
        ):
            assert forbidden not in block


def test_no_bypass_or_manual_approval_flags_exist():
    for path in (BASH, WINDOWS):
        source = _text(path)
        for forbidden in (
            "--authorize-all", "--approve", "--unsafe", "--yes",
            "--approval-id", "--code-approval-id", "--safe-state",
            "-ApprovalId", "-CodeApprovalId", "-SafeState",
        ):
            assert forbidden not in source, (path.name, forbidden)


def test_elevation_uses_approved_os_mechanism_and_preserves_bundle_path():
    bash = _text(BASH)
    windows = _text(WINDOWS)
    assert 'exec sudo -- "$SCRIPT_PATH" "${SCRIPT_ARGS[@]}"' in bash
    assert "Start-Process" in windows
    assert "-Verb RunAs" in windows
    assert "Invoke-AegisElevatedRelaunch" in windows
    assert "-BundleRoot" in windows.split("function Invoke-AegisElevatedRelaunch", 1)[1]
    for source in (bash, windows):
        assert "-ExecutionPolicy Bypass" not in source
        assert "Set-MpPreference" not in source
        assert "Add-MpPreference" not in source


def test_windows_launcher_build_script_and_powershell_fallback():
    build = _text(BUILD)
    source = _text(LAUNCHER_SOURCE)
    fallback = _text(FALLBACK)
    assert "AegisSetupLauncher.cs" in build
    assert "csc.exe" in build
    assert "csc.exe is unavailable" in build
    assert "/target:winexe" in build
    assert "signtool" in build
    assert "/sha1" in build
    assert "SigningThumbprint" in build
    assert "/pa" in build
    assert "Pfx" not in build and "PrivateKey" not in build
    assert "Aegis-Setup.exe" in source
    assert 'Verb = "runas"' in source
    assert "Install-Aegis.ps1" in source
    assert "-Verb RunAs" in fallback
    assert "Install-Aegis.ps1" in fallback
    assert "Start-AegisSetup.ps1" in build


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_windows_build_script_produces_double_click_launcher(tmp_path):
    if not (Path(os.environ.get("WINDIR", r"C:\Windows"))
            / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe").is_file():
        pytest.skip("C# compiler unavailable for launcher build")
    output = tmp_path / "Aegis-Setup.exe"
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(BUILD), "-OutputPath", str(output)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file() and output.stat().st_size > 0
    assert "POWERSHELL_FALLBACK=" in result.stdout
    assert "AUTHENTICODE=NOT_SIGNED" in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_windows_check_previews_through_guided_orchestrator_with_fake_runtime(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "Install-Aegis.ps1"
    shutil.copyfile(WINDOWS, script)
    _write_trust(installer)
    _compile_echo_exe(bundle / "runtime" / "python" / "python.exe")

    owner_trust = tmp_path / "owner-trust"
    _write_trust(owner_trust)
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(script), "-Check", "-Json",
         "-InstallRoot", r"D:\Aegis", "-TrustRoot", str(owner_trust)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_guided" in result.stdout
    assert "--bundle-root" in result.stdout
    assert str(bundle) in result.stdout
    assert "--check" in result.stdout
    assert "--json" in result.stdout
    assert "--install-root" in result.stdout
    assert r"D:\Aegis" in result.stdout
    assert "--trust-root" in result.stdout
    assert str(owner_trust) in result.stdout
    assert "--approval-id" not in result.stdout
    assert "--wired" not in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_windows_check_denies_missing_trust_anchor(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "Install-Aegis.ps1"
    shutil.copyfile(WINDOWS, script)
    _compile_echo_exe(bundle / "runtime" / "python" / "python.exe")

    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(script), "-Check", "-Json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["schema"] == "aegis.installer.guided-launcher.v1"
    assert payload["result"] == "BLOCKED"
    assert "trust anchor" in payload["message"]
    assert "platform_installer_guided" not in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_windows_check_denies_missing_bundled_runtime(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "Install-Aegis.ps1"
    shutil.copyfile(WINDOWS, script)
    _write_trust(installer)

    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(script), "-Check", "-Json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "Exactly one bundled Python runtime" in payload["message"]
    assert "platform_installer_guided" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_windows_check_denies_missing_release_bundle(tmp_path):
    installer = tmp_path / "media" / "installer"
    installer.mkdir(parents=True)
    script = installer / "Install-Aegis.ps1"
    shutil.copyfile(WINDOWS, script)

    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(script), "-Check", "-Json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "release bundle not found" in payload["message"]


@pytest.mark.skipif(not _linux_runtime_available(), reason="x86_64 Linux Bash only")
def test_bash_check_previews_through_guided_orchestrator_with_fake_runtime(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "install-aegis.sh"
    shutil.copyfile(BASH, script)
    _write_trust(installer)
    _python_echo_script(bundle / "runtime" / "python" / "bin" / "python3.12")

    result = subprocess.run(
        ["bash", str(script), "--check", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_guided" in result.stdout
    assert "--bundle-root" in result.stdout
    assert str(bundle) in result.stdout
    assert "--check" in result.stdout
    assert "--json" in result.stdout
    assert "--approval-id" not in result.stdout
    assert "--wired" not in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _linux_runtime_available(), reason="x86_64 Linux Bash only")
def test_bash_operation_status_forwards_without_elevation(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "install-aegis.sh"
    shutil.copyfile(BASH, script)
    _write_trust(installer)
    _python_echo_script(bundle / "runtime" / "python" / "bin" / "python3.12")

    result = subprocess.run(
        ["bash", str(script), "--operation", "status", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_guided" in result.stdout
    assert "--operation status" in result.stdout
    assert "sudo" not in result.stdout


@pytest.mark.skipif(not _linux_runtime_available(), reason="x86_64 Linux Bash only")
def test_bash_check_denies_missing_trust_anchor(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "install-aegis.sh"
    shutil.copyfile(BASH, script)
    _python_echo_script(bundle / "runtime" / "python" / "bin" / "python3.12")

    result = subprocess.run(
        ["bash", str(script), "--check", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["schema"] == "aegis.installer.guided-launcher.v1"
    assert payload["result"] == "BLOCKED"
    assert "trust anchor" in payload["message"]
    assert "platform_installer_guided" not in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _linux_runtime_available(), reason="x86_64 Linux Bash only")
def test_bash_check_denies_missing_bundled_runtime(tmp_path):
    bundle = tmp_path / "media" / "bundle"
    installer = bundle / "installer"
    installer.mkdir(parents=True)
    (bundle / "release-manifest.json").write_text("{}\n", encoding="ascii")
    script = installer / "install-aegis.sh"
    shutil.copyfile(BASH, script)
    _write_trust(installer)

    result = subprocess.run(
        ["bash", str(script), "--check", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "Exactly one bundled Python runtime" in payload["message"]
    assert "platform_installer_guided" not in result.stdout
