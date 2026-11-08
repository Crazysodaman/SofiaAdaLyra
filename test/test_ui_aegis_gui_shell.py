"""Native Windows GUI shell contract: live authority remains unavailable."""
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "ui" / "Start-AegisControlCenter.ps1"


def test_gui_shell_is_sourced_from_canonical_theme_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "aegis-theme-v1.json", "Aegis Platform Control Center",
        "Core Manager", "Module Manager", "Settings",
        "Security / Approvals", "Updates / Recovery", "Diagnostics",
        "UNVERIFIED", "Management service not connected",
        "No actions are enabled",
    ):
        assert token in source
    for forbidden in (
        "Start-Service ", "New-Service ", "Remove-Service ",
        "Invoke-Expression ", "ExecutionApprovalVerifier(",
        "CanonicalSQLiteGuard(", "Set-Content ", "Add-Content ",
    ):
        assert forbidden not in source


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell native shell only")
def test_gui_theme_and_safe_preflight_in_windows_powershell():
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-File", str(SCRIPT), "-Check"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "AEGIS_GUI_PREFLIGHT=PASS" in result.stdout
    assert "THEME=aegis.ui.theme.v1" in result.stdout
    assert "STATUS=UNVERIFIED" in result.stdout
    assert "HOST_OPERATIONS=DISABLED" in result.stdout
    assert "STATE_WRITES=NONE" in result.stdout
