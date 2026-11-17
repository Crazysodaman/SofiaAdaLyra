//! Aegis Platform 1.0 standalone Core-free terminal shell.
//! Read-only until the separately authenticated Platform IPC exists.
//! NEVER infer host health from a local launch, cached file or process ID.

use serde_json::Value;
use sofia_ui_broker::action_preview::{
    empty_payload, ActionPreview, CallerApproval, MutationSubmission,
};
use sofia_ui_broker::connection_state::{ConnectionState, ConnectionStateModel};
use sofia_ui_broker::control_center::{
    ActionHint, ControlCenterView, LinkState, ProposedAction, SafeState,
};
use sofia_ui_broker::control_center_session::{
    DisplayReadSource, DisplaySession, OfflineReader, ReadFailure,
};
use sofia_ui_broker::management_mutation::{MutationClient, MutationTransport};
use sofia_ui_broker::manager_snapshot::{
    read_manager_snapshot, AuthenticatedManagerSnapshotSource,
};
use sofia_ui_broker::manager_views::{self, ManagerPage, ManagerSnapshot, StartupState};
use sofia_ui_broker::native_management;
use std::env;
use std::fmt::Write as _;
use std::io::{self, IsTerminal, Write};
use std::process::ExitCode;

const THEME: &str = include_str!("../../../../../contracts/ui/aegis-theme-v1.json");
const ENV_ENDPOINT: &str = "AEGIS_MANAGEMENT_ENDPOINT";
const ENV_PLATFORM_ID: &str = "AEGIS_EXPECTED_PLATFORM_ID";
const ENV_GENERATION: &str = "AEGIS_EXPECTED_GENERATION";

#[allow(clippy::struct_excessive_bools)]
#[derive(Debug, Default, PartialEq, Eq)]
struct CliOptions {
    plain: bool,
    status: bool,
    status_json: bool,
    library_status: bool,
    library_json: bool,
    help: bool,
    endpoint: Option<String>,
    platform_id: Option<String>,
    generation: Option<u64>,
}

#[derive(Debug, PartialEq, Eq)]
enum CliError {
    Unknown(String),
    MissingValue(String),
    InvalidGeneration(String),
}

