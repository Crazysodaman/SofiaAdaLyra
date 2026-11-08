"""Aegis Windows GUI stays optional, themed and strictly read-only."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "packaging/gui/Start-AegisControlCenter.ps1"
THEME = ROOT / "contracts/ui/aegis-theme-v1.json"


def test_gui_shell_is_separately_installed_and_core_free():
    source = SHELL.read_text(encoding="utf-8")
    assert THEME.exists()
    assert "aegis-theme-v1.json" in source
    assert "aegis.ui.theme.v1" in source
    for menu in (
        "Platform Overview", "Core Manager", "Module Manager",
        "Fleet", "Settings", "Security & Approvals",
        "Updates & Recovery", "Diagnostics",
    ):
        assert menu in source
    assert "No authenticated Platform management service is connected" in source
    assert "SOURCE: UNVERIFIED" in source
    assert "NOT OBSERVED" in source
    assert "Get-AegisTheme" in source


def test_gui_shell_does_not_install_or_grant_permissions():
    source = SHELL.read_text(encoding="utf-8")
    for forbidden in (
        "Start-Service ", "Stop-Service ", "Set-Service ", "New-Service ",
        "Invoke-Expression ", "Remove-Item ", "Invoke-RestMethod ",
        "Get-Credential ", "OwnerSecretStore(", "sofia.db",
    ):
        assert forbidden not in source


@pytest.mark.skipif(os.name != "nt", reason="native WinForms needs Windows")
def test_windows_gui_check_mode_is_headless_and_no_service_actions():
    done = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-File", str(SHELL), "-Check",
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    assert "AEGIS_GUI=READ_ONLY_SHELL" in done.stdout
    assert "THEME=aegis.ui.theme.v1" in done.stdout
    assert "SERVICE=UNAVAILABLE" in done.stdout
    assert "AUTHENTICATION=NOT_CONNECTED" in done.stdout
    assert "PRODUCTION_AUTHORIZED=FALSE" in done.stdout
