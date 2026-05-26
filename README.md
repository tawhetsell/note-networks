# Note Networks — Portable Zettelkasten with Live Semantic Graph

A local, self-contained tool that turns a folder of markdown notes into an interactive force-directed graph. It finds thematic connections between notes automatically, without cloud services, embeddings, or an internet connection after setup.

---

## What it does

You write short atomic notes — one idea per file. The tool reads them all, computes [TF-IDF](https://en.wikipedia.org/wiki/Tf%E2%80%93idf) term weights to find each note's most distinctive vocabulary, then draws edges between notes that share distinctive terms. The result is a navigable map of your corpus: clusters reveal themes, hub nodes are the ideas everything connects through, and isolated nodes surface gaps.

The browser viewer updates automatically whenever you save a note. You pan, zoom, click a node to read it, hover an edge to see which terms connected two notes, and switch between 12 layout algorithms (force-directed, Kamada-Kawai, spectral, circular, and more).

Everything runs locally. No account, no API key, no data sent anywhere.

---

## Demo corpus

The included seed corpus covers every **Federalist and Anti-Federalist paper with a confirmed or best-estimate Supreme Court citation** — 67 notes total.

**Federalist papers (56):** Ranked by SCOTUS citation frequency using Lupu, *The Most-Cited Federalist Papers* (Constitutional Commentary, 1998), Corley, Howard & Nixon (Political Research Quarterly, 2005), and the Melton citation lists (Kentucky Law Journal, 1996–2007). Papers addressing only narrow legislative mechanics with no constitutional litigation surface are excluded.

**Anti-Federalist papers (11):** Identified by Zelinsky, *Misunderstanding the Anti-Federalist Papers* (Alabama Law Review, 2013) as appearing in SCOTUS opinions, supplemented by the citation trails in *Garcia v. San Antonio* (1985), *Printz v. United States* (1997), *District of Columbia v. Heller* (2008), and *McDonald v. City of Chicago* (2010). AF citations increased sharply after Storing's *Complete Anti-Federalist* (1981) made the full corpus accessible.

Each note is a ~100-word abstract of the paper's constitutional argument.

The graph produced:
- **Node size** = degree centrality (number of edges)
- **Node color** = author — Hamilton, Madison, Jay (Federalist); Brutus, Federal Farmer, Centinel, Cato (Anti-Federalist)
- **Edge weight** = shared distinctive terms
- **Labels** — Federalist: `F42 · commerce`, `F78 · judiciary`; Anti-Federalist: `B11 · supremacy`, `FF6 · rights`

The judicial power papers (#78, #80, #81, #82) cluster with Brutus #11 and #15, which predicted federal judicial expansion. Executive power papers (#69–#77) form a separate cluster. Federalist #51 (*Checks and Balances*) sits at the structural center.

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/tawhetsell/note-networks.git
cd note-networks
pip install -r requirements.txt

# 2. Seed the demo corpus (67 notes)
python tools/seed_from_fed.py

# 3. Build the graph
python tools/build_graph.py

# 4. Start the watcher + local server
python tools/watch.py
```

Then open **http://localhost:8765/viz/graph.html**.

The watcher monitors `notes/` for changes and rebuilds the graph automatically. The browser polls for updates every 3 seconds and re-renders without a manual refresh.

> **Without the watcher:** open `viz/graph.html` directly in a browser. The graph renders, but clicking a node to read its body requires the local server (browsers block `file://` cross-origin fetches).

---

## Optional: enrich with full paper text

```bash
# Fetch all 85 Federalist Papers from Project Gutenberg (~1 MB, one-time)
python tools/fed_papers_fetch.py

# Re-seed: prepends each paper's opening sentence to the abstract
python tools/seed_from_fed.py
```

---

## Using your own notes

Drop `.md` files into `notes/`, then run `python tools/build_graph.py` (or let the watcher do it). The only requirement is a YAML frontmatter block at the top:

```yaml
---
id: my-note-001
speaker: ME           # drives node color; use any consistent string
source: "My source"   # shown in the side panel
tags: [idea, concept]
word_count: 80
---

Note body goes here...
```

`speaker` is the categorical field that determines node color. Use it for author, project, domain, or any grouping that makes sense for your corpus. The color palette auto-extends as you add new values.

The `notes/` folder supports subdirectories — `build_graph.py` walks the full tree.

---

## How it works

```
notes/*.md
    │
    ▼
tools/build_graph.py          TF-IDF scoring
    │  ├─ Strip YAML frontmatter
    │  ├─ Tokenize + remove stopwords
    │  ├─ Score each term: tf × log(N / (1 + df))
    │  ├─ Keep top-25 distinctive terms per note
    │  └─ Draw edges where ≥1 distinctive term is shared
    │
    ▼
data/graph.json               nodes + edges + metadata
    │
    ▼
viz/graph.html                d3 v7 force-directed viewer
    ├─ Fruchterman–Reingold physics (forceManyBody + forceLink)
    ├─ 12 layout algorithms  (circular, Kamada-Kawai, spectral, …)
    ├─ Node size = degree centrality
    ├─ Click node  → side panel with note body
    ├─ Hover edge  → tooltip with shared terms
    └─ Auto-reload on graph.json change (HEAD poll every 3 s)
```

TF-IDF down-weights words that appear in many notes (common, uninformative) and surfaces words distinctive to a small number of notes. Two notes share a distinctive term only if it ranks in the top-25 for *both* — reducing noise edges from words that slip past the stopword list.

---

## Folder structure

```
note-networks/
├── notes/                  ← atomic notes (Markdown)
├── tools/
│   ├── build_graph.py      ← notes/ → data/graph.json + co_occurrence.csv
│   ├── seed_from_fed.py    ← write the demo corpus (67 notes)
│   ├── fed_papers_fetch.py ← fetch full paper texts from Project Gutenberg
│   └── watch.py            ← file watcher + local HTTP server (port 8765)
├── viz/
│   └── graph.html          ← self-contained browser viewer (d3 v7)
├── data/                   ← generated artifacts (gitignored — regenerate anytime)
│   ├── graph.json
│   └── co_occurrence.csv
├── requirements.txt
└── .gitignore
```

---

## Platform support

| Platform | Launch command |
|---|---|
| macOS / Linux | `python3 tools/watch.py` |
| Windows | `python tools/watch.py` or double-click `note-networks-pc.bat` |

All paths resolve from repo root via `Path(__file__).resolve().parent.parent`. The directory is fully portable — copy it to any machine or sync folder and it works without reconfiguration.

RTF file support is available on macOS via the built-in `textutil` converter. RTF files are skipped gracefully on other platforms.

---

## Requirements

- Python 3.9+
- `requests`, `beautifulsoup4`, `watchdog` (see `requirements.txt`)
- A modern browser (Chrome, Firefox, Safari, Edge)

No Node.js, no build step, no database. `d3.js` loads from a CDN on first open; subsequent loads use the browser cache.

---

## Roadmap

| Version | Feature |
|---|---|
| V1 (current) | TF-IDF co-occurrence, 67-note SCOTUS citation corpus, 12 layout algorithms |
| V2 | Sentence-transformer embeddings for semantic (not lexical) similarity |
| V3 | Named-entity extraction (spaCy) for person / place / concept nodes |

---

## License

Tool code is MIT. The included corpus (Federalist and Anti-Federalist Papers, 1787–1788) is public domain.