impl std::fmt::Display for CliError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Unknown(option) => write!(formatter, "Unknown option: {option}. Use --help."),
            Self::MissingValue(option) => write!(formatter, "Missing value for {option}."),
            Self::InvalidGeneration(value) => {
                write!(formatter, "Invalid expected generation: {value}.")
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct LiveTarget {
    endpoint: String,
    platform_id: String,
    generation: u64,
}

impl CliOptions {
    fn parse(args: &[String]) -> Result<Self, CliError> {
        let mut options = Self::default();
        let mut index = 0;
        while index < args.len() {
            let argument = args[index].as_str();
            if let Some(value) = argument.strip_prefix("--management-endpoint=") {
                options.endpoint = Some(value.to_owned());
            } else if let Some(value) = argument.strip_prefix("--expected-platform-id=") {
                options.platform_id = Some(value.to_owned());
            } else if let Some(value) = argument.strip_prefix("--expected-generation=") {
                options.generation = Some(parse_generation(value)?);
            } else {
                match argument {
                    "--plain" => options.plain = true,
                    "--status" => options.status = true,
                    "--status-json" => options.status_json = true,
                    "--library-status" => options.library_status = true,
                    "--library-json" => options.library_json = true,
                    "--help" | "-h" => options.help = true,
                    "--management-endpoint" => {
                        options.endpoint =
                            Some(option_value(args, &mut index, "--management-endpoint")?);
                    }
                    "--expected-platform-id" => {
                        options.platform_id =
                            Some(option_value(args, &mut index, "--expected-platform-id")?);
                    }
                    "--expected-generation" => {
                        options.generation = Some(parse_generation(&option_value(
                            args,
                            &mut index,
                            "--expected-generation",
                        )?)?);
                    }
                    _ => return Err(CliError::Unknown(argument.to_owned())),
                }
            }
            index += 1;
        }
        Ok(options)
    }

    fn from_process(args: &[String]) -> Result<Self, CliError> {
        let mut options = Self::parse(args)?;
        if options.endpoint.is_none() {
            options.endpoint = environment(ENV_ENDPOINT);
        }
        if options.platform_id.is_none() {
            options.platform_id = environment(ENV_PLATFORM_ID);
        }
        if options.generation.is_none() {
            if let Some(value) = environment(ENV_GENERATION) {
                options.generation = Some(parse_generation(&value)?);
            }
        }
        Ok(options)
    }

    fn live_target(&self) -> Result<Option<LiveTarget>, ()> {
        match (&self.endpoint, &self.platform_id, self.generation) {
            (None, None, None) => Ok(None),
            (Some(endpoint), Some(platform_id), Some(generation))
                if !endpoint.trim().is_empty()
                    && valid_platform_id(platform_id)
                    && generation > 0 =>
            {
                Ok(Some(LiveTarget {
                    endpoint: endpoint.clone(),
                    platform_id: platform_id.clone(),
                    generation,
                }))
            }
            _ => Err(()),
        }
    }
}

fn option_value(args: &[String], index: &mut usize, name: &str) -> Result<String, CliError> {
    *index += 1;
    args.get(*index)
        .cloned()
        .ok_or_else(|| CliError::MissingValue(name.to_owned()))
}

fn environment(name: &str) -> Option<String> {
    env::var(name).ok().filter(|value| !value.trim().is_empty())
}

fn parse_generation(value: &str) -> Result<u64, CliError> {
    value
        .parse::<u64>()
        .map_err(|_| CliError::InvalidGeneration(value.to_owned()))
}

fn valid_platform_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 160
        && bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(*byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

struct FailureReader(ReadFailure);

impl DisplayReadSource for FailureReader {
    fn next(
        &mut self,
    ) -> Result<sofia_ui_broker::control_center_session::DisplaySnapshot, ReadFailure> {
        Err(self.0)
    }
}

/// With an explicitly configured endpoint, an unreachable or mismatched
/// native channel is UNVERIFIED/UNKNOWN rather than an implicit offline
/// fallback. After one genuine observation, later loss remains OFFLINE.
struct ConfiguredStatusReader<R> {
    inner: R,
    observed: bool,
}

impl<R: DisplayReadSource> DisplayReadSource for ConfiguredStatusReader<R> {
    fn next(
        &mut self,
    ) -> Result<sofia_ui_broker::control_center_session::DisplaySnapshot, ReadFailure> {
        match self.inner.next() {
            Ok(snapshot) => {
                self.observed = true;
                Ok(snapshot)
            }
            Err(ReadFailure::Offline) if !self.observed => Err(ReadFailure::Unverified),
            Err(failure) => Err(failure),
        }
    }
}

struct ConfiguredSnapshotReader<R> {
    inner: R,
    observed: bool,
}

impl<R: AuthenticatedManagerSnapshotSource> AuthenticatedManagerSnapshotSource
    for ConfiguredSnapshotReader<R>
{
    fn observe_operation(
        &mut self,
        operation: &str,
    ) -> Result<sofia_ui_broker::manager_snapshot::AuthenticatedObservation, ReadFailure> {
        match self.inner.observe_operation(operation) {
            Ok(observation) => {
                self.observed = true;
                Ok(observation)
            }
            Err(ReadFailure::Offline) if !self.observed => Err(ReadFailure::Unverified),
            Err(failure) => Err(failure),
        }
    }
}

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

const PAGES: [Page; 15] = [
    Page::Platform,
    Page::Cores,
    Page::Modules,
    Page::Settings,
    Page::Security,
    Page::Updates,
    Page::Diagnostics,
    Page::Fleet,
    Page::LibraryCatalog,
    Page::LibrarySources,
    Page::LibraryDownloads,
    Page::LibraryInstalled,
    Page::LibraryStorage,
    Page::LibraryHub,
    Page::LibraryHistory,
];

#[derive(Debug, PartialEq, Eq)]
enum Navigation {
    Show(Page),
    Refresh,
    Preview,
    Approval(String),
    Submit,
    Exit,
    Invalid,
}

fn navigate(command: &str, selected: &mut usize) -> Navigation {
    match command.trim() {
        "0" | "q" | "quit" => Navigation::Exit,
        "r" | "refresh" => Navigation::Refresh,
        "p" | "preview" => Navigation::Preview,
        "s" | "submit" => Navigation::Submit,
        "j" | "next" => {
            *selected = (*selected + 1) % PAGES.len();
            Navigation::Show(PAGES[*selected])
        }
        "k" | "previous" => {
            *selected = (*selected + PAGES.len() - 1) % PAGES.len();
            Navigation::Show(PAGES[*selected])
        }
        "" => Navigation::Show(PAGES[*selected]),
        choice => {
            if let Some(approval) = choice
                .strip_prefix("a ")
                .or_else(|| choice.strip_prefix("approval "))
            {
                return Navigation::Approval(approval.trim().to_owned());
            }
            match select_page(choice) {
                Some(page) => {
                    // select_page and PAGES describe the same bounded menu.
                    *selected = PAGES.iter().position(|entry| *entry == page).unwrap_or(0);
                    Navigation::Show(page)
                }
                None => Navigation::Invalid,
            }
        }
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ColorMode {
    Plain,
    Ansi16,
    TrueColor,
}

fn choose_color_mode(
    terminal: bool,
    plain: bool,
    no_color: bool,
    term: Option<&str>,
    colorterm: Option<&str>,
) -> ColorMode {
    if !terminal
        || plain
        || no_color
        || term.is_none_or(|value| value.is_empty() || value == "dumb")
    {
        return ColorMode::Plain;
    }
    if colorterm.is_some_and(|value| {
        value.eq_ignore_ascii_case("truecolor") || value.eq_ignore_ascii_case("24bit")
    }) {
        ColorMode::TrueColor
    } else {
        ColorMode::Ansi16
    }
}

fn paint(text: &str, role: &str, colors: ColorMode) -> String {
    match colors {
        ColorMode::Plain => text.to_owned(),
        ColorMode::Ansi16 => {
            let code = match role {
                "primary" => 35,
                "accent" => 36,
                "tertiary" => 32,
                "warning" => 33,
                _ => return text.to_owned(),
            };
            format!("\x1b[{code}m{text}\x1b[0m")
        }
        ColorMode::TrueColor => match rgb(role) {
            Some((red, green, blue)) => format!("\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m"),
            None => text.to_owned(),
        },
    }
}

fn runtime_color_mode(args: &[String]) -> ColorMode {
    choose_color_mode(
        io::stdout().is_terminal(),
        args.iter().any(|arg| arg == "--plain"),
        env::var_os("NO_COLOR").is_some(),
        env::var("TERM").ok().as_deref(),
        env::var("COLORTERM").ok().as_deref(),
    )
}

fn render_menu(colors: ColorMode, view: &ControlCenterView) -> String {
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

fn render_menu_with_connection(
    colors: ColorMode,
    view: &ControlCenterView,
    connection: ConnectionState,
) -> String {
    format!(
        "{}\n{} {}",
        render_menu(colors, view),
        paint("CONNECTION:", "accent", colors),
        connection.label()
    )
}

fn render_page_with_connection_and_snapshot(
    page: Page,
    colors: ColorMode,
    view: &ControlCenterView,
    connection: ConnectionState,
    snapshot: Option<&ManagerSnapshot>,
) -> String {
    format!(
        "{}\n{} {}",
        render_page_with_snapshot(page, colors, view, snapshot),
        paint("LIVE CONNECTION:", "accent", colors),
        connection.label()
    )
}

fn proposed_action(page: Page) -> ProposedAction {
    match page {
        Page::Cores => ProposedAction::RestartCore,
        Page::Modules => ProposedAction::InstallModule,
        Page::Settings => ProposedAction::SaveSettings,
        Page::Security => ProposedAction::RequestApproval,
        Page::Updates => ProposedAction::UpdatePlatform,
        Page::Platform
        | Page::Diagnostics
        | Page::Fleet
        | Page::LibraryCatalog
        | Page::LibrarySources
        | Page::LibraryDownloads
        | Page::LibraryInstalled
        | Page::LibraryStorage
        | Page::LibraryHub
        | Page::LibraryHistory => ProposedAction::Inspect,
    }
}

fn action_request_line(page: Page, state: &ControlCenterView) -> String {
    match state.action_hint(proposed_action(page)) {
        ActionHint::Blocked(reason) => format!("ACTION REQUEST: BLOCKED / REASON: {reason}"),
        ActionHint::ReadOnly => "ACTION REQUEST: READ_ONLY / NO RECEIPT REQUIRED".to_owned(),
        ActionHint::RecheckWithService => format!(
            "ACTION REQUEST: PREVIEW_REQUIRED / REQUIRES_OWNER_APPROVAL / EXPLICIT_TARGET_REQUIRED / EXPECTED_GENERATION: {} / EXECUTION_RECEIPT_REQUIRED",
            state.platform_generation.map_or_else(
                || "UNKNOWN".to_owned(),
                |generation| generation.to_string(),
            )
        ),
    }
}

fn manager_page(page: Page) -> Option<ManagerPage> {
    match page {
        Page::Cores => Some(ManagerPage::Cores),
        Page::Modules => Some(ManagerPage::Modules),
        Page::Fleet => Some(ManagerPage::Fleet),
        Page::Security => Some(ManagerPage::Security),
        Page::Updates => Some(ManagerPage::Updates),
        Page::Diagnostics => Some(ManagerPage::Diagnostics),
        Page::Platform
        | Page::Settings
        | Page::LibraryCatalog
        | Page::LibrarySources
        | Page::LibraryDownloads
        | Page::LibraryInstalled
        | Page::LibraryStorage
        | Page::LibraryHub
        | Page::LibraryHistory => None,
    }
}

fn manager_section(
    page: Page,
    state: &ControlCenterView,
    snapshot: Option<&ManagerSnapshot>,
) -> String {
    manager_page(page).map_or_else(String::new, |manager| {
        let mut lines = manager_views::manager_lines(manager, state, snapshot);
        if let Some(snapshot) = snapshot {
            lines.extend(sofia_ui_broker::action_preview::context_lines(
                manager, state, snapshot,
            ));
        }
        lines.join("\n")
    })
}

#[cfg(test)]
fn render_page(page: Page, colors: ColorMode, state: &ControlCenterView) -> String {
    render_page_with_snapshot(page, colors, state, None)
}

fn render_page_with_snapshot(
    page: Page,
    colors: ColorMode,
    state: &ControlCenterView,
    snapshot: Option<&ManagerSnapshot>,
) -> String {
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
    let values = if current_status(state) {
        format!(
            "PLATFORM GENERATION: {} / SAVED SETTINGS REVISION: {} / APPLIED SETTINGS REVISION: {}",
            state
                .platform_generation
                .map_or_else(|| "UNKNOWN".into(), |value| value.to_string()),
            state
                .settings_revision
                .map_or_else(|| "UNKNOWN".into(), |value| value.to_string()),
            state
                .effective_settings_revision
                .map_or_else(|| "UNKNOWN".into(), |value| value.to_string()),
        )
    } else {
        "VALUES: UNAVAILABLE (not disconnected, removed, healthy or zero)".into()
    };
    let manager = manager_section(page, state, snapshot);
    let startup = if page == Page::Platform {
        manager_views::startup_lines(snapshot).join("\n")
    } else {
        String::new()
    };
    format!(
        "{}\nCONNECTION: {}\nSERVICE: {} / SOURCE: {}\nSETTINGS: {}\nINSTALLATION: {}\n{}\n{}\n{}\n{}\n{}\n{}\n{}",
        paint(page.heading(), "primary", colors),
        ConnectionState::from_view(state).label(),
        state.service_label(),
        state.source_label(),
        state.settings_label(),
        state.installation_label(),
        values,
        permission,
        action_request_line(page, state),
        "No writes, approvals, downloads, installation, state files or service changes.",
        startup,
        manager,
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
        "status={} source={} safe={} permission={} installation={} connection={}",
        status_name(view),
        status_source(view),
        view.safe_label(),
        view.permission_label(),
        view.installation_label(),
        ConnectionState::from_view(view).label()
    )
}

fn status_json(view: &ControlCenterView, snapshot: Option<&ManagerSnapshot>) -> Value {
    let current = current_status(view);
    let operator_stop = if current { Some(false) } else { None };
    // Startup and Core counts come only from the current authenticated
    // startup.status projection. Never infer them from a launch or a name.
    let startup = if current {
        snapshot.and_then(|snapshot| snapshot.startup.as_ref())
    } else {
        None
    };
    serde_json::json!({
        "schema": "aegis.ui.platform.status-display.v1",
        "status": status_name(view),
        "source": status_source(view),
        "connection": ConnectionState::from_view(view).label(),
        "platform_generation": if current { view.platform_generation } else { None },
        "safe": view.safe_label(),
        "operator_stop": operator_stop,
        "core_started": startup.map(|startup| startup.core_started),
        "startup_state": startup.map(|startup| startup.startup_state.label()),
        "core_count": startup.map(|startup| startup.core_count),
        "active_core_count": startup.map(|startup| startup.active_core_count),
        "cores_disabled": startup
            .map(|startup| startup.startup_state == StartupState::CoresDisabled),
        "management_listening": startup.map(|startup| startup.management_listening),
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

// Native Linux status implements the SAME reader. Composition is explicit:
// endpoint/config flags select the live native reader, otherwise OfflineReader.
fn run_with_source(source: &mut impl DisplayReadSource) -> io::Result<ExitCode> {
    let args: Vec<String> = env::args().skip(1).collect();
    let options = match CliOptions::from_process(&args) {
        Ok(options) => options,
        Err(error) => {
            eprintln!("{error}");
            return Ok(ExitCode::from(2));
        }
    };
    run_with_sources(source, None, None, &args, &options)
}

fn run_with_sources(
    source: &mut impl DisplayReadSource,
    mut snapshot_source: Option<&mut dyn AuthenticatedManagerSnapshotSource>,
    mutation_transport: Option<&mut dyn MutationTransport>,
    args: &[String],
    options: &CliOptions,
) -> io::Result<ExitCode> {
    let mut session = DisplaySession::default();
    if options.help {
        const HELP: &str = concat!(
            "aegis-tui [--plain | --help | --status | --status-json",
            " | --library-status | --library-json",
            " | --management-endpoint <native> --expected-platform-id <id>",
            " --expected-generation <n>]"
        );
        println!("{HELP}");
        println!("Endpoint and expected identity may also come from {ENV_ENDPOINT}, {ENV_PLATFORM_ID} and {ENV_GENERATION}.");
        println!("Without an endpoint this shell is explicitly read-only and OFFLINE.");
        println!("With an endpoint it reads the existing authenticated native management channel; no retry, discovery or second protocol.");
        println!("Protected manager actions are previews requiring a caller-supplied owner approval and a service receipt.");
        println!("Preview: p; attach approval: 'a <approval-id>'; submit: s.");
        println!("Keyboard: 1-15 select, j/k next/previous, Enter open, r refresh, q exit.");
        println!("Closing this shell never stops Platform, a Core or any service.");
        return Ok(ExitCode::SUCCESS);
    }
    let status_snapshot = if options.status || options.status_json {
        snapshot_source
            .as_mut()
            .map(|source| read_manager_snapshot(&mut **source))
    } else {
        None
    };
    let _ = session.refresh(source, std::time::Instant::now());
    if options.status {
        println!("{}", status_line(session.view()));
        return Ok(status_exit(session.view()));
    }
    if options.status_json {
        println!("{}", status_json(session.view(), status_snapshot.as_ref()));
        return Ok(status_exit(session.view()));
    }
    if options.library_json {
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
    if options.library_status {
        let status = concat!(
            "library=UNAVAILABLE source=UNVERIFIED catalog=UNKNOWN ",
            "cache=UNKNOWN installed=UNKNOWN active=UNKNOWN ",
            "received_bytes=UNKNOWN verified_bytes=UNKNOWN ",
            "internet_fallback=DISABLED actions=DISABLED"
        );
        println!("{status}");
        return Ok(ExitCode::from(3));
    }
    let colors = runtime_color_mode(args);
    if !io::stdin().is_terminal() {
        print!("{}", render_menu(ColorMode::Plain, session.view()));
        println!("\nInteractive input requires a terminal; no operation performed.");
        return Ok(ExitCode::SUCCESS);
    }
    let mutation_transport =
        mutation_transport.map(|transport| Box::new(transport) as Box<dyn MutationTransport + '_>);
    run_interactive(source, snapshot_source, mutation_transport, colors)
}

fn exact_target(page: Page, snapshot: Option<&ManagerSnapshot>) -> Option<String> {
    let snapshot = snapshot?;
    match manager_page(page)? {
        ManagerPage::Cores => snapshot.cores.first().map(|core| core.core_id.clone()),
        ManagerPage::Modules => snapshot
            .modules
            .first()
            .map(|module| module.module_id.clone()),
        ManagerPage::Security | ManagerPage::Updates => snapshot.platform_id.clone(),
        ManagerPage::Fleet | ManagerPage::Diagnostics => None,
    }
}

fn print_preview(
    page: Page,
    state: &ControlCenterView,
    snapshot: Option<&ManagerSnapshot>,
    approval: Option<&CallerApproval>,
) -> Option<ActionPreview> {
    let Some(manager) = manager_page(page) else {
        println!("ACTION PREVIEW: READ_ONLY / NO_MUTATION\n");
        return None;
    };
    let Some(snapshot) = snapshot else {
        println!("ACTION PREVIEW: BLOCKED / MANAGER_SNAPSHOT_NOT_OBSERVED\n");
        return None;
    };
    let Some(target) = exact_target(page, Some(snapshot)) else {
        println!(
            "ACTION PREVIEW: BLOCKED / EXACT_TARGET_NOT_SELECTED / DISPLAY_NAME_IS_NOT_AUTHORITY\n"
        );
        return None;
    };
    match ActionPreview::prepare(manager, &target, empty_payload(), state, snapshot) {
        Ok(preview) => {
            println!("{}\n", preview.lines(approval).join("\n"));
            Some(preview)
        }
        Err(error) => {
            println!("ACTION PREVIEW: BLOCKED / {}\n", error.label());
            None
        }
    }
}

fn random_id(prefix: &str) -> Option<String> {
    let mut bytes = [0_u8; 16];
    getrandom::getrandom(&mut bytes).ok()?;
    let mut id = String::from(prefix);
    for byte in bytes {
        write!(&mut id, "{byte:02x}").ok()?;
    }
    Some(id)
}

fn submit_preview<T: MutationTransport + ?Sized>(
    preview: &ActionPreview,
    approval: &CallerApproval,
    submitted: &mut MutationSubmission,
    transport: Option<&mut T>,
) {
    let Some(transport) = transport else {
        println!("SUBMISSION: NOT_SUBMITTED / NO_AUTHENTICATED_MUTATION_TRANSPORT\n");
        return;
    };
    let (Some(request_id), Some(correlation_id), Some(idempotency_key)) = (
        random_id("req:mutation:"),
        random_id("corr:"),
        random_id("idem:"),
    ) else {
        println!("SUBMISSION: NOT_SUBMITTED / ID_GENERATION_UNAVAILABLE\n");
        return;
    };
    let request_now = chrono::Utc::now().fixed_offset();
    let deadline = (request_now + chrono::Duration::seconds(30))
        .to_rfc3339_opts(chrono::SecondsFormat::Micros, true);
    let request = match preview.request(
        request_id,
        correlation_id,
        idempotency_key,
        &deadline,
        approval,
    ) {
        Ok(request) => request,
        Err(error) => {
            println!("SUBMISSION: NOT_SUBMITTED / {}\n", error.label());
            return;
        }
    };
    let mut client = MutationClient::new(transport);
    match submitted.submit_with_clock(&mut client, &request, request_now, || {
        chrono::Utc::now().fixed_offset()
    }) {
        Ok(outcome) => println!("{}\n", outcome.lines().join("\n")),
        Err(error) => println!("SUBMISSION: FAILED / {}\n", error.label()),
    }
}

#[allow(clippy::too_many_lines)]
fn run_interactive(
    source: &mut impl DisplayReadSource,
    mut snapshot_source: Option<&mut dyn AuthenticatedManagerSnapshotSource>,
    mut mutation_transport: Option<Box<dyn MutationTransport + '_>>,
    colors: ColorMode,
) -> io::Result<ExitCode> {
    let mut session = DisplaySession::default();
    let mut selected = 0;
    let mut connection = ConnectionStateModel::default();
    let mut preview: Option<ActionPreview> = None;
    let mut approval: Option<CallerApproval> = None;
    let mut submitted = MutationSubmission::default();
    loop {
        let _ = session.refresh(source, std::time::Instant::now());
        session.expire_at(std::time::Instant::now());
        connection.observe_link(session.view().link);
        println!(
            "{}",
            render_menu_with_connection(colors, session.view(), connection.state())
        );
        print!(
            "Select [0-15], j/k next/previous, Enter selected, p preview, a <approval-id>, s submit, r refresh, q exit: "
        );
        io::stdout().flush()?;
        let mut selection = String::new();
        if io::stdin().read_line(&mut selection)? == 0 {
            return Ok(ExitCode::SUCCESS);
        }
        let command = navigate(&selection, &mut selected);
        if command == Navigation::Exit {
            return Ok(ExitCode::SUCCESS);
        }
        let _ = session.refresh(source, std::time::Instant::now());
        session.expire_at(std::time::Instant::now());
        connection.observe_link(session.view().link);
        let snapshot = snapshot_source
            .as_mut()
            .map(|source| read_manager_snapshot(&mut **source));
        match command {
            Navigation::Exit => unreachable!("exit handled before service refresh"),
            Navigation::Show(page) => {
                if preview
                    .as_ref()
                    .is_some_and(|preview| manager_page(page) != Some(preview.page))
                {
                    preview = None;
                    approval = None;
                }
                println!(
                    "{}\n",
                    render_page_with_connection_and_snapshot(
                        page,
                        colors,
                        session.view(),
                        connection.state(),
                        snapshot.as_ref(),
                    )
                );
            }
            Navigation::Preview => {
                preview = print_preview(
                    PAGES[selected],
                    session.view(),
                    snapshot.as_ref(),
                    approval.as_ref(),
                );
            }
            Navigation::Approval(value) => match CallerApproval::new(value) {
                Ok(value) => {
                    approval = Some(value);
                    if let Some(preview) = &preview {
                        println!("{}\n", preview.lines(approval.as_ref()).join("\n"));
                    } else {
                        println!("APPROVAL: SUPPLIED / NO_PREVIEW_SELECTED\n");
                    }
                }
                Err(error) => {
                    println!("APPROVAL: REJECTED / {}\n", error.label());
                }
            },
            Navigation::Submit => match (&preview, &approval) {
                (None, _) => println!("SUBMISSION: NOT_SUBMITTED / NO_PREVIEW\n"),
                (Some(_), None) => {
                    println!("SUBMISSION: NOT_SUBMITTED / CALLER_SUPPLIED_APPROVAL_ID_REQUIRED\n");
                }
                (Some(preview), Some(approval)) => {
                    submit_preview(
                        preview,
                        approval,
                        &mut submitted,
                        mutation_transport.as_deref_mut(),
                    );
                }
            },
            Navigation::Refresh => {
                connection.begin_reconnect();
                let _ = session.refresh(source, std::time::Instant::now());
                session.expire_at(std::time::Instant::now());
                connection.observe_link(session.view().link);
                println!(
                    "{} reconnect_attempts={}",
                    status_line(session.view()),
                    connection.reconnect_attempts()
                );
            }
            Navigation::Invalid => {
                println!("Not a valid menu command; no operation performed.\n");
            }
        }
    }
}

fn run() -> io::Result<ExitCode> {
    let args: Vec<String> = env::args().skip(1).collect();
    let options = match CliOptions::from_process(&args) {
        Ok(options) => options,
        Err(error) => {
            eprintln!("{error}");
            return Ok(ExitCode::from(2));
        }
    };
    let Ok(target) = options.live_target() else {
        // A partial or malformed live configuration is a denial, never a
        // reason to fall back to fabricated offline health.
        return run_with_sources(
            &mut FailureReader(ReadFailure::Denied),
            None,
            None,
            &args,
            &options,
        );
    };
    let Some(target) = target else {
        // No endpoint supplied: retain explicit NOT_OBSERVED/offline behavior.
        return run_with_source(&mut OfflineReader);
    };
    match native_management::open_live_management_readers(
        &target.endpoint,
        &target.platform_id,
        target.generation,
    ) {
        Err(ReadFailure::Offline) => run_with_sources(
            &mut FailureReader(ReadFailure::Unverified),
            None,
            None,
            &args,
            &options,
        ),
        Err(failure) => run_with_sources(&mut FailureReader(failure), None, None, &args, &options),
        Ok((status_reader, snapshot_reader)) => {
            let mut status_reader = ConfiguredStatusReader {
                inner: status_reader,
                observed: false,
            };
            let mut snapshot_reader = ConfiguredSnapshotReader {
                inner: snapshot_reader,
                observed: false,
            };
            run_with_sources(
                &mut status_reader,
                Some(&mut snapshot_reader),
                None,
                &args,
                &options,
            )
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
    use super::{
        action_request_line, choose_color_mode, navigate, paint, render_menu, render_page,
        render_page_with_snapshot, rgb, select_page, status_exit, status_json, status_line,
        valid_platform_id, CliError, CliOptions, ColorMode, Navigation, Page, PAGES,
    };
    use sofia_ui_broker::control_center::{
        ControlCenterView, InstallationState, LinkState, PermissionState, SafeState,
    };

    #[test]
    fn keyboard_navigation_reaches_every_section_and_refresh_never_mutates() {
        let mut selected = 0;
        assert_eq!(
            navigate("", &mut selected),
            Navigation::Show(Page::Platform)
        );
        for page in PAGES.iter().skip(1) {
            assert_eq!(navigate("j", &mut selected), Navigation::Show(*page));
        }
        assert_eq!(
            navigate("next", &mut selected),
            Navigation::Show(Page::Platform)
        );
        assert_eq!(
            navigate("k", &mut selected),
            Navigation::Show(Page::LibraryHistory)
        );
        assert_eq!(
            navigate("1", &mut selected),
            Navigation::Show(Page::Platform)
        );
        assert_eq!(navigate("r", &mut selected), Navigation::Refresh);
        assert_eq!(navigate("p", &mut selected), Navigation::Preview);
        assert_eq!(
            navigate("a approval:owner:1", &mut selected),
            Navigation::Approval("approval:owner:1".into())
        );
        assert_eq!(navigate("s", &mut selected), Navigation::Submit);
        assert_eq!(selected, 0);
        assert_eq!(navigate("approve", &mut selected), Navigation::Invalid);
        assert_eq!(navigate("q", &mut selected), Navigation::Exit);
    }

    #[test]
    fn snapshot_aware_pages_show_exact_target_and_never_fabricate_success() {
        use sofia_ui_broker::manager_views::{
            CoreLifecycle, CoreObservation, ManagedHealth, ManagerPage, ManagerSnapshot,
            SectionTruth,
        };
        use sofia_ui_broker::platform_status::ObservationFreshness;
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        view.safe = SafeState::Clear;
        view.permission = PermissionState::MayRequest;
        view.platform_generation = Some(9);
        view.installation = InstallationState::Absent;
        view.settings_revision = Some(4);
        view.effective_settings_revision = Some(4);
        let mut snapshot = ManagerSnapshot {
            freshness: ObservationFreshness::Fresh,
            platform_id: Some("platform:alpha".into()),
            platform_generation: Some(9),
            platform_revision: Some(6),
            ..ManagerSnapshot::default()
        };
        snapshot.mark(ManagerPage::Cores, SectionTruth::Observed);
        snapshot.cores.push(CoreObservation {
            core_id: "core:primary".into(),
            lifecycle: CoreLifecycle::Active,
            health: ManagedHealth::VerifiedHealthy,
            generation: 3,
            source_digest: Some("a".repeat(64)),
            installed: None,
            enabled: None,
            startup_mode: None,
            observed_state: None,
            last_error_code: None,
        });
        let text = render_page_with_snapshot(Page::Cores, ColorMode::Plain, &view, Some(&snapshot));
        assert!(text.contains("CORE core:primary"));
        assert!(text.contains("SNAPSHOT TARGET: platform:alpha"));
        assert!(text.contains("ACTION PREVIEW CONTEXT: core.restart"));
        assert!(text.contains("EXPECTED REVISION: 6"));
        assert!(!text.contains('\x1b'));

        snapshot.mark(ManagerPage::Cores, SectionTruth::Revoked);
        snapshot.cores.clear();
        let denied =
            render_page_with_snapshot(Page::Cores, ColorMode::Plain, &view, Some(&snapshot));
        assert!(denied.contains("CORE MANAGER: REVOKED"));
        assert!(!denied.contains("NONE_INSTALLED"));
        assert!(!denied.contains("VERIFIED_HEALTHY"));
    }

    #[test]
    fn protected_pages_require_preview_target_generation_and_receipt() {
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        view.safe = SafeState::Clear;
        view.permission = PermissionState::MayRequest;
        view.platform_generation = Some(12);
        view.installation = InstallationState::Absent;
        view.settings_revision = Some(4);
        view.effective_settings_revision = Some(4);
        for page in [
            Page::Cores,
            Page::Modules,
            Page::Settings,
            Page::Security,
            Page::Updates,
        ] {
            let line = action_request_line(page, &view);
            assert!(line.contains("PREVIEW_REQUIRED"));
            assert!(line.contains("EXPLICIT_TARGET_REQUIRED"));
            assert!(line.contains("EXPECTED_GENERATION: 12"));
            assert!(line.contains("EXECUTION_RECEIPT_REQUIRED"));
        }
        assert_eq!(
            action_request_line(Page::Platform, &view),
            "ACTION REQUEST: READ_ONLY / NO RECEIPT REQUIRED"
        );
    }

    #[test]
    fn stale_revoked_stop_and_denied_views_cannot_offer_action_requests() {
        for (link, safe, permission, reason) in [
            (
                LinkState::Stale,
                SafeState::Clear,
                PermissionState::MayRequest,
                "OBSERVATION_STALE",
            ),
            (
                LinkState::Revoked,
                SafeState::Clear,
                PermissionState::MayRequest,
                "OWNER_REVOKED",
            ),
            (
                LinkState::Observed,
                SafeState::StopActive,
                PermissionState::MayRequest,
                "SAFE_STOP_ACTIVE",
            ),
            (
                LinkState::Observed,
                SafeState::Clear,
                PermissionState::Denied,
                "PERMISSION_DENIED",
            ),
        ] {
            let mut view = ControlCenterView::offline();
            view.link = link;
            view.safe = safe;
            view.permission = permission;
            view.platform_generation = Some(12);
            let line = action_request_line(Page::Updates, &view);
            assert_eq!(line, format!("ACTION REQUEST: BLOCKED / REASON: {reason}"));
            assert!(!line.contains("EXPECTED_GENERATION"));
        }
    }

    #[test]
    fn terminal_color_selection_is_bounded_and_honors_plain_and_no_color() {
        assert_eq!(
            choose_color_mode(
                true,
                false,
                false,
                Some("xterm-256color"),
                Some("truecolor")
            ),
            ColorMode::TrueColor
        );
        assert_eq!(
            choose_color_mode(true, false, false, Some("xterm"), None),
            ColorMode::Ansi16
        );
        for (terminal, plain, no_color, term, color) in [
            (false, false, false, Some("xterm"), Some("truecolor")),
            (true, true, false, Some("xterm"), Some("truecolor")),
            (true, false, true, Some("xterm"), Some("truecolor")),
            (true, false, false, Some("dumb"), Some("truecolor")),
            (true, false, false, None, Some("truecolor")),
        ] {
            assert_eq!(
                choose_color_mode(terminal, plain, no_color, term, color),
                ColorMode::Plain
            );
        }
        assert_eq!(
            choose_color_mode(true, false, false, Some("xterm"), Some("nottruecolor")),
            ColorMode::Ansi16
        );
        let limited = render_menu(ColorMode::Ansi16, &ControlCenterView::offline());
        assert!(limited.contains("\x1b["));
        assert!(!limited.contains("38;2;"));
        let plain = render_menu(ColorMode::Plain, &ControlCenterView::offline());
        assert!(plain.is_ascii());
        assert!(!plain.contains('\x1b'));
    }

    #[test]
    fn theme_imports_exact_shared_manifest() {
        assert_eq!(rgb("primary"), Some((148, 0, 211)));
        assert_eq!(rgb("accent"), Some((0, 194, 255)));
        assert_eq!(rgb("tertiary"), Some((57, 255, 20)));
    }

    #[test]
    fn plain_mode_has_no_ansi_or_unsupported_authority_claims() {
        let menu = render_menu(ColorMode::Plain, &ControlCenterView::offline());
        assert!(!menu.contains('\x1b'));
        assert!(menu.contains("UNAVAILABLE"));
        assert!(menu.contains("SOURCE UNVERIFIED"));
        assert!(menu.contains("Settings"));
        assert!(!menu.contains("VERIFIED HEALTHY"));
        let page = render_page(
            Page::Settings,
            ColorMode::Plain,
            &ControlCenterView::offline(),
        );
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
            let page = render_page(Page::Modules, ColorMode::Plain, &state);
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
        let page = render_page(Page::Security, ColorMode::Plain, &state);
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
            let text = render_page(page, ColorMode::Plain, &ControlCenterView::offline());
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
        let data = status_json(&view, None);
        assert_eq!(data["schema"], "aegis.ui.platform.status-display.v1");
        assert_eq!(data["platform_generation"], serde_json::Value::Null);
        assert_eq!(data["operator_stop"], serde_json::Value::Null);
        assert_eq!(data["core_started"], serde_json::Value::Null);
        assert_eq!(data["actions_enabled"], false);
        assert_eq!(data["installation"], "NOT_CURRENTLY_VERIFIED");
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
    }

    #[test]
    fn verified_page_shows_revisions_but_stale_page_hides_cached_values() {
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        view.platform_generation = Some(9);
        view.safe = SafeState::Clear;
        view.settings_revision = Some(7);
        view.effective_settings_revision = Some(6);
        let observed = render_page(Page::Settings, ColorMode::Plain, &view);
        assert!(observed.contains("PLATFORM GENERATION: 9"));
        assert!(observed.contains("SAVED SETTINGS REVISION: 7"));
        assert!(observed.contains("APPLIED SETTINGS REVISION: 6"));
        view.link = LinkState::Stale;
        let stale = render_page(Page::Settings, ColorMode::Plain, &view);
        assert!(stale.contains("VALUES: UNAVAILABLE"));
        assert!(!stale.contains("PLATFORM GENERATION: 9"));
        assert!(!stale.contains("SETTINGS REVISION: 7"));
    }

    #[test]
    fn menu_reflects_observation_or_denial_instead_of_hardcoded_offline() {
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Revoked;
        let denied = render_menu(ColorMode::Plain, &view);
        assert!(denied.contains("SERVICE REVOKED"));
        assert!(denied.contains("SOURCE REVOKED"));
        view.link = LinkState::Observed;
        view.platform_generation = Some(9);
        let live = render_menu(ColorMode::Plain, &view);
        assert!(live.contains("SERVICE OBSERVED"));
        assert!(live.contains("SOURCE SERVICE_OBSERVED"));
        assert!(!live.contains("SERVICE UNAVAILABLE"));
    }

    #[test]
    fn only_service_observed_generation_can_make_status_cli_success() {
        use sofia_ui_broker::manager_views::ManagerSnapshot;
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        view.platform_generation = Some(8);
        view.safe = SafeState::StopActive;
        assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        let denied = status_json(&view, None);
        assert_eq!(denied["status"], "STOP_ACTIVE");
        assert_eq!(denied["source"], "UNVERIFIED");
        assert_eq!(denied["platform_generation"], serde_json::Value::Null);
        view.safe = SafeState::Clear;
        assert_eq!(status_exit(&view), std::process::ExitCode::SUCCESS);
        let mut snapshot = ManagerSnapshot {
            platform_id: Some("platform:alpha".into()),
            platform_generation: Some(8),
            ..ManagerSnapshot::default()
        };
        snapshot.startup = Some(sofia_ui_broker::manager_views::StartupObservation {
            core_started: false,
            core_count: 0,
            active_core_count: 0,
            startup_state: sofia_ui_broker::manager_views::StartupState::ZeroCoreHealthy,
            autostart_enabled_count: 0,
            autostart_reconciled_at: None,
            management_listening: true,
        });
        let data = status_json(&view, Some(&snapshot));
        assert_eq!(data["status"], "OBSERVED");
        assert_eq!(data["source"], "SERVICE_OBSERVED");
        assert_eq!(data["platform_generation"], 8);
        assert_eq!(data["operator_stop"], false);
        assert_eq!(data["core_started"], false);
        assert_eq!(data["startup_state"], "ZERO_CORE_HEALTHY");
        assert_eq!(data["core_count"], 0);
        assert_eq!(data["management_listening"], true);
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
            let data = status_json(&view, None);
            assert_eq!(data["status"], expected);
            assert_eq!(data["platform_generation"], serde_json::Value::Null);
            assert_eq!(data["operator_stop"], serde_json::Value::Null);
            assert_eq!(data["actions_enabled"], false);
            assert_eq!(status_exit(&view), std::process::ExitCode::from(3));
        }
    }

    #[test]
    fn live_startup_flags_require_exact_endpoint_identity_tuple() {
        let args = [
            "--plain",
            "--status-json",
            "--management-endpoint",
            r"\\.\pipe\aegis-test",
            "--expected-platform-id",
            "platform:alpha",
            "--expected-generation",
            "7",
        ]
        .map(str::to_owned);
        let options = CliOptions::parse(&args).expect("reviewed flags");
        assert!(options.plain);
        assert!(options.status_json);
        assert_eq!(
            options.live_target().unwrap(),
            Some(super::LiveTarget {
                endpoint: r"\\.\pipe\aegis-test".into(),
                platform_id: "platform:alpha".into(),
                generation: 7,
            })
        );
        let equals = ["--management-endpoint=/tmp/aegis.sock".to_owned()];
        assert_eq!(
            CliOptions::parse(&equals).unwrap().endpoint.as_deref(),
            Some("/tmp/aegis.sock")
        );
        assert_eq!(
            CliOptions::parse(&["--management-endpoint".to_owned()]).unwrap_err(),
            CliError::MissingValue("--management-endpoint".into())
        );
        assert!(matches!(
            CliOptions::parse(&["--expected-generation".into(), "nope".into()]),
            Err(CliError::InvalidGeneration(_))
        ));
        assert!(matches!(
            CliOptions::parse(&["--install".into()]),
            Err(CliError::Unknown(_))
        ));
        let partial = [
            "--management-endpoint".to_owned(),
            "endpoint".to_owned(),
            "--expected-platform-id".to_owned(),
            "platform:alpha".to_owned(),
        ];
        assert!(CliOptions::parse(&partial).unwrap().live_target().is_err());
        assert!(valid_platform_id("platform:alpha"));
        assert!(!valid_platform_id("../bad"));
    }

    #[test]
    fn startup_core_inventory_renders_disabled_cores_without_health_claims() {
        use sofia_ui_broker::manager_views::{
            CoreLifecycle, CoreObservation, ManagedHealth, ManagerPage, ManagerSnapshot,
            SectionTruth, StartupObservation, StartupState,
        };
        use sofia_ui_broker::platform_status::ObservationFreshness;
        let mut view = ControlCenterView::offline();
        view.link = LinkState::Observed;
        view.safe = SafeState::Clear;
        view.permission = PermissionState::MayRequest;
        view.platform_generation = Some(4);
        let mut snapshot = ManagerSnapshot {
            freshness: ObservationFreshness::Fresh,
            platform_id: Some("platform:alpha".into()),
            platform_generation: Some(4),
            startup: Some(StartupObservation {
                core_started: false,
                core_count: 1,
                active_core_count: 0,
                startup_state: StartupState::CoresDisabled,
                autostart_enabled_count: 0,
                autostart_reconciled_at: None,
                management_listening: true,
            }),
            ..ManagerSnapshot::default()
        };
        snapshot.mark(ManagerPage::Cores, SectionTruth::Observed);
        snapshot.cores.push(CoreObservation {
            core_id: "01234567-89ab-cdef-0123-456789abcdef".into(),
            lifecycle: CoreLifecycle::Disabled,
            health: ManagedHealth::Unknown,
            generation: 0,
            source_digest: None,
            installed: Some(true),
            enabled: Some(false),
            startup_mode: Some("manual".into()),
            observed_state: Some("STOPPED".into()),
            last_error_code: Some("OPERATOR_STOP".into()),
        });
        let platform =
            render_page_with_snapshot(Page::Platform, ColorMode::Plain, &view, Some(&snapshot));
        assert!(platform.contains("STARTUP: state=CORES_DISABLED"));
        assert!(platform.contains("core_started=NO"));
        assert!(platform.contains("active_core_count=0"));
        let cores =
            render_page_with_snapshot(Page::Cores, ColorMode::Plain, &view, Some(&snapshot));
        assert!(cores.contains("STARTUP: state=CORES_DISABLED"));
        assert!(cores.contains("lifecycle=DISABLED"));
        assert!(cores.contains("health=UNKNOWN"));
        assert!(cores.contains("installed=YES"));
        assert!(cores.contains("enabled=NO"));
        assert!(cores.contains("observed_state=STOPPED"));
        assert!(cores.contains("last_error_code=OPERATOR_STOP"));
        assert!(!cores.contains("VERIFIED_HEALTHY"));
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
        assert!(paint("X", "accent", ColorMode::Plain) == "X");
    }
}
