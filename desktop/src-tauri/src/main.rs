// Suppress the additional console window that Windows opens by default
// when launching a GUI app from an .exe.  Has no effect on macOS/Linux.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    note_networks_app_lib::run();
}
