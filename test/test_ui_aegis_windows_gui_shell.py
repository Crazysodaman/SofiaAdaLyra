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
        "Library > Catalog", "Library > Sources", "Library > Downloads",
        "Library > Installed", "Library > Storage", "Library > Hub",
        "Library > History",
    ):
        assert menu in source
    assert "No authenticated Platform management service is connected" in source
    assert "SOURCE: UNVERIFIED" in source
    assert "NOT OBSERVED" in source
    assert "Stale or changed revisions require review" in source
    assert "uninstall requires" in source.lower()
    assert "actionsByPage" in source
    assert "Enabled = $false" in source
    assert "HighContrast" in source
    assert "Get-AegisTheme" in source
    assert "Get-AegisBlockedReason" in source
    assert "AEGIS_GUI_NATIVE_CONSTRUCTION=PASS" in source


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
    assert "ACTIONS=DISABLED" in done.stdout
    assert "OFFLINE_STALE_RESTART_DENIED=FAIL_CLOSED" in done.stdout
    assert "BLOCK_STATES=STOP_ACTIVE,REVOKED,DENIED,STALE,UNKNOWN_GENERATION,RESTARTING,OFFLINE" in done.stdout
    assert "LIBRARY=UNAVAILABLE" in done.stdout
    assert "LIBRARY_INVENTORY=NOT_OBSERVED" in done.stdout
    assert "LIBRARY_ACTIONS=DISABLED" in done.stdout
    assert "INTERNET_FALLBACK=DISABLED" in done.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows WinForms construction probe")
def test_windows_native_controls_constructed_with_management_disabled():
    result = subprocess.run(
        [
            "powershell.exe", "-STA", "-NoProfile", "-NonInteractive",
            "-File", str(SHELL), "-UiProbe",
        ],
        capture_output=True, text=True, timeout=50,
    )
    assert result.returncode == 0, result.stderr
    assert "AEGIS_GUI_NATIVE_CONSTRUCTION=PASS" in result.stdout
    assert "ARTIFACT_LIBRARY_NAVIGATION=7" in result.stdout
    assert "LIBRARY_NAVIGATION_PROBE=PASS" in result.stdout
    for page in ("Catalog", "Sources", "Downloads", "Installed",
                 "Storage", "Hub", "History"):
        assert ("LIBRARY_PAGE_VERIFIED=Library > " + page +
                ";SOURCE=UNVERIFIED;ACTIONS=DISABLED") in result.stdout
    assert "LIBRARY_ACTIONS=DISABLED" in result.stdout
    assert "AUTHENTICATION=NOT_CONNECTED" in result.stdout
    assert "ACTIONS=DISABLED" in result.stdout
