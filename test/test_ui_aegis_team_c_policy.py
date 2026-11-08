"""Team C unified GUI/TUI static authority and theme acceptance preflight."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "packaging/gui/Start-AegisControlCenter.ps1"
RUST = ROOT / "rust/crates/sofia-ui-broker/src/control_center.rs"
SESSION = ROOT / "rust/crates/sofia-ui-broker/src/control_center_session.rs"
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


def test_management_display_session_does_not_connect_or_authorize():
    source = SESSION.read_text(encoding="utf-8")
    for field in ("OfflineReader", "DisplayReadSource", "MAX_DISPLAY_AGE",
                  "SettingsRegressed", "SequenceReplayed", "GenerationRegressed"):
        assert field in source
    for forbidden in ("UnixStream::connect", "TcpStream", "NamedPipe",
                      "Invoke-RestMethod", "sofia.db"):
        assert forbidden not in source


def test_gui_blocks_all_inactive_management_states_and_supports_escape():
    source = GUI.read_text(encoding="utf-8")
    for code in ("STOP_ACTIVE", "REVOKED", "DENIED", "STALE",
                 "UNKNOWN_GENERATION", "RESTARTING", "OFFLINE"):
        assert code in source
    assert "AccessibleDescription" in source
    assert "Add_KeyDown" in source
    assert "Enabled = $true" not in source


def test_d028_06_library_navigation_is_read_only_without_a_service_source():
    gui = GUI.read_text(encoding="utf-8")
    tui = TUI.read_text(encoding="utf-8")
    for page in ("Catalog", "Sources", "Downloads", "Installed",
                 "Storage", "Hub", "History"):
        assert "Library > " + page in gui
        assert "Library > " + page in tui
    for expected in ("LIBRARY=UNAVAILABLE", "LIBRARY_ACTIONS=DISABLED",
                     "INTERNET_FALLBACK=DISABLED"):
        assert expected in gui
    assert "OfflineReader" in tui
    assert "CATALOG: NOT_OBSERVED" in tui
    assert "RECEIVED_BYTES: UNKNOWN" in tui
    assert "VERIFIED_BYTES: UNKNOWN" in tui
    assert "CACHED: UNKNOWN" in tui
    assert "INSTALLED: UNKNOWN" in tui
    assert "ACTIVE: UNKNOWN" in tui
    assert "download" in gui.lower()
    assert "Enabled = $true" not in gui


def test_c003_stop_denial_mapping_matches_canonical_a_management_codes():
    session = SESSION.read_text(encoding="utf-8")
    state = RUST.read_text(encoding="utf-8")
    for code in ("NOT_PERMITTED", "REVOKED", "STOPPED",
                 "STALE_GENERATION", "EXPIRED", "UNAVAILABLE"):
        assert '"' + code + '"' in session
    assert 'LinkState::Stopped => "SAFE_STOP_ACTIVE"' in state
    assert 'ReadFailure::Stopped' in session


def test_c003_headless_json_is_offline_display_not_ipc_contract():
    tui = TUI.read_text(encoding="utf-8")
    assert "--library-json" in tui
    assert "aegis.ui.library.offline-status.v1" in tui
    assert '"installed": null' in tui
    assert '"active": null' in tui
    assert '"actions_enabled": false' in tui
    assert "OfflineReader" in tui
