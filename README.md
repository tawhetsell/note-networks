# Note Networks — Portable Zettelkasten with Live Semantic Graph

Turn a folder of markdown notes into an interactive, self-updating knowledge graph — with no cloud services, no embeddings, and no internet connection required after setup.

---

## Use case

You have a body of text you want to think with: research notes, book excerpts, meeting summaries, a reading journal. You want to see the structure — which ideas cluster, which are hubs everything passes through, which sit isolated at the edges.

Note Networks does that. You write short atomic notes, one idea per file. The tool reads them, scores each note's vocabulary with TF-IDF to surface its most distinctive terms, then draws edges between notes that share those terms. The result is a navigable map of your corpus.

The graph updates live as you write. Open a note in your editor, save, and the browser re-renders within a few seconds — no manual rebuild, no page refresh.

---

## What you get

- **Semantic co-occurrence graph** built from your actual text, not hand-coded links
- **Live reload** — file watcher + HEAD poll, updates in ~3 seconds
- **Interactive viewer**: pan, zoom, click a node to read it, hover an edge to see the shared terms that connected two notes
- **13 layout algorithms** — Force (FR), Force Atlas, Kamada-Kawai, spectral, circular, concentric, and more
- **Edge density filter** — collapse the graph from all edges down to only the strongest connections (≥2, ≥3, ≥4 shared terms) with a single click
- **Gephi-aligned physics controls** — Repulsion and Gravity sliders that match the parameters Gephi users already know
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
    ├─ Hover edge  → tooltip showing shared terms
    └─ HEAD poll every 3 s → auto-reload on graph change
```

TF-IDF down-weights words that appear across many notes and surfaces terms distinctive to a small number. An edge forms only when a term ranks in the top-25 for *both* notes — this cuts noise from common words that slip past the stopword list.

---

## Folder structure

```
note-networks/
├── notes/                    ← your atomic notes (Markdown)
├── tools/
│   ├── build_graph.py        ← notes/ → data/graph.json
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

The repo ships with 74 passages from Marcus Aurelius's *Meditations* (Casaubon translation, Project Gutenberg). Run `python tools/seed_from_aurelius.py` to write them to `notes/`, then `build_graph.py` to render the graph.

---

## Roadmap

| Version | Feature |
|---|---|
| V1 (current) | TF-IDF co-occurrence, 13 layout algorithms, live reload |
| V2 | Sentence-transformer embeddings for semantic similarity |
| V3 | Named-entity extraction (spaCy) for person / place / concept nodes |

---

## Acknowledgements

Layout algorithms and physics parameter conventions are modelled on [Gephi](https://gephi.org/), the open-source network visualisation platform. The Repulsion / Gravity slider names, the Force Atlas degree-weighted repulsion, and the Kamada-Kawai stress-minimisation approach all follow Gephi's design. Gephi remains the reference tool for serious network analysis; Note Networks borrows its vocabulary to make the physics controls familiar to anyone who has used it.

---

## Built with Claude Code

This application was built with [Claude Code](https://claude.ai/code) — Anthropic's agentic coding tool — running the **Claude Opus 4.7** model inside the VS Code extension. The graph layout algorithms, TF-IDF pipeline, live-reload watcher, and interactive viewer were all designed and implemented through a single iterative conversation with the agent.
