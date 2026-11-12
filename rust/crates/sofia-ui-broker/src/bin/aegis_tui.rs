//! Aegis Platform 1.0 standalone Core-free terminal shell.
//! Read-only until the separately authenticated Platform IPC exists.
//! NEVER infer host health from a local launch, cached file or process ID.

use serde_json::Value;
use sofia_ui_broker::control_center::{ControlCenterView, LinkState, SafeState};
use sofia_ui_broker::control_center_session::{DisplayReadSource, DisplaySession, OfflineReader};
use std::env;
use std::io::{self, IsTerminal, Write};
use std::process::ExitCode;

const THEME: &str = include_str!("../../../../../contracts/ui/aegis-theme-v1.json");

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Page {
    Platform,
    Cores,
    Modules,
    Settings,
    Security,
    Updates,
    Diagnostics,
    Fleet,
    LibraryCatalog,
    LibrarySources,
    LibraryDownloads,
    LibraryInstalled,
    LibraryStorage,
    LibraryHub,
    LibraryHistory,
}

impl Page {
    fn heading(self) -> &'static str {
        match self {
            Self::Platform => "Platform",
            Self::Cores => "Core Manager",
            Self::Modules => "Module Manager",
            Self::Settings => "Settings",
            Self::Security => "Security and Approvals",
            Self::Updates => "Updates and Recovery",
            Self::Diagnostics => "Diagnostics",
            Self::Fleet => "Fleet",
            Self::LibraryCatalog => "Library > Catalog",
            Self::LibrarySources => "Library > Sources",
            Self::LibraryDownloads => "Library > Downloads",
            Self::LibraryInstalled => "Library > Installed",
            Self::LibraryStorage => "Library > Storage",
            Self::LibraryHub => "Library > Hub",
            Self::LibraryHistory => "Library > History",
        }
    }
}

fn select_page(choice: &str) -> Option<Page> {
    match choice.trim() {
        "1" => Some(Page::Platform),
        "2" => Some(Page::Cores),
        "3" => Some(Page::Modules),
        "4" => Some(Page::Settings),
        "5" => Some(Page::Security),
        "6" => Some(Page::Updates),
        "7" => Some(Page::Diagnostics),
        "8" => Some(Page::Fleet),
        "9" => Some(Page::LibraryCatalog),
        "10" => Some(Page::LibrarySources),
        "11" => Some(Page::LibraryDownloads),
        "12" => Some(Page::LibraryInstalled),
        "13" => Some(Page::LibraryStorage),
        "14" => Some(Page::LibraryHub),
        "15" => Some(Page::LibraryHistory),
        _ => None,
    }
}

fn rgb(role: &str) -> Option<(u8, u8, u8)> {
    let document: Value = serde_json::from_str(THEME).ok()?;
    if document.get("schema")?.as_str()? != "aegis.ui.theme.v1" {
        return None;
    }
    let color = document.get("tokens")?.get(role)?.as_str()?;
    if color.len() != 7 || !color.starts_with('#') {
        return None;
    }
    let red = u8::from_str_radix(&color[1..3], 16).ok()?;
    let green = u8::from_str_radix(&color[3..5], 16).ok()?;
    let blue = u8::from_str_radix(&color[5..7], 16).ok()?;
    Some((red, green, blue))
}

fn paint(text: &str, role: &str, colors: bool) -> String {
    if !colors {
        return text.to_owned();
    }
    match rgb(role) {
        Some((red, green, blue)) => {
            format!("\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m")
        }
        None => text.to_owned(),
    }
}

fn color_supported() -> bool {
    io::stdout().is_terminal()
        && env::var_os("NO_COLOR").is_none()
        && env::var("TERM").map_or(true, |term| term != "dumb")
        && env::var("COLORTERM")
            .is_ok_and(|term| term.contains("truecolor") || term.contains("24bit"))
}

