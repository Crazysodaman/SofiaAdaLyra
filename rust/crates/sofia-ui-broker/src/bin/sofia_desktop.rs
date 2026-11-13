//! Rust personal presentation; cognition and personal state stay in Python.
// Shared desktop module also contains the separately launched Control Center.
#[path = "../personal_desktop.rs"]
mod personal_desktop;
#[allow(dead_code)]
#[path = "../platform_gui.rs"]
mod platform_gui;
fn main() -> eframe::Result {
    personal_desktop::run()
}
