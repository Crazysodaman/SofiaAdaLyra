//! Cross-platform Rust Control Center; canonical authority remains in Platform.
#[path = "../platform_gui.rs"]
mod platform_gui;
fn main() -> eframe::Result {
    platform_gui::run()
}
