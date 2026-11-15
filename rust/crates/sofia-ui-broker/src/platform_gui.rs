//! Rust desktop presentation. No enrollment, permission engine or state writer.
use eframe::egui;
use sofia_ui_broker::connection_state::ConnectionStateModel;
use sofia_ui_broker::control_center::{ActionHint, ControlCenterView, ProposedAction};
use sofia_ui_broker::control_center_session::{DisplayReadSource, DisplaySession, OfflineReader};
use sofia_ui_broker::manager_views::{self, ManagerPage};
use std::time::{Duration, Instant};

const THEME: &str = include_str!("../../../../contracts/ui/aegis-theme-v1.json");

/// The source must be composed by the installer-backed authenticated IPC layer.
/// This wrapper cannot establish publisher trust or owner enrollment.
pub struct DesktopStatus<S: DisplayReadSource> {
    session: DisplaySession,
    source: S,
    connection: ConnectionStateModel,
    error: Option<String>,
}
impl<S: DisplayReadSource> DesktopStatus<S> {
    pub fn new(source: S) -> Self {
        Self {
            session: DisplaySession::default(),
            source,
            connection: ConnectionStateModel::default(),
            error: None,
        }
    }
    pub fn refresh(&mut self) {
        self.error = self
            .session
            .refresh(&mut self.source, Instant::now())
            .err()
            .map(|error| format!("Rejected status: {error:?}"));
        self.connection.observe_link(self.session.view().link);
    }
    pub fn draw(&mut self, ui: &mut egui::Ui) {
        self.session.expire_at(Instant::now());
        self.connection.observe_link(self.session.view().link);
        let view = self.session.view();
        egui::Grid::new("verified-status")
            .striped(true)
            .show(ui, |ui| {
                for (name, value) in [
                    ("Connection", self.connection.state().label()),
                    ("Management", view.service_label()),
                    ("Observation source", view.source_label()),
                    ("SAFE / STOP", view.safe_label()),
                    ("Permissions", view.permission_label()),
                    ("Installation", view.installation_label()),
                ] {
                    ui.label(name);
                    ui.monospace(value);
                    ui.end_row();
                }
                ui.label("Platform identity");
                ui.monospace(self.session.platform_id().unwrap_or("NOT VERIFIED"));
                ui.end_row();
                ui.label("Generation");
                ui.monospace(
                    view.platform_generation
                        .map_or_else(|| "UNKNOWN".into(), |v| v.to_string()),
                );
                ui.end_row();
            });
        if let Some(error) = &self.error {
            ui.colored_label(egui::Color32::LIGHT_RED, error);
        }
    }
    pub fn diagnostic(&self) -> String {
        let view = self.session.view();
        format!(
            "Aegis desktop diagnostic\nConnection: {}\nManagement: {}\nSource: {}\nPlatform: {}\nSAFE: {}\nPermission: {}\nInstallation: {}\n",
            self.connection.state().label(),
            view.service_label(),
            view.source_label(),
            self.session.platform_id().unwrap_or("NOT VERIFIED"),
            view.safe_label(),
            view.permission_label(),
            view.installation_label()
        )
    }
}

pub fn apply_theme(context: &egui::Context) {
    let mut visuals = egui::Visuals::dark();
    if let Ok(theme) = serde_json::from_str::<serde_json::Value>(THEME) {
        let color = |key: &str| -> Option<egui::Color32> {
            let value = theme.get("tokens")?.get(key)?.as_str()?;
            if value.len() != 7 || !value.starts_with('#') {
                return None;
            }
            Some(egui::Color32::from_rgb(
                u8::from_str_radix(&value[1..3], 16).ok()?,
                u8::from_str_radix(&value[3..5], 16).ok()?,
                u8::from_str_radix(&value[5..7], 16).ok()?,
            ))
        };
        if let Some(value) = color("surface_card") {
            visuals.panel_fill = value;
        }
        if let Some(value) = color("accent") {
            visuals.selection.bg_fill = value;
        }
        if let Some(value) = color("text_main") {
            visuals.override_text_color = Some(value);
        }
    }
    context.set_visuals(visuals);
}