fn render_menu(colors: bool, view: &ControlCenterView) -> String {
    let mut lines = vec![
        paint(
            "AEGIS PLATFORM | TERMINAL CONTROL CENTER",
            "primary",
            colors,
        ),
        paint(
            &format!(
                "MODE: READ ONLY / MANAGEMENT SERVICE {} / SOURCE {}",
                view.service_label(),
                view.source_label()
            ),
            "warning",
            colors,
        ),
        String::new(),
    ];
    for (digit, title) in [
        ("1", "Platform"),
        ("2", "Core Manager"),
        ("3", "Module Manager"),
        ("4", "Settings"),
        ("5", "Security / Approvals"),
        ("6", "Updates / Recovery"),
        ("7", "Diagnostics"),
        ("8", "Fleet"),
        ("9", "Library > Catalog"),
        ("10", "Library > Sources"),
        ("11", "Library > Downloads"),
        ("12", "Library > Installed"),
        ("13", "Library > Storage"),
        ("14", "Library > Hub"),
        ("15", "Library > History"),
        ("0", "Exit"),
    ] {
        lines.push(format!(
            "{} {title}",
            paint(&format!("[{digit}]"), "accent", colors)
        ));
    }
    lines.join("\n")
}

fn render_page(page: Page, colors: bool, state: &ControlCenterView) -> String {
    // No catalog, inventory, progress, signer or receipt is invented by a
    // locally launched UI; only Team A's authenticated service can supply it.
    let library = match page {
        Page::LibraryCatalog => "CATALOG: NOT_OBSERVED / SELECTED: UNKNOWN / COMPATIBILITY: UNKNOWN",
        Page::LibrarySources => "SOURCES: NOT_OBSERVED / HUB: UNKNOWN / PEERS: UNKNOWN / INTERNET_FALLBACK: DISABLED",
        Page::LibraryDownloads => "DOWNLOADS: NOT_OBSERVED / RECEIVED_BYTES: UNKNOWN / VERIFIED_BYTES: UNKNOWN",
        Page::LibraryInstalled => "CACHED: UNKNOWN / VERIFIED: UNKNOWN / STAGED: UNKNOWN / INSTALLED: UNKNOWN / ACTIVE: UNKNOWN",
        Page::LibraryStorage => "STORAGE: NOT_OBSERVED / QUOTA: UNKNOWN / PINS: UNKNOWN / GC: DISABLED",
        Page::LibraryHub => "HUB_ROLE: UNKNOWN / ENROLLED_CLIENTS: NOT_OBSERVED / PUBLIC_EXPOSURE: NOT_CONFIGURED",
        Page::LibraryHistory => "HISTORY: NOT_OBSERVED / SIGNER: UNKNOWN / RECEIPTS: NOT_OBSERVED",
        _ => "",
    };
    let permission = format!(
        "PERMISSION: {} / SAFE-STOP: {}",
        state.permission_label(),
        state.safe_label()
    );
    format!(
        "{}\nSERVICE: {} / SOURCE: {}\nSETTINGS: {}\nINSTALLATION: {}\n{}\n{}\n{}\n{}",
        paint(page.heading(), "primary", colors),
        state.service_label(),
        state.source_label(),
        state.settings_label(),
        state.installation_label(),
        "VALUES: UNAVAILABLE (not disconnected, removed, healthy or zero)",
        permission,
        "No writes, approvals, downloads, installation, state files or service changes.",
        library
    )
}

// This is a presentation of an already authenticated state, not a
// verification of native OS service origin, owner enrollment, or SAFE.
// The sole wired producer remains OfflineReader until Team A/B sign off.
fn current_status(view: &ControlCenterView) -> bool {
    view.link == LinkState::Observed
        && view.platform_generation.is_some()
        && view.safe == SafeState::Clear
}

fn status_name(view: &ControlCenterView) -> &'static str {
    if view.link == LinkState::Observed && !current_status(view) {
        if view.safe == SafeState::StopActive {
            "STOP_ACTIVE"
        } else {
            "UNVERIFIED"
        }
    } else {
        view.service_label()
    }
}

fn status_source(view: &ControlCenterView) -> &'static str {
    if current_status(view) {
        "SERVICE_OBSERVED"
    } else if view.link == LinkState::Observed {
        "UNVERIFIED"
    } else {
        view.source_label()
    }
}

