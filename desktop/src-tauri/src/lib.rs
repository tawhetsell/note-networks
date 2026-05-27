//! Tauri shell for Note Networks.
//!
//! All graph + note logic lives in `note-graph-core`.  This file just
//! exposes IPC commands the frontend invokes via `window.__TAURI__.core.invoke`.

use std::path::PathBuf;

use note_graph_core::{
    build, create_note as core_create, delete_note as core_delete,
    read_note_raw as core_read, update_note as core_update,
    BuildConfig, Graph,
};

// ---- HELPERS ----

/// Resolve `corpus_dir/notes` from a corpus path supplied by the frontend.
fn notes_dir(corpus: &str) -> PathBuf {
    PathBuf::from(corpus).join("notes")
}

// ---- IPC COMMANDS ----

/// Sanity-check the IPC channel.  The frontend uses this to confirm
/// it's running inside Tauri rather than a plain browser.
#[tauri::command]
fn ping() -> &'static str {
    "pong"
}

/// Build and return the graph for `corpus`.  Same shape as `data/graph.json`.
#[tauri::command]
fn get_graph(corpus: String) -> Result<Graph, String> {
    build(&BuildConfig::new(PathBuf::from(&corpus))).map_err(|e| e.to_string())
}

/// Read a note's raw file content (frontmatter + body).
#[tauri::command]
fn get_note(corpus: String, stem: String) -> Result<String, String> {
    core_read(&notes_dir(&corpus), &stem).map_err(|e| e.to_string())
}

/// Update an existing note's tags + body.
#[tauri::command]
fn update_note(
    corpus: String,
    stem:   String,
    tags:   Option<Vec<String>>,
    body:   String,
) -> Result<(), String> {
    core_update(&notes_dir(&corpus), &stem, tags, &body).map_err(|e| e.to_string())
}

/// Create a new note.  Returns the path to the created file.
#[tauri::command]
fn create_note(
    corpus:  String,
    id:      String,
    speaker: Option<String>,
    source:  Option<String>,
    tags:    Option<Vec<String>>,
    body:    Option<String>,
) -> Result<String, String> {
    let p = core_create(
        &notes_dir(&corpus),
        &id,
        speaker.as_deref().unwrap_or("ME"),
        source.as_deref().unwrap_or(""),
        tags.unwrap_or_default(),
        body.as_deref().unwrap_or(""),
    )
    .map_err(|e| e.to_string())?;
    Ok(p.display().to_string())
}

/// Delete a note by stem.
#[tauri::command]
fn delete_note(corpus: String, stem: String) -> Result<(), String> {
    core_delete(&notes_dir(&corpus), &stem).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            ping,
            get_graph,
            get_note,
            update_note,
            create_note,
            delete_note,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
