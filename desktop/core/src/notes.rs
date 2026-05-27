//! Note CRUD operations — port of the read/write/delete helpers in watch.py.
//!
//! These functions work against a `notes_dir` rather than a full corpus dir,
//! so the same logic is reusable from CLI, Tauri, or future mobile contexts.

use anyhow::{anyhow, Context, Result};
use std::path::{Path, PathBuf};

use crate::frontmatter::{self, Frontmatter, Value};

const NOTE_EXTS: &[&str] = &["md", "txt", "rtf"];

/// Locate a note by its stem (filename without extension).
/// Searches the top level first, then recursively.
pub fn find_note(notes_dir: &Path, stem: &str) -> Option<PathBuf> {
    for ext in NOTE_EXTS {
        let p = notes_dir.join(format!("{stem}.{ext}"));
        if p.is_file() {
            return Some(p);
        }
    }
    walkdir::WalkDir::new(notes_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .find(|e| {
            e.file_type().is_file()
                && e.path().file_stem().and_then(|s| s.to_str()) == Some(stem)
                && e.path()
                    .extension()
                    .and_then(|s| s.to_str())
                    .map(|s| NOTE_EXTS.contains(&s.to_ascii_lowercase().as_str()))
                    .unwrap_or(false)
        })
        .map(|e| e.into_path())
}

/// Return the raw file contents (frontmatter + body), or an error if not found.
pub fn read_note_raw(notes_dir: &Path, stem: &str) -> Result<String> {
    let p = find_note(notes_dir, stem).ok_or_else(|| anyhow!("note not found: {stem}"))?;
    std::fs::read_to_string(&p).with_context(|| format!("reading {}", p.display()))
}

/// Update an existing note's tags + body, preserving any other frontmatter fields.
/// `tags` is `None` if the caller doesn't want to change the tags.
pub fn update_note(
    notes_dir: &Path,
    stem:      &str,
    tags:      Option<Vec<String>>,
    body:      &str,
) -> Result<()> {
    let p = find_note(notes_dir, stem)
        .ok_or_else(|| anyhow!("note not found: {stem}"))?;
    let raw = std::fs::read_to_string(&p)?;
    let mut fm = frontmatter::parse(&raw);
    if let Some(t) = tags {
        fm.insert("tags".into(), Value::List(t));
    }
    fm.insert(
        "word_count".into(),
        Value::Str(body.split_whitespace().count().to_string()),
    );
    let new_text = format!("{}\n{body}", serialize_frontmatter(&fm));
    std::fs::write(&p, new_text)?;
    Ok(())
}

/// Create a new note.  Returns an error if a note with this id already exists.
pub fn create_note(
    notes_dir: &Path,
    id:        &str,
    speaker:   &str,
    source:    &str,
    tags:      Vec<String>,
    body:      &str,
) -> Result<PathBuf> {
    if find_note(notes_dir, id).is_some() {
        return Err(anyhow!("note already exists: {id}"));
    }
    std::fs::create_dir_all(notes_dir)?;
    let p = notes_dir.join(format!("{id}.md"));

    let mut fm = Frontmatter::new();
    fm.insert("id".into(),         Value::Str(id.to_string()));
    fm.insert("speaker".into(),    Value::Str(speaker.to_string()));
    fm.insert("source".into(),     Value::Str(source.to_string()));
    fm.insert("tags".into(),       Value::List(tags));
    fm.insert(
        "word_count".into(),
        Value::Str(body.split_whitespace().count().to_string()),
    );

    let text = format!("{}\n{body}", serialize_frontmatter(&fm));
    std::fs::write(&p, text)?;
    Ok(p)
}

/// Delete a note by stem.
pub fn delete_note(notes_dir: &Path, stem: &str) -> Result<()> {
    let p = find_note(notes_dir, stem).ok_or_else(|| anyhow!("note not found: {stem}"))?;
    std::fs::remove_file(&p)?;
    Ok(())
}

/// Serialize a frontmatter map back into a YAML block.  Matches the Python format.
fn serialize_frontmatter(fm: &Frontmatter) -> String {
    // Stable, human-friendly ordering for known fields; everything else after, alphabetically.
    let order = ["id", "speaker", "source", "tags", "word_count"];
    let mut keys: Vec<&String> = fm.keys().collect();
    keys.sort_by(|a, b| {
        let ai = order.iter().position(|k| k == a);
        let bi = order.iter().position(|k| k == b);
        match (ai, bi) {
            (Some(x), Some(y)) => x.cmp(&y),
            (Some(_), None)    => std::cmp::Ordering::Less,
            (None, Some(_))    => std::cmp::Ordering::Greater,
            (None, None)       => a.cmp(b),
        }
    });

    let mut out = String::from("---\n");
    for k in keys {
        match &fm[k] {
            Value::Str(s)  => out.push_str(&format!("{k}: {s}\n")),
            Value::List(l) => out.push_str(&format!("{k}: [{}]\n", l.join(", "))),
        }
    }
    out.push_str("---\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn create_then_read_round_trip() {
        let tmp   = tempdir().unwrap();
        let notes = tmp.path().join("notes");
        std::fs::create_dir_all(&notes).unwrap();

        create_note(
            &notes,
            "test-note",
            "ME",
            "Source",
            vec!["a".into(), "b".into()],
            "Body of the note.",
        )
        .unwrap();

        let raw = read_note_raw(&notes, "test-note").unwrap();
        assert!(raw.contains("id: test-note"));
        assert!(raw.contains("tags: [a, b]"));
        assert!(raw.contains("Body of the note."));
    }

    #[test]
    fn update_replaces_tags_and_body_but_preserves_id() {
        let tmp   = tempdir().unwrap();
        let notes = tmp.path().join("notes");
        std::fs::create_dir_all(&notes).unwrap();

        create_note(&notes, "n", "ME", "S", vec!["old".into()], "old body").unwrap();
        update_note(&notes, "n", Some(vec!["new".into()]), "new body").unwrap();

        let raw = read_note_raw(&notes, "n").unwrap();
        assert!(raw.contains("id: n"));
        assert!(raw.contains("tags: [new]"));
        assert!(raw.contains("new body"));
        assert!(!raw.contains("old body"));
    }

    #[test]
    fn delete_removes_file() {
        let tmp   = tempdir().unwrap();
        let notes = tmp.path().join("notes");
        std::fs::create_dir_all(&notes).unwrap();

        create_note(&notes, "doomed", "ME", "S", vec![], "bye").unwrap();
        assert!(find_note(&notes, "doomed").is_some());
        delete_note(&notes, "doomed").unwrap();
        assert!(find_note(&notes, "doomed").is_none());
    }
}
