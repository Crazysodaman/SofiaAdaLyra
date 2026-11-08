//! Aegis Platform 1.0 standalone Core-free terminal shell.
//! Read-only until the separately authenticated Platform IPC exists.
//! NEVER infer host health from a local launch, cached file or process ID.

use serde_json::Value;
use sofia_ui_broker::control_center::ControlCenterView;
use sofia_ui_broker::control_center_session::{DisplaySession, OfflineReader};
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

fn render_menu(colors: bool) -> String {
    let mut lines = vec![
        paint(
            "AEGIS PLATFORM | TERMINAL CONTROL CENTER",
            "primary",
            colors,
        ),
        paint(
            "MODE: READ ONLY / MANAGEMENT SERVICE UNAVAILABLE",
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
    format!(
        "{}\nSERVICE: {} / SOURCE: {}\nSETTINGS: {}\nINSTALLATION: {}\n{}\n{}\n{}",
        paint(page.heading(), "primary", colors),
        state.service_label(),
        state.source_label(),
        state.settings_label(),
        state.installation_label(),
        "VALUES: UNAVAILABLE (not disconnected, removed, healthy or zero)",
        format!(
            "PERMISSION: {} / SAFE-STOP: {}",
            state.permission_label(),
            state.safe_label()
        ),
        "No writes, approvals, downloads, installation, state files or service changes."
    )
}

fn run() -> io::Result<ExitCode> {
    let args: Vec<String> = env::args().skip(1).collect();
    // Only the offline reader is wired until Team A's authenticated
    // response contract and native OS transport are approved.
    let mut session = DisplaySession::default();
    let _ = session.refresh(&mut OfflineReader, std::time::Instant::now());
    if args.iter().any(|arg| arg == "--help" || arg == "-h") {
        println!("aegis-tui [--plain | --help | --status]");
        println!("This read-only shell does not perform management operations.");
        return Ok(ExitCode::SUCCESS);
    }
    if args.len() > 1
        || args
            .first()
            .is_some_and(|arg| arg != "--plain" && arg != "--status")
    {
        eprintln!("Unknown option. Use --help.");
        return Ok(ExitCode::from(2));
    }
    if args.first().is_some_and(|arg| arg == "--status") {
        println!("status=UNAVAILABLE source=UNVERIFIED");
        return Ok(ExitCode::from(3));
    }
    let colors = !args.iter().any(|arg| arg == "--plain") && color_supported();
    if !io::stdin().is_terminal() {
        print!("{}", render_menu(false));
        println!("\nInteractive input requires a terminal; no operation performed.");
        return Ok(ExitCode::SUCCESS);
    }
    loop {
        println!("{}", render_menu(colors));
        print!("Select [0-8]: ");
        io::stdout().flush()?;
        let mut selection = String::new();
        if io::stdin().read_line(&mut selection)? == 0 {
            return Ok(ExitCode::SUCCESS);
        }
        if selection.trim() == "0" {
            return Ok(ExitCode::SUCCESS);
        }
        if let Some(page) = select_page(&selection) {
            println!("{}\n", render_page(page, colors, session.view()));
        } else {
            println!("Not a valid menu number; no operation performed.\n");
        }
    }
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
    use super::{paint, render_menu, render_page, rgb, select_page, Page};
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
        let menu = render_menu(false);
        assert!(!menu.contains('\x1b'));
        assert!(menu.contains("UNAVAILABLE"));
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
    fn invalid_menu_input_cannot_start_service_or_grant_approval() {
        assert_eq!(select_page("4"), Some(Page::Settings));
        assert_eq!(select_page("1"), Some(Page::Platform));
        assert_eq!(select_page("4;rm -rf /"), None);
        assert_eq!(select_page("8"), Some(Page::Fleet));
        assert_eq!(select_page("9"), None);
        assert!(paint("X", "accent", false) == "X");
    }
}
