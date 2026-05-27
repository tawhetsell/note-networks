//! Portable graph-building core for note-networks.
//!
//! Mirrors the behaviour of `tools/build_graph.py` (the Python reference
//! implementation) but written in pure Rust with no I/O assumptions baked
//! into the math.  Designed to be reused by:
//!   - the CLI binary (replaces `python tools/build_graph.py`)
//!   - the future Tauri desktop app
//!   - any future mobile build (no UI dependencies)

pub mod frontmatter;
pub mod tokens;
pub mod graph;
pub mod notes;

pub use graph::{build, BuildConfig, Edge, Graph, Method, Node};
pub use notes::{create_note, delete_note, read_note_raw, update_note};
