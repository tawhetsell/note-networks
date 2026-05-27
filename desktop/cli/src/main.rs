//! `note-graph` — CLI for building a note-network graph from a corpus directory.
//!
//! Behavioural parity with `python tools/build_graph.py`:
//!   note-graph --corpus ../networks/aurelius
//!   note-graph --corpus ../networks/aurelius --method bm25

use anyhow::Result;
use clap::Parser;
use note_graph_core::{build, graph, BuildConfig, Method};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(
    name    = "note-graph",
    about   = "Build a note-network graph from a corpus directory",
    version,
)]
struct Args {
    /// Corpus directory (containing notes/ and data/ subdirs).
    /// Defaults to ../networks/aurelius relative to the cwd.
    #[arg(long, default_value = "networks/aurelius")]
    corpus: PathBuf,

    /// Link scoring algorithm.
    #[arg(long, value_enum, default_value_t = MethodArg::Tfidf)]
    method: MethodArg,
}

#[derive(clap::ValueEnum, Clone, Debug)]
enum MethodArg {
    Tfidf,
    Bm25,
}

impl From<MethodArg> for Method {
    fn from(m: MethodArg) -> Self {
        match m {
            MethodArg::Tfidf => Method::TfIdf,
            MethodArg::Bm25  => Method::Bm25,
        }
    }
}

fn main() -> Result<()> {
    let args   = Args::parse();
    let corpus = args.corpus.canonicalize().unwrap_or(args.corpus.clone());

    let mut cfg = BuildConfig::new(&corpus);
    cfg.method  = args.method.clone().into();

    let g = build(&cfg)?;

    let out_dir = corpus.join("data");
    let json    = out_dir.join("graph.json");
    let csv     = out_dir.join("co_occurrence.csv");
    graph::write_json(&g, &json)?;
    graph::write_csv(&g, &csv)?;

    let method_name = match args.method {
        MethodArg::Tfidf => "tfidf",
        MethodArg::Bm25  => "bm25",
    };
    println!(
        "Built graph [{method_name}]: {} nodes, {} edges",
        g.nodes.len(),
        g.edges.len()
    );
    println!("  -> {}", json.display());
    println!("  -> {}", csv.display());

    // Speaker distribution
    let mut by_spk: std::collections::BTreeMap<&str, usize> = std::collections::BTreeMap::new();
    for n in &g.nodes {
        *by_spk.entry(n.speaker.as_str()).or_insert(0) += 1;
    }
    for (spk, cnt) in by_spk {
        println!("     {spk:20}  {cnt:3} notes");
    }
    Ok(())
}
