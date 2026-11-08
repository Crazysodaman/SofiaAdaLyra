"""Team C unified GUI/TUI static authority and theme acceptance preflight."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "packaging/gui/Start-AegisControlCenter.ps1"
RUST = ROOT / "rust/crates/sofia-ui-broker/src/control_center.rs"
TUI = ROOT / "rust/crates/sofia-ui-broker/src/bin/aegis_tui.rs"


def test_one_canonical_windows_gui_preview_and_no_second_shell():
    assert GUI.is_file()
    assert not (ROOT / "packaging/ui/Start-AegisControlCenter.ps1").exists()
    gui = GUI.read_text(encoding="utf-8")
    assert "aegis-theme-v1.json" in gui
    assert "SystemInformation]::HighContrast" in gui
    for required in ("Install Module", "Uninstall Module", "Reinstall Module",
                     "Restart Core", "Save Settings", "Request Approval",
                     "Update Platform", "Rollback"):
        assert required in gui
    assert "Enabled = $false" in gui
    assert "AUTHENTICATION=NOT_CONNECTED" in gui


def test_tui_and_rust_presentation_require_real_service_recheck():
    tui = TUI.read_text(encoding="utf-8")
    state = RUST.read_text(encoding="utf-8")
    assert "ControlCenterView::offline()" in tui
    assert "SERVICE_REVALIDATION" not in tui
    assert "RecheckWithService" in state
    assert "SAFE_STOP_ACTIVE" in state
    assert "PERMISSION_DENIED" in state
    assert "OBSERVATION_STALE" in state
    assert "SERVICE_RESTARTING" in state
    assert "REINSTALL_REQUIRES_VERIFIED_REMOVAL" in state
    for forbidden in ("Start-Service ", "Stop-Service ", "Invoke-RestMethod ",
                      "sofia.db", "Get-Credential "):
        assert forbidden not in GUI.read_text(encoding="utf-8")