fn status_line(view: &ControlCenterView) -> String {
    format!(
        "status={} source={} safe={} permission={} installation={}",
        status_name(view),
        status_source(view),
        view.safe_label(),
        view.permission_label(),
        view.installation_label()
    )
}

fn status_json(view: &ControlCenterView) -> Value {
    let current = current_status(view);
    let operator_stop = if current { Some(false) } else { None };
    serde_json::json!({
        "schema": "aegis.ui.platform.status-display.v1",
        "status": status_name(view),
        "source": status_source(view),
        "platform_generation": if current { view.platform_generation } else { None },
        "safe": view.safe_label(),
        "operator_stop": operator_stop,
        // Team A v1 strict OK requires core_started=false.
        // Never show that value for an unverified observation or denial.
        "core_started": if current { Some(false) } else { None },
        "permission": view.permission_label(),
        "installation": view.installation_label(),
        "actions_enabled": false
    })
}

fn status_exit(view: &ControlCenterView) -> ExitCode {
    if current_status(view) {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(3)
    }
}

// Native Linux status implements the SAME reader. Only an independently
// B1-verified installed profile may activate it, never untrusted CLI flags.
fn run_with_source(source: &mut impl DisplayReadSource) -> io::Result<ExitCode> {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut session = DisplaySession::default();
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        const HELP: &str = concat!(
            "aegis-tui [--plain | --help | --status | --status-json",
            " | --library-status | --library-json]"
        );
        println!("{HELP}");
        println!("This read-only shell does not perform management operations.");
        return Ok(ExitCode::SUCCESS);
    }
    if args.len() > 1
        || args.first().is_some_and(|arg| {
            arg != "--plain"
                && arg != "--status"
                && arg != "--status-json"
                && arg != "--library-status"
                && arg != "--library-json"
        })
    {
        eprintln!("Unknown option. Use --help.");
        return Ok(ExitCode::from(2));
    }
    let _ = session.refresh(source, std::time::Instant::now());
    if args.first().is_some_and(|arg| arg == "--status") {
        println!("{}", status_line(session.view()));
        return Ok(status_exit(session.view()));
    }
    if args.first().is_some_and(|arg| arg == "--status-json") {
        println!("{}", status_json(session.view()));
        return Ok(status_exit(session.view()));
    }
    if args.first().is_some_and(|arg| arg == "--library-json") {
        // UI-only OFFLINE status, not Team A's management/library wire schema.
        // Null means NOT OBSERVED. Closing this tool never affects Platform.
        let offline = serde_json::json!({
            "schema": "aegis.ui.library.offline-status.v1",
            "library": "UNAVAILABLE",
            "source": "UNVERIFIED",
            "catalog": null,
            "downloaded": null,
            "verified": null,
            "staged": null,
            "installed": null,
            "active": null,
            "received_bytes": null,
            "verified_bytes": null,
            "internet_fallback": "DISABLED",
            "actions_enabled": false
        });
        println!("{offline}");
        return Ok(ExitCode::from(3));
    }
    if args.first().is_some_and(|arg| arg == "--library-status") {
        let status = concat!(
            "library=UNAVAILABLE source=UNVERIFIED catalog=UNKNOWN ",
            "cache=UNKNOWN installed=UNKNOWN active=UNKNOWN ",
            "received_bytes=UNKNOWN verified_bytes=UNKNOWN ",
            "internet_fallback=DISABLED actions=DISABLED"
        );
        println!("{status}");
        return Ok(ExitCode::from(3));
    }
    let colors = !args.iter().any(|arg| arg == "--plain") && color_supported();
    if !io::stdin().is_terminal() {
        print!("{}", render_menu(false, session.view()));
        println!("\nInteractive input requires a terminal; no operation performed.");
        return Ok(ExitCode::SUCCESS);
    }
    loop {
        let _ = session.refresh(source, std::time::Instant::now());
        session.expire_at(std::time::Instant::now());
        println!("{}", render_menu(colors, session.view()));
        print!("Select [0-15]: ");
        io::stdout().flush()?;
        let mut selection = String::new();
        if io::stdin().read_line(&mut selection)? == 0 {
            return Ok(ExitCode::SUCCESS);
        }
        if selection.trim() == "0" {
            return Ok(ExitCode::SUCCESS);
        }
        let _ = session.refresh(source, std::time::Instant::now());
        session.expire_at(std::time::Instant::now());
        if let Some(page) = select_page(&selection) {
            println!("{}\n", render_page(page, colors, session.view()));
        } else {
            println!("Not a valid menu number; no operation performed.\n");
        }
    }
}