const PAGES: &[&str] = &[
    "Dashboard",
    "Fleet",
    "Core Manager",
    "Modules",
    "Library",
    "Models",
    "Downloads",
    "Security",
    "Updates / Recovery",
    "Resources",
    "Settings",
    "Diagnostics",
];

fn proposed_action(page: usize) -> ProposedAction {
    match page {
        2 => ProposedAction::RestartCore,
        3 => ProposedAction::InstallModule,
        7 => ProposedAction::RequestApproval,
        8 => ProposedAction::UpdatePlatform,
        10 => ProposedAction::SaveSettings,
        _ => ProposedAction::Inspect,
    }
}

fn action_label(page: usize) -> &'static str {
    match page {
        2 => "Restart selected Core",
        3 => "Install selected module",
        7 => "Request owner approval",
        8 => "Update Platform",
        10 => "Save Platform settings",
        _ => "Inspect current state",
    }
}

fn action_status(page: usize, view: &ControlCenterView) -> String {
    match view.action_hint(proposed_action(page)) {
        ActionHint::Blocked(reason) => format!("BLOCKED · {reason}"),
        ActionHint::ReadOnly => "READ ONLY · CURRENT OBSERVATION AVAILABLE".to_owned(),
        ActionHint::RecheckWithService => format!(
            "SERVICE RECHECK REQUIRED · PREVIEW · REQUIRES OWNER APPROVAL · EXPLICIT TARGET · GENERATION {} · RECEIPT",
            view.platform_generation
                .map_or_else(|| "UNKNOWN".to_owned(), |value| value.to_string())
        ),
    }
}

pub struct PlatformApp<S: DisplayReadSource> {
    status: DesktopStatus<S>,
    page: usize,
    manager_snapshot: Option<manager_views::ManagerSnapshot>,
    large_text: bool,
    compact: bool,
}
impl<S: DisplayReadSource> PlatformApp<S> {
    pub fn new(source: S) -> Self {
        Self {
            status: DesktopStatus::new(source),
            page: 0,
            manager_snapshot: None,
            large_text: false,
            compact: false,
        }
    }

    /// Supply only observations produced by the separately authenticated
    /// management client. This does not verify or authorize the snapshot.
    #[allow(dead_code)] // integration seam for the installed management client
    pub fn set_manager_snapshot(&mut self, snapshot: Option<manager_views::ManagerSnapshot>) {
        self.manager_snapshot = snapshot;
    }

    fn manager_panel(&mut self, ui: &mut egui::Ui, manager: ManagerPage) {
        let view = self.status.session.view().clone();
        for line in manager_views::manager_lines(manager, &view, self.manager_snapshot.as_ref()) {
            ui.monospace(line);
        }
        ui.separator();
        ui.add_enabled(false, egui::Button::new(action_label(self.page)));
        ui.monospace(action_status(self.page, &view));
    }

