"""Opt-in wired launcher path delegates to the canonical Python CLI.

The launchers must remain preview-only unless every wired trust input is
present, and they must never perform OS service changes themselves.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui
ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "packaging/installers/install-aegis.sh"
POWERSHELL = ROOT / "packaging/installers/Install-Aegis.ps1"


def _compile_echo_executable(path: Path) -> None:
    candidates = [
        Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"),
    ]
    compiler = next((item for item in candidates if item.is_file()), None)
    if compiler is None:
        pytest.skip("C# compiler unavailable for disposable native runtime fixture")
    source = path.with_suffix(".cs")
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


def _write_echo_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="ascii")
    path.chmod(0o700)


def test_wired_launchers_are_opt_in_and_reuse_the_canonical_python_cli():
    bash = BASH.read_text(encoding="utf-8")
    windows = POWERSHELL.read_text(encoding="utf-8")
    assert "--wired" in bash
    assert "$Wired" in windows
    assert "-Wired" in windows
    assert "platform_installer_cli" in bash
    assert "platform_installer_cli" in windows
    for source in (bash, windows):
        assert "--release-root" in source or "$ReleaseRoot" in source
        assert "--bundled-python" in source or "$BundledPython" in source
        for disallowed in ("sudo systemctl ", "Start-Service ", "New-Service ",
                           "Invoke-Expression ", "curl | bash"):
            assert disallowed not in source


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_wired_path_requires_complete_inputs():
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(POWERSHELL),
         "-Wired", "-Operation", "verify", "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "Wired installer requires" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_wired_path_invokes_bundled_python_without_service_mutation(tmp_path):
    release_root = tmp_path / "release"
    release_root.mkdir()
    fake_python = tmp_path / "fake-python.cmd"
    fake_python.write_text("@echo %*\r\n@exit /b 0\r\n", encoding="ascii")
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(POWERSHELL),
         "-Wired", "-Operation", "verify",
         "-ReleaseRoot", str(release_root),
         "-BundledPython", str(fake_python),
         "-MinimumRevision", "1", "-NoColor"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_cli" in result.stdout
    assert "--release-root" in result.stdout
    assert "verify" in result.stdout
    assert "systemctl" not in result.stdout
    assert "Start-Service" not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="Linux Bash runner only")
def test_bash_wired_path_execs_bundled_python_cli(tmp_path):
    release_root = tmp_path / "release"
    release_root.mkdir()
    fake_python = tmp_path / "fake-python"
    fake_python.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="ascii")
    fake_python.chmod(0o700)
    result = subprocess.run(
        ["bash", str(BASH), "--wired", "--operation", "verify",
         "--release-root", str(release_root),
         "--bundled-python", str(fake_python),
         "--minimum-revision", "1", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_cli" in result.stdout
    assert "verify" in result.stdout
    assert "systemctl" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_wired_discovers_exactly_one_bundled_runtime(tmp_path):
    release_root = tmp_path / "release"
    runtime = release_root / "runtime" / "python" / "python.exe"
    _compile_echo_executable(runtime)
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(POWERSHELL),
         "-Wired", "-Operation", "verify",
         "-ReleaseRoot", str(release_root),
         "-MinimumRevision", "1", "-NoColor", "-Json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_cli" in result.stdout
    assert "--release-root" in result.stdout
    assert "verify" in result.stdout
    assert "--json" in result.stdout
    assert "\n-I\n" not in result.stdout
    assert "systemctl" not in result.stdout
    assert "Start-Service" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_wired_refuses_missing_bundled_runtime(tmp_path):
    release_root = tmp_path / "release"
    release_root.mkdir()
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(POWERSHELL),
         "-Wired", "-Operation", "verify",
         "-ReleaseRoot", str(release_root),
         "-MinimumRevision", "1", "-NoColor", "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "Wired bundled runtime is missing" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_wired_refuses_redirected_runtime_directory(tmp_path):
    release_root = tmp_path / "release"
    release_root.mkdir()
    outside = tmp_path / "outside"
    (outside / "python").mkdir(parents=True)
    (outside / "python" / "python.exe").write_bytes(b"MZ" + b"0" * 64)
    junction = release_root / "runtime"
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True, text=True,
    )
    if made.returncode != 0:
        pytest.skip("junction creation is unavailable in this environment")
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(POWERSHELL),
         "-Wired", "-Operation", "verify",
         "-ReleaseRoot", str(release_root),
         "-MinimumRevision", "1", "-NoColor", "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "Wired bundled runtime is missing" in result.stderr


def _posix_runtime_host() -> bool:
    return os.name != "nt" and platform.system() == "Linux" and \
        platform.machine().lower() in ("x86_64", "amd64")


@pytest.mark.skipif(not _posix_runtime_host(), reason="x86_64 Linux Bash runner only")
def test_bash_wired_discovers_exactly_one_bundled_runtime(tmp_path):
    release_root = tmp_path / "release"
    runtime = release_root / "runtime" / "python" / "bin" / "python3.12"
    _write_echo_script(runtime)
    result = subprocess.run(
        ["bash", str(BASH), "--wired", "--operation", "verify",
         "--release-root", str(release_root),
         "--minimum-revision", "1", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "platform_installer_cli" in result.stdout
    assert "--release-root" in result.stdout
    assert "verify" in result.stdout
    assert "--json" in result.stdout
    assert " -I " not in f" {result.stdout} "


@pytest.mark.skipif(not _posix_runtime_host(), reason="x86_64 Linux Bash runner only")
def test_bash_wired_refuses_missing_ambiguous_or_redirected_runtime(tmp_path):
    missing = tmp_path / "missing"
    missing.mkdir()
    empty = subprocess.run(
        ["bash", str(BASH), "--wired", "--operation", "verify",
         "--release-root", str(missing), "--minimum-revision", "1", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert empty.returncode == 2
    assert "Exactly one bundled Python runtime" in empty.stderr

    ambiguous = tmp_path / "ambiguous"
    _write_echo_script(ambiguous / "runtime" / "python" / "bin" / "python3.12")
    _write_echo_script(ambiguous / "runtime" / "python" / "bin" / "python3")
    both = subprocess.run(
        ["bash", str(BASH), "--wired", "--operation", "verify",
         "--release-root", str(ambiguous), "--minimum-revision", "1", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert both.returncode == 2
    assert "Exactly one bundled Python runtime" in both.stderr

    redirected = tmp_path / "redirected"
    redirected.mkdir()
    outside = tmp_path / "outside-runtime"
    _write_echo_script(outside / "python" / "bin" / "python3.12")
    os.symlink(outside, redirected / "runtime", target_is_directory=True)
    linked = subprocess.run(
        ["bash", str(BASH), "--wired", "--operation", "verify",
         "--release-root", str(redirected), "--minimum-revision", "1", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert linked.returncode == 2
    assert "Wired bundled runtime" in linked.stderr or "symlink" in linked.stderr
