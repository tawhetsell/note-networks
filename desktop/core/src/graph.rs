//! Graph builder — port of the Python `build()` function.
//!
//! Reads markdown notes from a corpus directory, computes per-note TF-IDF
//! (or BM25) scores, keeps the top-K distinctive terms per note, and draws
//! an edge between any two notes that share ≥ `min_shared` distinctive terms.

use anyhow::{Context, Result};
use serde::Serialize;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

use crate::frontmatter::{self, Frontmatter, Value};
use crate::tokens::tokenize;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Method {
    TfIdf,
    Bm25,
}

#[derive(Debug, Clone)]
pub struct BuildConfig {
    pub corpus_dir: PathBuf,
    pub method:     Method,
    pub min_shared: usize,
    pub top_k:      usize,
}

impl BuildConfig {
    /// Defaults that mirror build_graph.py constants.
    pub fn new(corpus_dir: impl Into<PathBuf>) -> Self {
        Self {
            corpus_dir: corpus_dir.into(),
            method:     Method::TfIdf,
            min_shared: 1,
            top_k:      25,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct Node {
    pub id:         String,
    pub label:      String,
    pub word_count: usize,
    pub degree:     usize,
    pub speaker:    String,
    pub tags:       Vec<String>,
    pub source:     String,
}

#[derive(Debug, Serialize)]
pub struct Edge {
    pub from:   String,
    pub to:     String,
    pub weight: usize,
    pub terms:  Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct Graph {
    pub nodes: Vec<Node>,
    pub edges: Vec<Edge>,
}

/// Build the graph for the given corpus directory.
/// Writes nothing — the caller decides where to put the output.
pub fn build(config: &BuildConfig) -> Result<Graph> {
    let notes_dir = config.corpus_dir.join("notes");

    // 1. Discover note files (.md/.txt/.rtf, recursive)
    let files: Vec<PathBuf> = WalkDir::new(&notes_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .map(|e| e.into_path())
        .filter(|p| matches!(
            p.extension().and_then(|s| s.to_str()).map(str::to_ascii_lowercase).as_deref(),
            Some("md") | Some("txt") | Some("rtf")
        ))
        .collect();

    // Stable ordering — BTreeMap keeps insertion ordered by key (file stem)
    let mut raw_texts:   BTreeMap<String, String>      = BTreeMap::new();
    let mut frontmatter: BTreeMap<String, Frontmatter> = BTreeMap::new();
    let mut docs:        BTreeMap<String, Vec<String>> = BTreeMap::new();

    for p in &files {
        let Some(stem) = p.file_stem().and_then(|s| s.to_str()) else { continue };
        let text = std::fs::read_to_string(p)
            .with_context(|| format!("reading {}", p.display()))?;
        let toks = tokenize(&text);
        let fm   = frontmatter::parse(&text);
        raw_texts.insert(stem.to_string(), text);
        frontmatter.insert(stem.to_string(), fm);
        docs.insert(stem.to_string(), toks);
    }

    // Empty corpus → valid empty graph (matches the Python early-return path)
    if docs.is_empty() {
        return Ok(Graph { nodes: vec![], edges: vec![] });
    }

    // 2. Document frequency: how many notes each term appears in
    let n_docs = docs.len() as f64;
    let mut df: HashMap<&str, usize> = HashMap::new();
    for toks in docs.values() {
        let unique: HashSet<&str> = toks.iter().map(|s| s.as_str()).collect();
        for t in unique {
            *df.entry(t).or_insert(0) += 1;
        }
    }

    // 3. Per-document length stats (for BM25)
    let doc_lens: HashMap<&str, usize> = docs
        .iter()
        .map(|(name, toks)| (name.as_str(), toks.len()))
        .collect();
    let avg_doc_len = if doc_lens.is_empty() {
        1.0
    } else {
        doc_lens.values().sum::<usize>() as f64 / doc_lens.len() as f64
    };

    // 4. Top-K distinctive terms per note
    let mut distinctive: BTreeMap<String, HashSet<String>> = BTreeMap::new();
    for (name, toks) in &docs {
        let mut tf: HashMap<&str, usize> = HashMap::new();
        for t in toks {
            *tf.entry(t.as_str()).or_insert(0) += 1;
        }
        let doc_len = doc_lens[name.as_str()];
        let mut ranked: Vec<(&str, f64)> = tf
            .iter()
            .map(|(term, &count)| {
                let df_t = df.get(term).copied().unwrap_or(1);
                let score = score_term(config.method, count, df_t, n_docs, doc_len, avg_doc_len);
                (*term, score)
            })
            .collect();
        // Highest score first; tie-break alphabetically for determinism
        ranked.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.0.cmp(b.0))
        });
        let top: HashSet<String> = ranked
            .into_iter()
            .take(config.top_k)
            .map(|(t, _)| t.to_string())
            .collect();
        distinctive.insert(name.clone(), top);
    }

    // 5. Edges — pairs sharing ≥ min_shared distinctive terms
    let names: Vec<&String> = docs.keys().collect();
    let mut edges: Vec<Edge> = Vec::new();
    for i in 0..names.len() {
        for j in (i + 1)..names.len() {
            let a = names[i];
            let b = names[j];
            let shared: Vec<String> = distinctive[a]
                .intersection(&distinctive[b])
                .cloned()
                .collect();
            if shared.len() >= config.min_shared {
                let mut shared = shared;
                shared.sort();
                edges.push(Edge {
                    from:   a.clone(),
                    to:     b.clone(),
                    weight: shared.len(),
                    terms:  shared,
                });
            }
        }
    }

    // 6. Degree centrality
    let mut degree: HashMap<&str, usize> = HashMap::new();
    for e in &edges {
        *degree.entry(e.from.as_str()).or_insert(0) += 1;
        *degree.entry(e.to.as_str()).or_insert(0)   += 1;
    }

    // 7. Nodes (with frontmatter metadata)
    let nodes: Vec<Node> = names
        .iter()
        .map(|name| {
            let name_s = name.as_str();
            let fm     = &frontmatter[*name];
            let wc     = fm
                .get("word_count")
                .and_then(Value::as_usize)
                .unwrap_or_else(|| docs[name_s].len());
            let speaker = fm
                .get("speaker")
                .and_then(Value::as_str)
                .unwrap_or("UNKNOWN")
                .to_string();
            let tags = fm
                .get("tags")
                .and_then(Value::as_list)
                .map(|v| v.to_vec())
                .unwrap_or_default();
            let source = fm
                .get("source")
                .or_else(|| fm.get("episode"))
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            Node {
                id:         name_s.to_string(),
                label:      name_s.to_string(),
                word_count: wc,
                degree:     degree.get(name_s).copied().unwrap_or(0),
                speaker,
                tags,
                source,
            }
        })
        .collect();

    Ok(Graph { nodes, edges })
}

fn score_term(
    method:      Method,
    tf:          usize,
    df:          usize,
    n_docs:      f64,
    doc_len:     usize,
    avg_doc_len: f64,
) -> f64 {
    let tf = tf as f64;
    let df = df as f64;
    match method {
        Method::TfIdf => {
            // Mirrors the Python: tf * log(N / (1 + df))
            tf * ((n_docs / (1.0 + df)).ln())
        }
        Method::Bm25 => {
            // Okapi BM25: k1=1.5, b=0.75 (same as Python)
            let k1 = 1.5;
            let b  = 0.75;
            let idf = ((n_docs - df + 0.5) / (df + 0.5) + 1.0).ln();
            let tf_norm = (tf * (k1 + 1.0))
                / (tf + k1 * (1.0 - b + b * doc_len as f64 / avg_doc_len));
            idf * tf_norm
        }
    }
}

/// Write a graph as JSON to the given path.  Matches the Python `json.dumps(..., indent=2)`.
pub fn write_json(graph: &Graph, path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let json = serde_json::to_string_pretty(graph)?;
    std::fs::write(path, json)?;
    Ok(())
}

/// Write the adjacency matrix CSV (mirrors the Python output).
pub fn write_csv(graph: &Graph, path: &Path) -> Result<()> {
    use std::fmt::Write;

    let names: Vec<&str> = graph.nodes.iter().map(|n| n.id.as_str()).collect();
    let weights: HashMap<(&str, &str), usize> = graph
        .edges
        .iter()
        .map(|e| ((e.from.as_str(), e.to.as_str()), e.weight))
        .collect();

    let mut out = String::new();
    // Header row
    out.push(',');
    out.push_str(&names.join(","));
    out.push('\n');
    // Data rows
    for a in &names {
        out.push_str(a);
        for b in &names {
            out.push(',');
            let w = weights
                .get(&(*a, *b))
                .or_else(|| weights.get(&(*b, *a)))
                .copied()
                .unwrap_or(0);
            write!(out, "{w}").ok();
        }
        out.push('\n');
    }
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, out)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn write_note(dir: &Path, name: &str, body: &str) {
        std::fs::create_dir_all(dir).unwrap();
        std::fs::write(dir.join(format!("{name}.md")), body).unwrap();
    }

    #[test]
    fn empty_corpus_returns_empty_graph() {
        let tmp = tempdir().unwrap();
        std::fs::create_dir_all(tmp.path().join("notes")).unwrap();
        let g = build(&BuildConfig::new(tmp.path())).unwrap();
        assert_eq!(g.nodes.len(), 0);
        assert_eq!(g.edges.len(), 0);
    }

    #[test]
    fn two_overlapping_notes_form_an_edge() {
        let tmp = tempdir().unwrap();
        let notes = tmp.path().join("notes");
        write_note(
            &notes,
            "a",
            "---\nspeaker: ME\ntags: [x]\n---\n\nphilosophy ethics virtue wisdom courage temperance justice",
        );
        write_note(
            &notes,
            "b",
            "---\nspeaker: ME\ntags: [x]\n---\n\nphilosophy ethics happiness flourishing eudaimonia virtue",
        );
        let g = build(&BuildConfig::new(tmp.path())).unwrap();
        assert_eq!(g.nodes.len(), 2);
        assert!(g.edges.len() >= 1, "expected at least one shared-term edge");
        assert!(g.edges[0].terms.iter().any(|t| t == "philosophy" || t == "virtue"));
    }
}
