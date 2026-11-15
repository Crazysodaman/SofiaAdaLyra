"""Opt-in wired launcher path delegates to the canonical Python CLI.

The launchers must remain preview-only unless every wired trust input is
present, and they must never perform OS service changes themselves.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui
ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "packaging/installers/install-aegis.sh"
POWERSHELL = ROOT / "packaging/installers/Install-Aegis.ps1"


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
