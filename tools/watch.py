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


# ---- HTTP SERVER (runs in background thread) ----

class QuietHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with suppressed request logs."""
    def log_message(self, format, *args): # noqa: A002
        pass   # silence per-request noise; we print our own rebuild stamps

def start_server():
    """Serve repo root on PORT in a daemon thread (dies with the main process)."""
    server = HTTPServer(("", PORT), QuietHandler)
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
