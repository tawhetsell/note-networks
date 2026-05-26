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

Usage: python tools/build_graph.py
"""

import csv
import json
import re
import subprocess
import sys
from collections import Counter
from math import log
from pathlib import Path

# ---- CONFIG (tune these to taste) ----
REPO       = Path(__file__).resolve().parent.parent   # repo root via script location
NOTES_DIR  = REPO / "notes"
OUTPUT_DIR = REPO / "data"

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
    Handles: string, quoted string, list ([a, b, c]), int.
    Not a full YAML parser — sufficient for our simple schema.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}
    block = m.group(0)[4:-4]   # strip leading '---\n' and trailing '\n---\n'
    result = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # list field: [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            result[key] = [v.strip().strip('"').strip("'")
                           for v in inner.split(",") if v.strip()]
        elif val.isdigit():
            result[key] = int(val)
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

def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect files (rglob = recursive glob across all subdirectories)
    files = sorted(
        p for p in NOTES_DIR.rglob("*")
        if p.suffix.lower() in {".md", ".txt", ".rtf"}
    )
    if not files:
        print(f"No notes found in {NOTES_DIR}. Run: python tools/seed_from_aurelius.py",
              file=sys.stderr)
        sys.exit(1)

    # Read text and parse frontmatter per file
    raw_texts = {p.stem: read_file(p) for p in files}
    frontmatter = {p.stem: parse_frontmatter(raw_texts[p.stem]) for p in files}
    docs = {p.stem: tokens(raw_texts[p.stem]) for p in files}

    N  = len(docs)
    # Document frequency: how many notes each term appears in
    df = Counter()
    for toks in docs.values():
        df.update(set(toks))

    # TF-IDF: down-weight ubiquitous words, surface distinctive ones.
    # tfidf(tf, term) = term_freq * log(N / (1 + doc_freq))
    def tfidf(tf: int, term: str) -> float:
        return tf * log(N / (1 + df[term]))

    # Top-K distinctive terms per note
    distinctive: dict[str, set[str]] = {}
    for name, toks in docs.items():
        tf     = Counter(toks)
        ranked = sorted(tf.items(), key=lambda x: -tfidf(x[1], x[0]))
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
    json_out = OUTPUT_DIR / "graph.json"
    json_out.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    csv_out = OUTPUT_DIR / "co_occurrence.csv"
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

    print(f"Built graph: {len(nodes)} nodes, {len(edges)} edges")
    print(f"  -> {json_out}")
    print(f"  -> {csv_out}")
    # Speaker distribution
    by_spk = Counter(n["speaker"] for n in nodes)
    for spk, cnt in sorted(by_spk.items()):
        print(f"     {spk:20s} {cnt:3d} notes")


if __name__ == "__main__":
    build()
