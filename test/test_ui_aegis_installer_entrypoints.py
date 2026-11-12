"""AG-D011 preview-only installer entrypoint tests on disposable CI hosts.

No script may execute installation before signed-release authority is wired.
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


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None,
                    reason="Debian Bash runs on Linux; Windows runs PowerShell")
def test_debian_readonly_preflight_uses_no_ansi_and_never_claims_install():
    result = subprocess.run(
        ["bash", str(BASH), "--check"], capture_output=True, text=True,
        env={**os.environ, "NO_COLOR": "1"}, timeout=15, check=True,
    )
    assert "MODE=PREVIEW_ONLY" in result.stdout
    assert "SIGNED_RELEASE=NOT_VERIFIED" in result.stdout
    assert "RESULT=NO_CHANGES_MADE" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None,
                    reason="Debian Bash runs on Linux; Windows runs PowerShell")
def test_bash_interactive_refused_without_tty_and_unknown_option_rejected():
    result = subprocess.run(
        ["bash", str(BASH)], input="", capture_output=True,
        text=True, timeout=15,
    )
    assert result.returncode == 2
    assert "requires a terminal" in result.stderr
    invalid = subprocess.run(
        ["bash", str(BASH), "--authorize-all"],
        capture_output=True, text=True, timeout=15,
    )
    assert invalid.returncode == 2


def test_both_entrypoints_use_one_shared_palette_not_a_second_registry():
    bash = BASH.read_text(encoding="utf-8")
    powershell = WINDOWS.read_text(encoding="utf-8")
    assert THEME.is_file()
    assert "aegis-theme-v1.json" in bash
    assert "aegis-theme-v1.json" in powershell
    assert "NO_COLOR" in bash and "NO_COLOR" in powershell
    assert "SIGNED_RELEASE=NOT_VERIFIED" in bash
    assert "SIGNED_RELEASE=NOT_VERIFIED" in powershell
    assert "RESULT=NO_CHANGES_MADE" in bash
    assert "RESULT=NO_CHANGES_MADE" in powershell
    assert "PREVIEW ONLY" in bash and "PREVIEW ONLY" in powershell
    for command in ("Start-Service ", "New-Service ", "Remove-Service ",
                    "sudo systemctl ", "Invoke-Expression ", "curl | bash"):
        assert command not in bash
        assert command not in powershell


@pytest.mark.skipif(os.name != "nt", reason="requires Windows PowerShell")
def test_powershell_installer_preflight_is_readonly():
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File",
         str(WINDOWS), "-Check"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "MODE=PREVIEW_ONLY" in result.stdout
    assert "RESULT=NO_CHANGES_MADE" in result.stdout
    assert "SIGNED_RELEASE=NOT_VERIFIED" in result.stdout