    fn body(&mut self, ui: &mut egui::Ui) {
        ui.heading(PAGES[self.page]);
        ui.separator();
        match self.page {
            0 => {
                self.status.draw(ui);
                ui.separator();
                ui.label("Core-free operation: the desktop does not require a Core or an inference provider.");
                ui.label("Launching this window does not verify an installation or service.");
            }
            1 => {
                ui.label("Enrolled peers, candidates, stale and unreachable hosts remain distinct. Discovery and callsigns are not permission.");
                self.manager_panel(ui, ManagerPage::Fleet);
            }
            2 => {
                ui.label("Core identity, lifecycle and health come only from the authenticated Platform. A Core-free Platform remains usable.");
                self.manager_panel(ui, ManagerPage::Cores);
            }
            3 => {
                ui.label("Installed lifecycle and verified runtime health remain separate. Removal requires a receipt.");
                self.manager_panel(ui, ManagerPage::Modules);
            }
            7 => {
                ui.label("SAFE/STOP, approvals, revocation and grants are service-owned. This window cannot grant permissions.");
                self.manager_panel(ui, ManagerPage::Security);
            }
            8 => {
                ui.label("Release preview, rollback eligibility and staged receipts are read-only observations.");
                self.manager_panel(ui, ManagerPage::Updates);
            }
            10 => {
                ui.label("Desktop appearance (this window only)");
                ui.checkbox(&mut self.large_text, "Larger text");
                ui.checkbox(&mut self.compact, "Compact spacing");
                ui.label("Platform settings require canonical authenticated settings IPC; no local configuration is written.");
                ui.separator();
                ui.add_enabled(false, egui::Button::new(action_label(self.page)));
                ui.monospace(action_status(self.page, self.status.session.view()));
            }
            11 => {
                ui.label(
                    "Bounded diagnostic summary; no private files, logs or credentials are read.",
                );
                self.manager_panel(ui, ManagerPage::Diagnostics);
                if ui.button("Copy diagnostic summary").clicked() {
                    ui.ctx().copy_text(self.status.diagnostic());
                }
                ui.monospace(self.status.diagnostic());
            }
            _ => {
                let explanation = match self.page {
                    1 => "Fleet membership and callsign ownership require current enrollment and registry evidence. No current Fleet observation is available.",
                    2 => "Core discovery, installation, start and detach require authenticated Core Link and exact owner approval. No current Core observation is available.",
                    3 => "Signed module inventory and lifecycle require authenticated module management IPC. No module inventory has been verified.",
                    4 => "Library catalog, sources, installed inventory and licensing require authenticated Library observations. An empty view does not mean the Library is empty.",
                    5 => "Model availability must come from the canonical provider and verified Library. No model availability has been observed.",
                    6 => "No current authenticated download observation. Downloads are not started by this window.",
                    7 => "Owner authority, approvals, revocation and STOP are enforced by the canonical service. This desktop cannot grant permissions.",
                    8 => "Signed updates, rollback and restore require current authenticated release authority. No release operation is available through this adapter.",
                    _ => "Resource measurements require an authenticated current service observation. No CPU, memory or disk estimate is fabricated.",
                };
                ui.label(explanation);
                ui.separator();
                self.status.draw(ui);
                let view = self.status.session.view();
                let status = action_status(self.page, view);
                ui.add_enabled(false, egui::Button::new(action_label(self.page)));
                ui.monospace(status);
                ui.label("Buttons never grant authority. Protected execution requires a fresh canonical service decision and a verified operation receipt.");
            }
        }
    }
}
impl<S: DisplayReadSource> eframe::App for PlatformApp<S> {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        context.set_zoom_factor(if self.large_text { 1.25 } else { 1.0 });
        context
            .style_mut(|style| style.spacing.item_spacing.y = if self.compact { 4.0 } else { 9.0 });
        egui::TopBottomPanel::top("top").show(context, |ui| {
            ui.horizontal(|ui| {
                ui.heading("AEGIS · Platform Control Center");
                if ui.button("Refresh / reconnect").clicked() {
                    self.status.refresh();
                }
                if ui.button("Close window").clicked() {
                    context.send_viewport_cmd(egui::ViewportCommand::Close);
                }
            });
            ui.label("Read-only presentation · service authority remains external");
        });
        egui::SidePanel::left("navigation")
            .resizable(true)
            .show(context, |ui| {
                for (index, name) in PAGES.iter().enumerate() {
                    ui.selectable_value(&mut self.page, index, *name);
                }
            });
        egui::CentralPanel::default().show(context, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| self.body(ui));
        });
        context.request_repaint_after(Duration::from_secs(1));
    }
}

pub fn run() -> eframe::Result {
    run_with_source(OfflineReader)
}

