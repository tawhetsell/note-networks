# Note Networks — Portable Zettelkasten with Live Semantic Graph

Turn a folder of markdown notes into an interactive, self-updating knowledge graph — with no cloud services, no internet connection required after setup.

---

## Use case

You have a body of text you want to think with: research notes, book excerpts, meeting summaries, a reading journal. You want to see the structure — which ideas cluster, which are hubs everything passes through, which sit isolated at the edges.

Note Networks does that. You write short atomic notes, one idea per file. The tool reads them, builds connections between notes based on shared vocabulary or shared tags, and draws the result as a navigable graph.

The graph updates live as you write. Open a note in your editor, save, and the browser re-renders within a few seconds — no manual rebuild, no page refresh.

---

## What you get

- **Two link methods** — TF-IDF vocabulary co-occurrence (algorithmic, from text) or tag-based Jaccard (from your own annotations); switch between them in the viewer
- **Live reload** — file watcher + HEAD poll, updates in ~3 seconds
- **Interactive viewer**: pan, zoom, click a node to read it, hover an edge to see shared terms or tags
- **12 layout algorithms** — Force (FR), Force Atlas, Kamada-Kawai, spectral, circular, concentric, and more
- **Edge density filter** — collapse the graph from all edges down to only the strongest connections with a single click
- **Gephi-aligned physics controls** — Repulsion and Gravity sliders that match the parameters Gephi users already know
- **Scrollable note list** with sort by title, chronology, or degree centrality
- **Fully local** — no account, no API key, no data leaves your machine

---

## Quickstart

```bash
git clone https://github.com/tawhetsell/note-networks.git
cd note-networks
pip install -r requirements.txt
python tools/build_graph.py
python tools/watch.py
```

Open **http://localhost:8765/viz/graph.html**.

Drop `.md` files into `notes/` and the graph rebuilds automatically.

---

## Note format

Each note needs a YAML frontmatter block:

```yaml
---
id: my-note-001
speaker: ME           # drives node color — use author, project, domain, or any grouping
source: "My source"   # shown in the side panel when you click a node
tags: [idea, concept]
word_count: 80
---

Note body goes here.
```

The `notes/` folder supports subdirectories. `build_graph.py` walks the full tree.

---

## How it works

```
notes/*.md
    │
    ▼
tools/build_graph.py
    ├─ Strip YAML frontmatter, tokenize, remove stopwords
    ├─ TF-IDF: score each term tf × log(N / (1 + df))
    ├─ Keep top-25 distinctive terms per note
    └─ Draw an edge between any two notes sharing a top-25 term
    │
    ▼
data/graph.json          nodes + edges + metadata
    │
    ▼
viz/graph.html
    ├─ d3 v7 force simulation (Fruchterman–Reingold + Force Atlas)
    ├─ Node size = degree centrality
    ├─ Click node  → side panel with full note body
    ├─ Hover edge  → tooltip showing shared terms or tags
    ├─ Links toggle → switch between TF-IDF and tag-based edges live
    └─ HEAD poll every 3 s → auto-reload on graph change
```

**TF-IDF** down-weights words that appear across many notes and surfaces terms distinctive to a small number. An edge forms only when a term ranks in the top-25 for *both* notes — this cuts noise from common words that slip past the stopword list.

**Tag-based edges** connect notes that share tags you annotated yourself. Edge weight equals the number of shared tags, so the density filter lets you show only notes with two or more tags in common — a sparser, more intentional view of your corpus.

### BM25 variant

For corpora where note length varies significantly, BM25 scoring gives better results than plain TF-IDF by saturating term frequency and normalising for document length:

```bash
python tools/build_graph.py --method bm25
```

---

## Folder structure

```
note-networks/
├── notes/                    ← your atomic notes (Markdown)
├── tools/
│   ├── build_graph.py        ← notes/ → data/graph.json  (--method tfidf|bm25)
│   ├── seed_from_aurelius.py ← generates the demo corpus
│   └── watch.py              ← file watcher + HTTP server on port 8765
├── viz/
│   └── graph.html            ← self-contained browser viewer (d3 v7)
├── data/                     ← generated (gitignored — rebuild anytime)
└── requirements.txt
```

---

## Requirements

- Python 3.9+
- `watchdog` (file watcher), `requests`, `beautifulsoup4` — see `requirements.txt`
- A modern browser

No Node.js, no build step, no database. `d3.js` loads from CDN on first open; subsequent loads use the browser cache.

| Platform | Command |
|---|---|
| macOS / Linux | `python3 tools/watch.py` |
| Windows | `python tools/watch.py` |

---

## Demo corpus

The repo ships with 74 passages from Marcus Aurelius's *Meditations* (Casaubon translation, Project Gutenberg), annotated with Stoic theme tags. Run `python tools/seed_from_aurelius.py` to write them to `notes/`, then `python tools/build_graph.py` to render the graph. The TF-IDF and Tags link methods produce visually distinct graphs of the same corpus — a useful illustration of how the two approaches differ.

---

## Roadmap

| Version | Feature |
|---|---|
| V1 (current) | TF-IDF and tag-based links, 12 layout algorithms, live reload |
| V2 | Named-entity extraction (spaCy) for person / place / concept nodes |
| V3 | Sentence-transformer embeddings for semantic similarity |

---

## Acknowledgements

Layout algorithms and physics parameter conventions are modelled on [Gephi](https://gephi.org/), the open-source network visualisation platform. The Repulsion / Gravity slider names, the Force Atlas degree-weighted repulsion, and the Kamada-Kawai stress-minimisation approach all follow Gephi's design. Gephi remains the reference tool for serious network analysis; Note Networks borrows its vocabulary to make the physics controls familiar to anyone who has used it.

---

## Built with Claude Code

This application was built with [Claude Code](https://claude.ai/code) running inside the VS Code extension. The graph layout algorithms, TF-IDF pipeline, live-reload watcher, and interactive viewer were all designed and implemented through an iterative conversation with the agent.
