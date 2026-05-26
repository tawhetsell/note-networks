#!/usr/bin/env python3
"""
Watch notes/ for changes and rebuild the graph automatically.
Also serves the repo on http://localhost:8765 so viz/graph.html
can load ../data/graph.json and ../notes/*.md via fetch() without
hitting browser file:// cross-origin restrictions.

Usage: python tools/watch.py
Open:  http://localhost:8765/viz/graph.html

Deps: watchdog (pip install watchdog)
"""

import json as _json
import re as _re
import subprocess
import sys
import webbrowser
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from watchdog.events import FileSystemEventHandler    # base class for FS events
from watchdog.observers import Observer               # thread that polls FS

REPO      = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO / "notes"
BUILDER   = REPO / "tools" / "build_graph.py"
PORT      = 8765
DEBOUNCE  = 0.5          # seconds to wait after last change before rebuilding


# ---- NOTE FILE HELPERS ----

def _find_note_file(stem: str) -> Path | None:
    """Return the Path for a note by its stem (filename without extension)."""
    for ext in (".md", ".txt", ".rtf"):
        p = NOTES_DIR / (stem + ext)
        if p.exists():
            return p
    for p in NOTES_DIR.rglob(stem + ".*"):
        if p.suffix.lower() in {".md", ".txt", ".rtf"}:
            return p
    return None

_FM_RE = _re.compile(r"^---\n(.*?)\n---\n", _re.DOTALL)

def _read_frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Split raw file text into a frontmatter dict and the body string."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
        elif val.isdigit():
            fm[key] = int(val)
        else:
            fm[key] = val
    return fm, text[m.end():]

def _build_frontmatter(fm: dict) -> str:
    """Serialise a dict back into a YAML frontmatter block."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---- HTTP SERVER (runs in background thread) ----

class AppHandler(SimpleHTTPRequestHandler):
    """
    Static file server + /api/* routes for read/write note access.

    GET  /api/ping            → {"ok": true}
    GET  /api/note/<stem>     → {"content": "<raw .md text>"}
    POST /api/note/<stem>     → update tags + body of an existing note
    POST /api/note            → create a new note
    """

    def log_message(self, format, *args):  # noqa: A002
        pass   # suppress per-request noise

    def _send_json(self, code: int, data: dict) -> None:
        body = _json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/ping":
            self._send_json(200, {"ok": True})
            return
        if self.path.startswith("/api/note/"):
            stem = self.path[len("/api/note/"):]
            p = _find_note_file(stem)
            if not p:
                self._send_json(404, {"error": "Not found"})
                return
            text = p.read_text(encoding="utf-8", errors="ignore")
            self._send_json(200, {"content": text})
            return
        super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = _json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if self.path.startswith("/api/note/") and self.path != "/api/note/":
            # Update existing note: preserve all frontmatter, replace tags + body
            stem = self.path[len("/api/note/"):]
            p = _find_note_file(stem)
            if not p:
                self._send_json(404, {"error": "Note not found"})
                return
            fm, _ = _read_frontmatter_and_body(
                p.read_text(encoding="utf-8", errors="ignore")
            )
            if "tags" in payload:
                tags = payload["tags"]
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                fm["tags"] = tags
            new_body = payload.get("body", "")
            fm["word_count"] = len(new_body.split())
            p.write_text(_build_frontmatter(fm) + "\n" + new_body, encoding="utf-8")
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/note":
            # Create new note
            note_id = payload.get("id", "").strip()
            if not note_id:
                self._send_json(400, {"error": "id required"})
                return
            p = NOTES_DIR / (note_id + ".md")
            if p.exists():
                self._send_json(409, {"error": "Note already exists"})
                return
            tags = payload.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            body = payload.get("body", "")
            fm = {
                "id":         note_id,
                "speaker":    payload.get("speaker", "ME"),
                "source":     payload.get("source", ""),
                "tags":       tags,
                "word_count": len(body.split()),
            }
            p.write_text(_build_frontmatter(fm) + "\n" + body, encoding="utf-8")
            self._send_json(201, {"ok": True, "id": note_id})
            return

        self._send_json(404, {"error": "Unknown endpoint"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_server():
    """Serve repo root on PORT in a daemon thread (dies with the main process)."""
    server = HTTPServer(("", PORT), AppHandler)
    # SimpleHTTPRequestHandler serves from cwd; we set cwd to repo root below
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ---- DEBOUNCED REBUILD ----

class RebuildHandler(FileSystemEventHandler):
    """
    On any .md/.txt/.rtf change in notes/, debounce 500 ms then rebuild.
    Debounce: cancel pending timer and reset it on each rapid-fire event,
    so a save-storm only triggers one rebuild.
    """
    def __init__(self):
        self._timer: threading.Timer | None = None
        self._lock  = threading.Lock()

    def on_any_event(self, event):
        # Ignore directory events and non-note file types
        if event.is_directory:
            return
        src = getattr(event, "src_path", "")
        if not any(src.endswith(ext) for ext in (".md", ".txt", ".rtf")):
            return
        with self._lock:
            if self._timer:
                self._timer.cancel()          # reset the debounce window
            self._timer = threading.Timer(DEBOUNCE, self._rebuild)
            self._timer.start()

    def _rebuild(self):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] Change detected — rebuilding graph...", flush=True)
        result = subprocess.run(
            [sys.executable, str(BUILDER)],
            capture_output=True, text=True,
            cwd=str(REPO)
        )
        ts2 = time.strftime("%H:%M:%S")
        if result.returncode == 0:
            # Print last non-empty line of build output (the summary line)
            summary = next(
                (ln for ln in reversed(result.stdout.splitlines()) if ln.strip()),
                "done"
            )
            print(f"[{ts2}] Rebuilt OK — {summary}", flush=True)
        else:
            print(f"[{ts2}] Build FAILED:\n{result.stderr}", flush=True)


# ---- MAIN ----

def main():
    import os
    os.chdir(str(REPO))   # serve files relative to repo root

    print(f"Watching {NOTES_DIR} for changes...")
    print(f"Serving  http://localhost:{PORT}/viz/graph.html")
    print(f"Press Ctrl-C to stop.\n")

    # Run an initial build so the page loads immediately
    print("Initial build...", end=" ", flush=True)
    r = subprocess.run([sys.executable, str(BUILDER)], cwd=str(REPO),
                       capture_output=True, text=True)
    print("OK" if r.returncode == 0 else f"FAILED\n{r.stderr}")

    # webbrowser.open: launches the system default browser
    url = f"http://localhost:{PORT}/viz/graph.html"
    webbrowser.open(url)

    start_server()

    # Watchdog observer: polls NOTES_DIR tree on a background thread
    handler  = RebuildHandler()
    observer = Observer()
    observer.schedule(handler, str(NOTES_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped.")
    observer.join()


if __name__ == "__main__":
    main()
