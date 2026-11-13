//! Personal desktop presentation; Python retains cognition and personal state.
//! No personal database, approval signer, tool executor or canonical writer.
use crate::platform_gui::{apply_theme, DesktopStatus};
use eframe::egui;
use sofia_ui_broker::control_center_session::{DisplayReadSource, OfflineReader};
use std::time::Duration;

const MAX_DRAFT_CHARS: usize = 16_384;
const TABS: &[&str] = &[
    "Conversation",
    "History",
    "Core Link",
    "Voice",
    "Avatar / overlays",
    "Notifications",
    "Settings",
    "Approvals / STOP",
];

pub struct PersonalApp<S: DisplayReadSource> {
    status: DesktopStatus<S>,
    tab: usize,
    draft: String,
    large_text: bool,
    confirm_close: bool,
    close_requested: bool,
}
impl<S: DisplayReadSource> PersonalApp<S> {
    pub fn new(source: S) -> Self {
        Self {
            status: DesktopStatus::new(source),
            tab: 0,
            draft: String::new(),
            large_text: false,
            confirm_close: true,
            close_requested: false,
        }
    }
    fn body(&mut self, ui: &mut egui::Ui) {
        ui.heading(TABS[self.tab]);
        ui.separator();
        match self.tab {
            0 => {
                ui.label("No authenticated conversation channel is connected.");
                ui.label("Drafts stay in this window's memory. They are never sent, persisted or passed to a model.");
                ui.add(
                    egui::TextEdit::multiline(&mut self.draft)
                        .char_limit(MAX_DRAFT_CHARS)
                        .desired_rows(10)
                        .desired_width(f32::INFINITY)
                        .hint_text("Unsent local draft"),
                );
                ui.horizontal(|ui| {
                    ui.add_enabled(false, egui::Button::new("Send to Core — unavailable"));
                    if ui.button("Clear unsent draft").clicked() {
                        self.draft.clear();
                    }
                    ui.label(format!(
                        "{} / {MAX_DRAFT_CHARS} characters",
                        self.draft.chars().count()
                    ));
                });
                ui.label("A management status observation cannot authorize conversation, tools or personal state access.");
            }
            1 => {
                ui.label("History unavailable: no authenticated Core conversation-history contract is connected.");
                ui.label("This window does not open a Core database or infer that your history is empty.");
            }
            2 => {
                self.status.draw(ui);
                ui.label(
                    "Platform management observation is separate from Core Link authentication.",
                );
                ui.label("Core identity, current binding, generation, model availability and Core health: NOT VERIFIED.");
                ui.add_enabled(
                    false,
                    egui::Button::new("Connect / select Core — unavailable"),
                );
            }
            3 => {
                ui.label("Voice input / output unavailable until an authorized voice capability is advertised by the current Core.");
                ui.add_enabled(false, egui::Button::new("Start microphone"));
                ui.add_enabled(false, egui::Button::new("Play voice"));
                ui.label("No microphone, audio device or provider is opened.");
            }
            4 => {
                ui.label("Renderer and overlay availability: NOT VERIFIED.");
                ui.add_enabled(false, egui::Button::new("Show avatar"));
                ui.add_enabled(false, egui::Button::new("Enable overlay"));
                ui.label("A renderer must use current authenticated broker visibility, quota, session and DND authority.");
            }
            5 => {
                ui.label("No authenticated broker notification observation.");
                ui.label("Notification receipts, tray integration and session/DND policy must come from the Rust broker; a desktop launch does not create notification permission.");
            }
            6 => {
                ui.checkbox(&mut self.large_text, "Larger text (this window only)");
                ui.checkbox(&mut self.confirm_close, "Confirm closing an unsent draft");
                ui.label("Appearance settings are ephemeral; Core personality, provider and personal settings require canonical authenticated settings IPC.");
            }
            _ => {
                ui.label("Protected lifecycle actions require current exact owner approval at the canonical Platform service.");
                self.status.draw(ui);
                ui.add_enabled(false, egui::Button::new("Request approval — unavailable"));
                ui.add_enabled(
                    false,
                    egui::Button::new("STOP Core / Platform — unavailable"),
                );
                ui.label("Closing this window only closes presentation. It does not stop a Core or the Platform service.");
            }
        }
    }
}
impl<S: DisplayReadSource> eframe::App for PersonalApp<S> {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        context.set_zoom_factor(if self.large_text { 1.25 } else { 1.0 });
        if context.input(|input| input.viewport().close_requested())
            && self.confirm_close
            && !self.draft.is_empty()
        {
            context.send_viewport_cmd(egui::ViewportCommand::CancelClose);
            self.close_requested = true;
        }
        egui::TopBottomPanel::top("personal-heading").show(context, |ui| {
            ui.horizontal(|ui| {
                ui.heading("Sofía · Personal Desktop");
                if ui.button("Refresh / reconnect management").clicked() {
                    self.status.refresh();
                }
            });
            ui.label("Rust presentation · Python Core cognition · Core identity not yet verified");
        });
        egui::SidePanel::left("personal-navigation").show(context, |ui| {
            for (index, name) in TABS.iter().enumerate() {
                ui.selectable_value(&mut self.tab, index, *name);
            }
        });
        egui::CentralPanel::default().show(context, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| self.body(ui));
        });
        if self.close_requested {
            egui::Window::new("Discard unsent draft?").collapsible(false).resizable(false).show(context,|ui| {
                ui.label("Your unsent local draft will be discarded. Core and Platform services keep running.");
                if ui.button("Discard draft and close window").clicked() {
                    self.draft.clear(); self.confirm_close=false;
                    context.send_viewport_cmd(egui::ViewportCommand::Close);
                }
                if ui.button("Keep editing").clicked() { self.close_requested=false; }
            });
        }
        context.request_repaint_after(Duration::from_secs(1));
    }
}
pub fn run() -> eframe::Result {
    run_with_source(OfflineReader)
}

/// Management observation alone never authenticates a personal Core channel.
pub fn run_with_source<S: DisplayReadSource + 'static>(source: S) -> eframe::Result {
    eframe::run_native(
        "Sofía Personal Desktop",
        eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default()
                .with_inner_size([1080.0, 740.0])
                .with_min_inner_size([640.0, 480.0]),
            ..Default::default()
        },
        Box::new(move |creation| {
            apply_theme(&creation.egui_ctx);
            Ok(Box::new(PersonalApp::new(source)))
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn personal_pages_render_core_free_with_no_personal_state() {
        let context = egui::Context::default();
        let mut app = PersonalApp::new(OfflineReader);
        for tab in 0..TABS.len() {
            app.tab = tab;
            let _ = context.run(egui::RawInput::default(), |ctx| {
                egui::CentralPanel::default().show(ctx, |ui| app.body(ui));
            });
        }
        assert!(app.draft.is_empty());
        assert!(app.status.diagnostic().contains("Management: UNAVAILABLE"));
    }
    #[test]
    fn composing_draft_does_not_create_chat_history_or_authority() {
        let mut app = PersonalApp::new(OfflineReader);
        app.draft = "synthetic unsent text".into();
        assert!(app.status.diagnostic().contains("Permission: UNKNOWN"));
        assert!(app.status.diagnostic().contains("Platform: NOT VERIFIED"));
        assert_eq!(app.draft, "synthetic unsent text");
    }
}
