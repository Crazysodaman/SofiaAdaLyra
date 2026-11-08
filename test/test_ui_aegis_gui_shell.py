"""Native Windows Aegis GUI must remain safe without management IPC."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging/ui/Start-AegisControlCenter.ps1"


def test_gui_shell_must_not_adopt_other_service_or_expose_privileged_operations():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "aegis-theme-v1.json" in source
    assert "PresentationFramework" in source
    assert "UI_MODE=READ_ONLY" in source
    assert "SERVICE_SOURCE=UNVERIFIED" in source
    assert "RESULT=NO_CHANGES_MADE" in source
    assert "ShowDialog" in source
    for forbidden in (
        "Start-Service ", "Stop-Service ", "New-Service ",
        "Remove-Service ", "Invoke-Expression ",
        "ExecutionApprovalVerifier", "sofia.db", "Invoke-RestMethod ",
    ):
        assert forbidden not in source


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 GUI preflight")
def test_windows_gui_preflight_runs_without_opening_window_or_touching_services():
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-File", str(SCRIPT), "-Check", "-NoColor",
        ],
        capture_output=True, text=True, timeout=35,
    )
    assert result.returncode == 0, result.stderr
    assert "AEGIS_GUI_SCHEMA=aegis.ui.theme.v1" in result.stdout
    assert "SERVICE_DATA=UNAVAILABLE" in result.stdout
    assert "MANAGEMENT_TRANSPORT=NOT_CONNECTED" in result.stdout
    assert "RESULT=NO_CHANGES_MADE" in result.stdout
    assert "\x1b" not in result.stdout
