"""Aegis guided installer entrypoint contract on disposable hosts.

No script may elevate, install a service or perform lifecycle work during these
tests. The one-step default is the guided orchestrator; legacy read-only seed and
publisher checks remain available but are not the default.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui

ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "packaging" / "installers" / "install-aegis.sh"
WINDOWS = ROOT / "packaging" / "installers" / "Install-Aegis.ps1"
THEME = ROOT / "contracts" / "ui" / "aegis-theme-v1.json"


def test_both_entrypoints_default_to_the_guided_installer_and_shared_palette():
    bash = BASH.read_text(encoding="utf-8")
    powershell = WINDOWS.read_text(encoding="utf-8")
    assert THEME.is_file()
    for source in (bash, powershell):
        assert "aegis-theme-v1.json" in source
        assert "NO_COLOR" in source
        assert "platform_installer_guided" in source
        assert "--bundle-root" in source
        assert "trusted-publisher.pem" in source
        assert "trust.json" in source
        assert "SAFE/STOP" in source
        assert "MODE=INSTALL" in source
        assert "PREVIEW ONLY" not in source
    for command in ("Start-Service ", "New-Service ", "Remove-Service ",
                    "sudo systemctl ", "Invoke-Expression ", "curl | bash",
                    "platform_installer_cli"):
        assert command not in bash
        assert command not in powershell


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None,
                    reason="Debian Bash runs on Linux; Windows runs PowerShell")
def test_bash_check_without_media_denies_with_actionable_message():
    result = subprocess.run(
        ["bash", str(BASH), "--check"], capture_output=True, text=True,
        env={**os.environ, "NO_COLOR": "1"}, timeout=15,
    )
    assert result.returncode == 2
    assert "release bundle not found" in result.stderr
    assert "MODE=PREVIEW_ONLY" not in result.stdout


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None,
                    reason="Debian Bash runs on Linux; Windows runs PowerShell")
def test_bash_unknown_option_rejected():
    result = subprocess.run(
        ["bash", str(BASH), "--authorize-all"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell")
def test_powershell_check_without_media_denies_before_elevation():
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File",
         str(WINDOWS), "-Check"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "release bundle not found" in result.stderr
    assert "MODE=PREVIEW_ONLY" not in result.stdout