/// Compose only an independently authenticated reader from the installed service.
pub fn run_with_source<S: DisplayReadSource + 'static>(source: S) -> eframe::Result {
    eframe::run_native(
        "Aegis Platform Control Center",
        eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default()
                .with_inner_size([1060.0, 720.0])
                .with_min_inner_size([640.0, 480.0]),
            ..Default::default()
        },
        Box::new(move |creation| {
            apply_theme(&creation.egui_ctx);
            Ok(Box::new(PlatformApp::new(source)))
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use sofia_ui_broker::control_center::{InstallationState, PermissionState, SafeState};
    use sofia_ui_broker::control_center_session::{DisplaySnapshot, ReadFailure};
    struct Synthetic {
        sequence: u64,
        denied: bool,
    }
    impl DisplayReadSource for Synthetic {
        fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
            if self.denied {
                return Err(ReadFailure::Revoked);
            }
            self.sequence += 1;
            Ok(DisplaySnapshot {
                platform_id: "synthetic:platform".into(),
                generation: 1,
                sequence: self.sequence,
                safe: SafeState::Clear,
                permission: PermissionState::Unknown,
                installation: InstallationState::Unknown,
                saved_revision: None,
                applied_revision: None,
                removal_receipt_verified: false,
            })
        }
    }
    #[test]
    fn offline_launch_does_not_imply_health_or_installation() {
        let status = DesktopStatus::new(OfflineReader);
        assert!(status.diagnostic().contains("Management: UNAVAILABLE"));
        assert!(status
            .diagnostic()
            .contains("Installation: NOT_CURRENTLY_VERIFIED"));
    }
    #[test]
    fn revocation_clears_current_permission_and_health() {
        let mut status = DesktopStatus::new(Synthetic {
            sequence: 0,
            denied: false,
        });
        status.refresh();
        assert!(status.diagnostic().contains("Management: OBSERVED"));
        status.source.denied = true;
        status.refresh();
        assert!(status.diagnostic().contains("Management: REVOKED"));
        assert!(status.diagnostic().contains("Permission: UNKNOWN"));
        assert!(!status.diagnostic().contains("Management: OBSERVED"));
    }
    #[test]
    fn every_page_renders_without_a_core_or_display_server() {
        let context = egui::Context::default();
        apply_theme(&context);
        let mut app = PlatformApp::new(OfflineReader);
        for page in 0..PAGES.len() {
            app.page = page;
            let _ = context.run(egui::RawInput::default(), |ctx| {
                egui::CentralPanel::default().show(ctx, |ui| app.body(ui));
            });
        }
    }

    #[test]
    fn page_actions_explain_exact_authority_blockers() {
        let offline = ControlCenterView::offline();
        assert_eq!(action_status(2, &offline), "BLOCKED · PLATFORM_OFFLINE");
        assert_eq!(action_status(4, &offline), "BLOCKED · PLATFORM_OFFLINE");

        let mut current = ControlCenterView::offline();
        current.link = sofia_ui_broker::control_center::LinkState::Observed;
        current.safe = SafeState::Clear;
        current.permission = PermissionState::MayRequest;
        current.platform_generation = Some(14);
        current.installation = InstallationState::Absent;
        assert_eq!(
            action_status(2, &current),
            "SERVICE RECHECK REQUIRED · PREVIEW · REQUIRES OWNER APPROVAL · EXPLICIT TARGET · GENERATION 14 · RECEIPT"
        );
        assert_eq!(
            action_status(4, &current),
            "READ ONLY · CURRENT OBSERVATION AVAILABLE"
        );

        current.safe = SafeState::StopActive;
        assert_eq!(action_status(8, &current), "BLOCKED · SAFE_STOP_ACTIVE");
        current.safe = SafeState::Clear;
        current.permission = PermissionState::Denied;
        assert_eq!(action_status(7, &current), "BLOCKED · PERMISSION_DENIED");
    }

    #[test]
    fn every_page_maps_to_a_bounded_existing_action_contract() {
        for page in 0..PAGES.len() {
            assert!(!action_label(page).is_empty());
            assert!(matches!(
                proposed_action(page),
                ProposedAction::Inspect
                    | ProposedAction::RestartCore
                    | ProposedAction::InstallModule
                    | ProposedAction::RequestApproval
                    | ProposedAction::UpdatePlatform
                    | ProposedAction::SaveSettings
            ));
        }
    }
}