fn run() -> io::Result<ExitCode> {
    // No B1-signed external service pins or approved external operator
    // entitlement are installed in this build. Fail closed by default.
    run_with_source(&mut OfflineReader)
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(error) => {
            eprintln!("TUI I/O failed: {error}");
            ExitCode::from(1)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        paint, render_menu, render_page, rgb, select_page, status_exit, status_json, status_line,
        Page,
    };
    use sofia_ui_broker::control_center::{
        ControlCenterView, LinkState, PermissionState, SafeState,
    };

    #[test]
    fn theme_imports_exact_shared_manifest() {
        assert_eq!(rgb("primary"), Some((148, 0, 211)));
        assert_eq!(rgb("accent"), Some((0, 194, 255)));
        assert_eq!(rgb("tertiary"), Some((57, 255, 20)));
    }

    #[test]
    fn plain_mode_has_no_ansi_or_unsupported_authority_claims() {
        let menu = render_menu(false, &ControlCenterView::offline());
        assert!(!menu.contains('\x1b'));
        assert!(menu.contains("UNAVAILABLE"));
        assert!(menu.contains("SOURCE UNVERIFIED"));
        assert!(menu.contains("Settings"));
        assert!(!menu.contains("VERIFIED HEALTHY"));
        let page = render_page(Page::Settings, false, &ControlCenterView::offline());
        assert!(page.contains("UNVERIFIED"));
        assert!(page.contains("No writes"));
        assert!(!page.contains('\x1b'));
    }

    #[test]
    fn all_denial_modes_are_visible_and_no_ansi_in_plain_mode() {
        for (link, label) in [
            (LinkState::Revoked, "REVOKED"),
            (LinkState::Stopped, "STOP_ACTIVE"),
            (LinkState::AccessDenied, "ACCESS_DENIED"),
            (LinkState::Stale, "STALE"),
            (LinkState::Restarting, "RESTARTING"),
            (LinkState::UnknownGeneration, "UNKNOWN_GENERATION"),
        ] {
            let mut state = ControlCenterView::offline();
            state.link = link;
            let page = render_page(Page::Modules, false, &state);
            assert!(page.contains(label));
            assert!(page.contains("NOT_CURRENTLY_VERIFIED"));
            assert!(!page.contains('\x1b'));
        }
    }

    #[test]
    fn observed_stop_and_denied_are_not_mislabeled_unknown() {
        let mut state = ControlCenterView::offline();
        state.link = LinkState::Observed;
        state.platform_generation = Some(7);
        state.safe = SafeState::StopActive;
        state.permission = PermissionState::Denied;
        let page = render_page(Page::Security, false, &state);
        assert!(page.contains("SAFE-STOP: STOP_ACTIVE"));
        assert!(page.contains("PERMISSION: DENIED"));
        assert!(!page.contains('\x1b'));
    }

    #[test]
    fn offline_library_pages_never_invent_package_inventory_or_progress() {
        for (page, expected) in [
            (Page::LibraryCatalog, "CATALOG: NOT_OBSERVED"),
            (Page::LibrarySources, "INTERNET_FALLBACK: DISABLED"),
            (Page::LibraryDownloads, "RECEIVED_BYTES: UNKNOWN"),
            (Page::LibraryInstalled, "INSTALLED: UNKNOWN"),
            (Page::LibraryStorage, "GC: DISABLED"),
            (Page::LibraryHub, "HUB_ROLE: UNKNOWN"),
            (Page::LibraryHistory, "RECEIPTS: NOT_OBSERVED"),
        ] {
            let text = render_page(page, false, &ControlCenterView::offline());
            assert!(text.contains(expected));
            assert!(text.contains("SOURCE: UNVERIFIED"));
            assert!(!text.contains('\x1b'));
            assert!(!text.contains("100%"));
        }
    }

    #[test]
    fn status_projection_is_offline_and_does_not_claim_installed_or_healthy() {
        let view = ControlCenterView::offline();
        let text = status_line(&view);
        assert!(text.starts_with("status=UNAVAILABLE source=UNVERIFIED"));
        let data = status_json(&view);
        assert_eq!(data["schema"], "aegis.ui.platform.status-display.v1");
        assert_eq!(data["platform_generation"], serde_json::Value::Null);
        assert_eq!(data["operator_stop"], serde_json::Value::Null);
        assert_eq!(data["core_started"], serde_json::Value::Null);
        assert_eq!(data["actions_enabled"], false);
        assert_eq!(data["installation"], "NOT_CURRENTLY_VERIFIED");
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
    }

    #[test]
    fn menu_reflects_observation_or_denial_instead_of_hardcoded_offline() {
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Revoked;
        let denied = render_menu(false, &view);
        assert!(denied.contains("SERVICE REVOKED"));
        assert!(denied.contains("SOURCE REVOKED"));
        view.link = LinkState::Observed;
        view.platform_generation = Some(9);
        let live = render_menu(false, &view);
        assert!(live.contains("SERVICE OBSERVED"));
        assert!(live.contains("SOURCE SERVICE_OBSERVED"));
        assert!(!live.contains("SERVICE UNAVAILABLE"));
    }

    #[test]
    fn only_service_observed_generation_can_make_status_cli_success() {
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        view.platform_generation = Some(8);
        view.safe = SafeState::StopActive;
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        let denied = status_json(&view);
        assert_eq!(denied["status"], "STOP_ACTIVE");
        assert_eq!(denied["source"], "UNVERIFIED");
        assert_eq!(denied["platform_generation"], serde_json::Value::Null);
        view.safe = SafeState::Clear;
        assert_eq!(status_exit(&view), std::process::ExitCode::SUCCESS);
        let data = status_json(&view);
        assert_eq!(data["status"], "OBSERVED");
        assert_eq!(data["source"], "SERVICE_OBSERVED");
        assert_eq!(data["platform_generation"], 8);
        assert_eq!(data["operator_stop"], false);
        assert_eq!(data["core_started"], false);
        assert_eq!(data["actions_enabled"], false);
    }

    #[test]
    fn denied_stop_revoked_and_stale_status_never_expose_generation() {
        for (link, expected) in [
            (LinkState::Stopped, "STOP_ACTIVE"),
            (LinkState::Revoked, "REVOKED"),
            (LinkState::AccessDenied, "ACCESS_DENIED"),
            (LinkState::Stale, "STALE"),
            (LinkState::UnknownGeneration, "UNKNOWN_GENERATION"),
        ] {
            let mut view = ControlCenterView::offline();
            view.platform_generation = Some(9); // cached, NOT CURRENT
            view.link = link;
            let data = status_json(&view);
            assert_eq!(data["status"], expected);
            assert_eq!(data["platform_generation"], serde_json::Value::Null);
            assert_eq!(data["operator_stop"], serde_json::Value::Null);
            assert_eq!(data["actions_enabled"], false);
            assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        }
    }

    #[test]
    fn invalid_menu_input_cannot_start_service_or_grant_approval() {
        assert_eq!(select_page("4"), Some(Page::Settings));
        assert_eq!(select_page("1"), Some(Page::Platform));
        assert_eq!(select_page("4;rm -rf /"), None);
        assert_eq!(select_page("8"), Some(Page::Fleet));
        assert_eq!(select_page("9"), Some(Page::LibraryCatalog));
        assert_eq!(select_page("15"), Some(Page::LibraryHistory));
        assert_eq!(select_page("16"), None);
        assert!(paint("X", "accent", false) == "X");
    }
}
