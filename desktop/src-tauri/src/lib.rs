//! Tauri shell for Note Networks.
//!
//! All graph + note logic lives in `note-graph-core`.  This file just
//! exposes IPC commands the frontend invokes via `window.__TAURI__.core.invoke`.

use std::path::{Path, PathBuf};

use note_graph_core::{
    build, create_note as core_create, delete_note as core_delete,
    read_note_raw as core_read, update_note as core_update,
    BuildConfig, Graph,
};

// ---- HELPERS ----

/// The folder every corpus must live in: `<repo>/networks`.
/// The frontend hard-codes `../../networks/aurelius` until the Phase 6 network
/// picker exists; refusing anything outside `networks/` means injected script
/// can't aim the note commands at arbitrary folders.  (Phase 6 will need to
/// allow folders the user picks in the dialog.)
fn networks_root() -> Result<PathBuf, String> {
    // env!("CARGO_MANIFEST_DIR"): compile-time absolute path of desktop/src-tauri.
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../networks")
        .canonicalize()
        .map_err(|e| format!("networks folder not found: {e}"))
}

/// Validate a corpus path supplied by the frontend.
fn corpus_dir(corpus: &str) -> Result<PathBuf, String> {
    // canonicalize(): absolute path with `..` and symlinks resolved (must exist).
    let resolved = Path::new(corpus)
        .canonicalize()
        .map_err(|e| format!("corpus not found: {corpus}: {e}"))?;
    if !resolved.is_dir() || !resolved.starts_with(networks_root()?) {
        return Err(format!("corpus must be a folder inside networks/: {corpus}"));
    }
    Ok(PathBuf::from(corpus))
}

/// Resolve `corpus_dir/notes` from a corpus path supplied by the frontend.
fn notes_dir(corpus: &str) -> Result<PathBuf, String> {
    Ok(corpus_dir(corpus)?.join("notes"))
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
    build(&BuildConfig::new(corpus_dir(&corpus)?)).map_err(|e| e.to_string())
}

/// Read a note's raw file content (frontmatter + body).
#[tauri::command]
fn get_note(corpus: String, stem: String) -> Result<String, String> {
    core_read(&notes_dir(&corpus)?, &stem).map_err(|e| e.to_string())
}

/// Update an existing note's tags + body.
#[tauri::command]
fn update_note(
    corpus: String,
    stem:   String,
    tags:   Option<Vec<String>>,
    body:   String,
) -> Result<(), String> {
    core_update(&notes_dir(&corpus)?, &stem, tags, &body).map_err(|e| e.to_string())
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
        &notes_dir(&corpus)?,
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
    core_delete(&notes_dir(&corpus)?, &stem).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    // `cargo test` runs with the working dir set to desktop/src-tauri, the same
    // dir `tauri dev` uses, so the frontend's relative CORPUS path resolves here too.
    #[test]
    fn corpus_must_be_inside_networks() {
        assert!(corpus_dir("../../networks/aurelius").is_ok());
        for bad in ["../..", "../../tools", "../../networks/../tools", "does-not-exist"] {
            assert!(corpus_dir(bad).is_err(), "should reject {bad:?}");
        }
        assert!(notes_dir(std::env::temp_dir().to_str().unwrap()).is_err());
    }
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
