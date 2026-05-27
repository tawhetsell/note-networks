#!/usr/bin/env python3
"""
Build a TF-IDF co-occurrence graph from notes/ and write data/graph.json
and data/co_occurrence.csv.

Refactored from note-networks.py:
  - Paths resolved from repo root (no ~/Proton Drive hard-code)
  - YAML frontmatter stripped before tokenizing
  - Extended stopwords (dialogue noise + common function words)
  - Node metadata pulled from frontmatter: speaker, tags, word_count
  - Edge metadata includes shared terms (kept from original)
  - No inline HTML generation — viz/graph.html is authored separately
  - Configurable constants at top of file

Usage:
  python tools/build_graph.py              # TF-IDF (default)
  python tools/build_graph.py --method bm25  # BM25 (better term-freq saturation)
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from math import log
from pathlib import Path

# ---- CONFIG (tune these to taste) ----
REPO = Path(__file__).resolve().parent.parent   # repo root via script location

MIN_SHARED = 1       # minimum shared distinctive terms to draw an edge
TOP_K      = 25      # keep top-K TF-IDF terms per note

# Core English stopwords
_STOP_CORE = (
    "a an the and or but if then so of in on at by for with to from as "
    "is are was were be been being have has had do does did this that "
    "these those i you he she it we they them my your his her its our "
    "their what which who when where why how not no yes into about more "
    "also such one two three all any some can will would could should "
    "may might must shall s t"
)

# Extra noise words from dialogue and informal prose
_STOP_EXTRA = (
    "yeah okay right like just well gonna want know said say get got "
    "go come back see think look let now even still only really quite "
    "very much more most least less than between among upon whether "
    "though although however therefore thus hence perhaps indeed "
    "shall must ought need seem become made make take give keep "
    "us them who whom whose mr mrs dr sir"
)

STOP = set((_STOP_CORE + " " + _STOP_EXTRA).split())

# Words added on top of the base set — edit here to tune without touching STOP
STOPWORDS_EXTRA: set[str] = set()


# ---- FRONTMATTER UTILS ----

# re.DOTALL makes '.' match newlines, so '.*?' spans the YAML block.
_FM_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)

def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- block) before tokenizing."""
    return _FM_RE.sub("", text, count=1)

