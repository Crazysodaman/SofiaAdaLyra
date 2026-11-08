"""Team C unified GUI/TUI static authority and theme acceptance preflight."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "packaging/gui/Start-AegisControlCenter.ps1"
RUST = ROOT / "rust/crates/sofia-ui-broker/src/control_center.rs"
SESSION = ROOT / "rust/crates/sofia-ui-broker/src/control_center_session.rs"
LIBRARY = ROOT / "rust/crates/sofia-ui-broker/src/library_display.rs"
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
    assert "LIBRARY_PAGE_VERIFIED=" in gui


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


def test_c005_library_projection_does_not_conflate_transfer_and_receipts():
    source = LIBRARY.read_text(encoding="utf-8")
    for stage in ("downloaded", "verified", "staged", "installed",
                  "active", "rollback_pinned"):
        assert "pub " + stage + ": Option<DisplayReceipt>" in source
    assert "received_bytes" in source
    assert "verified_bytes" in source
    assert "transfer.verified_bytes > transfer.received_bytes" in source
    assert "transfer.received_bytes > transfer.total_bytes" in source
    assert "InvalidStageReceipt" in source
    assert "InvalidProvenance" in source
    assert "GenerationRegressed" in source
    assert "RevisionRegressed" in source
    assert "SequenceReplayed" in source
    assert "UnexpectedSafeState" in source


def test_c005_library_projection_no_authentication_or_installer_backdoor():
    source = LIBRARY.read_text(encoding="utf-8")
    assert "OfflineLibraryReader" in source
    assert "pub trait LibraryObservationSource" in source
    assert "self.current()" in source
    assert "self.last_snapshot.as_ref()" in source
    for forbidden in ("UnixStream::connect", "TcpStream", "NamedPipe",
                      "Invoke-RestMethod", "Start-Service", "sofia.db",
                      "OwnerSecretStore", "curl", "reqwest"):
        assert forbidden not in source


def test_c006_receipt_evidence_is_not_issuer_or_installer_authority():
    source = LIBRARY.read_text(encoding="utf-8")
    for field in ("issuer_identity", "target_platform_id", "content_sha256",
                  "evidence_generation", "evidence_revision",
                  "evidence_observed_unix_ms"):
        assert "pub " + field + ":" in source
    for expected in (
        "receipt.evidence_generation == observation.generation",
        "receipt.evidence_revision == observation.state_revision",
        "receipt.evidence_observed_unix_ms == observation.observed_unix_ms",
        "valid_id(&receipt.issuer_identity)",
        "LibraryDisplayError::TimeRegressed",
        "seen.insert(receipt.reference.as_str())",
        "RECEIPT_REFERENCE_NOT_AUTHORITY",
        "forged_receipt_issuer_target_digest_generation_revision_and_time_are_denied",
    ):
        assert expected in source
    assert "OBSERVED_WITH_VERIFIED_SERVICE_RECEIPT" not in source
    assert "OfflineLibraryReader" in source


def test_c007_status_cli_is_sourced_from_display_and_denials_fail_closed():
    source = TUI.read_text(encoding="utf-8")
    assert "--status-json" in source
    assert "status_line(session.view())" in source
    assert "status_json(session.view())" in source
    assert "status_exit(session.view())" in source
    assert '"platform_generation": if current { view.platform_generation } else { None }' in source
    assert '"core_started": if current { Some(false) } else { None }' in source
    assert '"actions_enabled": false' in source
    assert "fn denied_stop_revoked_and_stale_status_never_expose_generation()" in source
    assert "session.refresh(&mut OfflineReader" in source


def test_c007_menu_never_freezes_a_future_live_status_as_offline():
    source = TUI.read_text(encoding="utf-8")
    assert "fn render_menu(colors: bool, view: &ControlCenterView)" in source
    assert "view.service_label()" in source
    assert "view.source_label()" in source
    assert "session.expire_at(std::time::Instant::now())" in source
    assert "menu_reflects_observation_or_denial_instead_of_hardcoded_offline" in source


def test_c007_stop_cannot_be_a_successful_platform_status_reply():
    session = SESSION.read_text(encoding="utf-8")
    tui = TUI.read_text(encoding="utf-8")
    assert "DisplayError::UnexpectedSafeState" in session
    assert "incoming.safe != SafeState::Clear" in session
    assert "ReadFailure::Stopped" in session
    assert "current_status(view)" in tui
    assert 'denied["status"], "STOP_ACTIVE"' in tui
    assert '"operator_stop": operator_stop' in tui
    assert '"actions_enabled": false' in tui


def test_c008_native_reader_is_not_activated_from_untrusted_cli_configuration():
    source = TUI.read_text(encoding="utf-8")
    client = (ROOT / "rust/crates/sofia-ui-broker/src/native_management.rs").read_text(encoding="utf-8")
    assert "fn run_with_source(source: &mut impl DisplayReadSource)" in source
    assert "run_with_source(&mut OfflineReader)" in source
    assert "self.local_sequence" in client
    assert "UntrustedManagementResponse::parse" in client
    assert "PeerCredentials" in client
    assert "verify_os_peer" in client
    assert "verify_endpoint(&self.pins)" in client
    assert "getrandom::getrandom" in client
    assert "from_verified_denial" in client
    assert "NativeLinuxManagementReader" in client
    for forbidden in ("--operator-uid", "--owner-grant", "--ignore-peer",
                      "--auto-enroll", "--start-core", "curl"):
        assert forbidden not in source
        assert forbidden not in client