def parse_frontmatter(text: str) -> dict:
    """
    Extract key: value pairs from a YAML frontmatter block.
    Handles: string, quoted string, inline list ([a, b, c]),
    multi-line list (- item per line), and int.
    Not a full YAML parser — sufficient for our schema and Obsidian-style notes.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}
    block = m.group(0)[4:-4]   # strip leading '---\n' and trailing '\n---\n'
    result = {}
    current_key = None   # tracks the last key that opened a multi-line list
    for line in block.splitlines():
        stripped = line.strip()
        # Multi-line list item (e.g. Obsidian writes tags as "  - tag")
        if stripped.startswith("- ") and current_key is not None:
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if ":" not in line:
            current_key = None
            continue
        key, _, val = line.partition(":")
        key  = key.strip()
        val  = val.strip().strip('"').strip("'")
        current_key = None
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            result[key] = [v.strip().strip('"').strip("'")
                           for v in inner.split(",") if v.strip()]
        elif val.isdigit():
            result[key] = int(val)
        elif val == "":
            result[key] = []   # empty value — expect multi-line list items next
            current_key = key
        else:
            result[key] = val
    return result


# ---- FILE READING ----

def read_file(p: Path) -> str:
    """RTF -> txt via macOS textutil; md/txt read directly."""
    if p.suffix.lower() == ".rtf":
        # textutil: built-in macOS converter. -stdout writes to stdout.
        # Falls back gracefully on non-macOS (e.g. this build machine).
        try:
            r = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", str(p)],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                return r.stdout
        except FileNotFoundError:
            pass   # textutil not available (non-macOS); skip RTF gracefully
        print(f"  [skip] RTF support requires macOS textutil: {p.name}", file=sys.stderr)
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


# ---- TOKENIZATION ----

ALL_STOP = STOP | STOPWORDS_EXTRA

def tokens(text: str) -> list[str]:
    """Lowercase, strip punctuation, drop stopwords + short/numeric tokens."""
    text = strip_frontmatter(text)
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [
        t for t in text.split()
        if t not in ALL_STOP and len(t) > 3 and not t.isdigit()
    ]


# ---- BUILD ----

def build(method: str = "tfidf", corpus_dir: Path | None = None):
    # corpus_dir: folder containing notes/ and data/ subdirectories.
    # Defaults to aurelius/ inside the repo when not specified.
    corpus_dir = (corpus_dir or REPO / "networks" / "aurelius").resolve()
    notes_dir  = corpus_dir / "notes"
    output_dir = corpus_dir / "data"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect files (rglob = recursive glob across all subdirectories)
    files = sorted(
        p for p in notes_dir.rglob("*")
        if p.suffix.lower() in {".md", ".txt", ".rtf"}
    )
    if not files:
        # Empty corpus — write a valid empty graph so the viewer still loads
        empty = {"nodes": [], "edges": []}
        (output_dir / "graph.json").write_text(json.dumps(empty), encoding="utf-8")
        print(f"Built graph [{method}]: 0 nodes, 0 edges (no notes yet)")
        return

    # Read text and parse frontmatter per file
    raw_texts = {p.stem: read_file(p) for p in files}
    frontmatter = {p.stem: parse_frontmatter(raw_texts[p.stem]) for p in files}
    docs = {p.stem: tokens(raw_texts[p.stem]) for p in files}

    N  = len(docs)
    # Document frequency: how many notes each term appears in
    df = Counter()
    for toks in docs.values():
        df.update(set(toks))

    # Scoring: TF-IDF or BM25.
    # BM25 adds term-frequency saturation (k1) and document-length normalisation (b),
    # preventing long notes from dominating just because a term appears many times.
    # k1=1.5, b=0.75 are standard defaults from the Okapi BM25 paper.
    doc_lens   = {name: len(toks) for name, toks in docs.items()}
    avg_doc_len = sum(doc_lens.values()) / len(doc_lens) if doc_lens else 1

    def score_term(tf: int, term: str, doc_len: int) -> float:
        if method == "bm25":
            k1, b = 1.5, 0.75
            # BM25 IDF (Robertson–Spärck Jones variant, stays positive)
            idf = log((N - df[term] + 0.5) / (df[term] + 0.5) + 1)
            # Saturated TF with length normalisation
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
            return idf * tf_norm
        # Default: classic TF-IDF
        return tf * log(N / (1 + df[term]))

    # Top-K distinctive terms per note
    distinctive: dict[str, set[str]] = {}
    for name, toks in docs.items():
        tf     = Counter(toks)
        ranked = sorted(tf.items(), key=lambda x: -score_term(x[1], x[0], doc_lens[name]))
        distinctive[name] = {t for t, _ in ranked[:TOP_K]}

    # Edges: pairs sharing MIN_SHARED+ distinctive terms
    names = list(docs.keys())
    edges = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = distinctive[a] & distinctive[b]
            if len(shared) >= MIN_SHARED:
                edges.append({
                    "from":   a,
                    "to":     b,
                    "weight": len(shared),
                    "terms":  sorted(shared),    # shared terms for edge tooltip
                })

    # Degree centrality: count how many edges each node participates in
    degree = Counter()
    for e in edges:
        degree[e["from"]] += 1
        degree[e["to"]]   += 1

    # Nodes: include frontmatter metadata for viz
    nodes = []
    for name in names:
        fm = frontmatter.get(name, {})
        nodes.append({
            "id":         name,
            "label":      name,
            "word_count": fm.get("word_count", len(docs[name])),
            "degree":     degree[name],   # edges this node participates in; drives node size
            "speaker":    fm.get("speaker", "UNKNOWN"),
            "tags":       fm.get("tags", []),
            "source":     fm.get("source", fm.get("episode", "")),
        })

    graph = {"nodes": nodes, "edges": edges}

    # ---- OUTPUTS ----
    json_out = output_dir / "graph.json"
    json_out.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    csv_out = output_dir / "co_occurrence.csv"
    weights = {(e["from"], e["to"]): e["weight"] for e in edges}
    with csv_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] + names)
        for a in names:
            row = [a] + [
                weights.get((a, b), weights.get((b, a), 0))
                for b in names
            ]
            w.writerow(row)

    print(f"Built graph [{method}]: {len(nodes)} nodes, {len(edges)} edges")
    print(f"  -> {json_out}")
    print(f"  -> {csv_out}")
    # Speaker distribution
    by_spk = Counter(n["speaker"] for n in nodes)
    for spk, cnt in sorted(by_spk.items()):
        print(f"     {spk:20s} {cnt:3d} notes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build note graph from a corpus directory.")
    parser.add_argument(
        "--method", choices=["tfidf", "bm25"], default="tfidf",
        help="Link scoring algorithm (default: tfidf)",
    )
    parser.add_argument(
        "--corpus", type=Path, default=None,
        help="Corpus directory containing notes/ (default: aurelius/)",
    )
    args = parser.parse_args()
    build(args.method, args.corpus)
