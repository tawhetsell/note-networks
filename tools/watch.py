#!/usr/bin/env python3
"""
Watch notes/ for changes and rebuild the graph automatically.
Also serves the repo on http://localhost:8765 so viz/graph.html
can load ../data/graph.json and ../notes/*.md via fetch() without
hitting browser file:// cross-origin restrictions.

Usage: python tools/watch.py
Opens the browser for you.  To reopen later, use the link it prints
(it carries this session's access token).

Deps: watchdog (pip install -r requirements.txt)
"""

import json as _json
import re as _re
import secrets
import subprocess
import sys
import webbrowser
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from watchdog.events import FileSystemEventHandler    # base class for FS events
from watchdog.observers import Observer               # thread that polls FS

REPO       = Path(__file__).resolve().parent.parent
BUILDER    = REPO / "tools" / "build_graph.py"
PORT       = 8765
DEBOUNCE   = 0.5   # seconds to wait after last change before rebuilding

# Host headers we answer to.  A request naming any other host (e.g. evil.com that
# re-pointed its DNS at 127.0.0.1 — "DNS rebinding") is refused, so a website can't
# read notes by pretending to be this server.
ALLOWED_HOSTS = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}

# Origins allowed to POST/DELETE.  graph.html is served from this server, so its
# requests are same-origin; anything else (another site open in the browser) is refused.
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}

# Per-run access token.  The browser is opened at /login?token=…, which stores it
# in a cookie; every other request must carry that cookie.  This keeps other user
# accounts on the same machine (who can reach 127.0.0.1 but not your files) out.
# secrets.token_urlsafe(): cryptographically random, URL-safe text.
TOKEN       = secrets.token_urlsafe(32)
COOKIE_NAME = f"nn_session_{PORT}"

# CORPUS_DIR and NOTES_DIR are set in main() from the CLI corpus argument.
# Module-level defaults keep type checkers and the file helpers happy at import time.
CORPUS_DIR = REPO / "networks" / "aurelius"
NOTES_DIR  = CORPUS_DIR / "notes"


# ---- NOTE FILE HELPERS ----

def _inside_notes_dir(p: Path) -> bool:
    """True if p, after resolving symlinks and '..', still lives under NOTES_DIR."""
    # Path.resolve(): make absolute and follow symlinks (works on paths that don't exist yet).
    # Path.is_relative_to(): True if the path starts with the given directory.
    try:
        return p.resolve().is_relative_to(NOTES_DIR.resolve())
    except OSError:
        # e.g. Windows "D:x" names point at another drive that may be locked/missing
        return False

def _valid_stem(stem: str) -> bool:
    """
    Reject note names that could escape NOTES_DIR (path traversal).
    A stem is a bare filename: no separators, no '..', no control characters
    (NUL, newline, … — Windows can't store them, and a newline would also break
    the id: line in the frontmatter).
    """
    if not stem or ".." in stem or any(c in stem for c in ("/", "\\")):
        return False
    # ord(): a character's Unicode code point.  0–31 and 127–159 are the control characters.
    if any(ord(c) < 32 or 127 <= ord(c) < 160 for c in stem):
        return False
    return _inside_notes_dir(NOTES_DIR / (stem + ".md"))

def _find_note_file(stem: str) -> Path | None:
    """Return the Path for a note by its stem (filename without extension)."""
    for ext in (".md", ".txt", ".rtf"):
        p = NOTES_DIR / (stem + ext)
        if p.exists() and _inside_notes_dir(p):
            return p
    for p in NOTES_DIR.rglob(stem + ".*"):
        if p.suffix.lower() in {".md", ".txt", ".rtf"} and _inside_notes_dir(p):
            return p
    return None

_FM_RE = _re.compile(r"^---\n(.*?)\n---\n", _re.DOTALL)

def _read_frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Split raw file text into a frontmatter dict and the body string."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    current_key = None   # tracks the last key that opened a multi-line list
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and current_key is not None:
            if not isinstance(fm.get(current_key), list):
                fm[current_key] = []
            fm[current_key].append(stripped[2:].strip().strip('"').strip("'"))
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
            fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
        elif val.isdigit():
            fm[key] = int(val)
        elif val == "":
            fm[key] = []
            current_key = key
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

    def parse_request(self):
        # parse_request(): http.server's hook that reads the request line + headers
        # before any do_GET/do_POST runs — one place to vet every request.
        if not super().parse_request():
            return False
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            self.send_error(403, "Host not allowed")
            return False
        if self.path.startswith("/login"):
            self._login()
            return False          # _login() already sent the response
        if not self._has_session():
            self.send_error(401, "Not signed in: open the link printed by watch.py")
            return False
        return True

    def _login(self) -> None:
        """Swap a valid ?token= for a session cookie, then redirect to the viewer."""
        import urllib.parse
        query = urllib.parse.urlsplit(self.path).query
        token = urllib.parse.parse_qs(query).get("token", [""])[0]
        # secrets.compare_digest(): constant-time compare, so response timing
        # can't leak how many leading characters of a guess were right.
        if not secrets.compare_digest(token, TOKEN):
            self.send_error(403, "Invalid token")
            return
        self.send_response(303)   # 303 See Other: follow-up request is a plain GET
        # HttpOnly: page scripts can't read the cookie.  SameSite=Strict: the browser
        # won't attach it to requests that other websites trigger.
        self.send_header("Set-Cookie",
                         f"{COOKIE_NAME}={TOKEN}; Path=/; HttpOnly; SameSite=Strict")
        # Redirecting drops the token from the address bar and browser history.
        self.send_header("Location", "/viz/graph.html")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _has_session(self) -> bool:
        from http.cookies import SimpleCookie, CookieError   # parses the "Cookie:" header
        try:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        sent = jar[COOKIE_NAME].value if COOKIE_NAME in jar else ""
        return secrets.compare_digest(sent, TOKEN)

    def translate_path(self, path):
        # Redirect /data/* and /notes/* to CORPUS_DIR so graph.html paths work
        # regardless of where the corpus lives.  All other paths serve from repo root.
        import urllib.parse, posixpath
        clean = path.split("?")[0].split("#")[0]
        p = urllib.parse.unquote(clean, errors="surrogatepass")
        p = posixpath.normpath(p)
        if p.startswith("/data") or p.startswith("/notes"):
            # strip leading slash, join with corpus dir
            parts = [w for w in p.split("/") if w not in ("", ".", "..")]
            return str(CORPUS_DIR.joinpath(*parts)) if parts else str(CORPUS_DIR)
        return super().translate_path(path)

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
            if not _valid_stem(stem):
                self._send_json(400, {"error": "Invalid note name"})
                return
            p = _find_note_file(stem)
            if not p:
                self._send_json(404, {"error": "Not found"})
                return
            text = p.read_text(encoding="utf-8", errors="ignore")
            self._send_json(200, {"content": text})
            return
        super().do_GET()

    def _origin_ok(self) -> bool:
        """
        Browsers attach an Origin header to cross-site POST/DELETE requests.
        If one is present and isn't this server, another website is trying to
        write to our notes — refuse.  (No Origin = curl/scripts; allowed.)
        """
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            self._send_json(403, {"error": "Origin not allowed"})
            return False
        return True

    def do_POST(self):
        if not self._origin_ok():
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = _json.loads(self.rfile.read(length))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if self.path.startswith("/api/note/") and self.path != "/api/note/":
            # Update existing note: preserve all frontmatter, replace tags + body
            stem = self.path[len("/api/note/"):]
            if not _valid_stem(stem):
                self._send_json(400, {"error": "Invalid note name"})
                return
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
            try:
                p.write_text(_build_frontmatter(fm) + "\n" + new_body, encoding="utf-8")
            except OSError as e:
                self._send_json(500, {"error": f"Could not save note: {e.strerror}"})
                return
            self._send_json(200, {"ok": True})
            return

        if self.path == "/api/note":
            # Create new note
            note_id = payload.get("id", "").strip()
            if not note_id:
                self._send_json(400, {"error": "id required"})
                return
            if not _valid_stem(note_id):
                self._send_json(400, {"error": "Invalid note name"})
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
            try:
                p.write_text(_build_frontmatter(fm) + "\n" + body, encoding="utf-8")
            except OSError as e:
                # e.g. Windows refuses names containing < > : " | ? *
                self._send_json(500, {"error": f"Could not save note: {e.strerror}"})
                return
            self._send_json(201, {"ok": True, "id": note_id})
            return

        self._send_json(404, {"error": "Unknown endpoint"})

    def do_DELETE(self):
        if not self._origin_ok():
            return
        if self.path.startswith("/api/note/") and self.path != "/api/note/":
            stem = self.path[len("/api/note/"):]
            if not _valid_stem(stem):
                self._send_json(400, {"error": "Invalid note name"})
                return
            p = _find_note_file(stem)
            if not p:
                self._send_json(404, {"error": "Note not found"})
                return
            try:
                p.unlink()
            except OSError as e:
                self._send_json(500, {"error": f"Could not delete note: {e.strerror}"})
                return
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "Unknown endpoint"})

    def do_OPTIONS(self):
        # No Access-Control-* headers on purpose: graph.html is same-origin and never
        # sends a CORS preflight, so a cross-site preflight here should simply fail.
        self.send_response(204)
        self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
        self.end_headers()


def start_server():
    """Serve repo root on PORT in a daemon thread (dies with the main process)."""
    # 127.0.0.1 = loopback only.  "" would listen on every interface (LAN, Wi-Fi),
    # letting other machines on the network read and edit notes.
    server = HTTPServer(("127.0.0.1", PORT), AppHandler)
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
            [sys.executable, str(BUILDER), "--corpus", str(CORPUS_DIR)],
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
    import argparse, os
    global CORPUS_DIR, NOTES_DIR

    parser = argparse.ArgumentParser(description="Watch a note corpus and serve the viewer.")
    parser.add_argument(
        "corpus", nargs="?", type=Path, default=REPO / "networks" / "aurelius",
        help="Corpus directory (default: networks/aurelius/).  Created automatically if missing.",
    )
    args = parser.parse_args()

    CORPUS_DIR = args.corpus.resolve()
    NOTES_DIR  = CORPUS_DIR / "notes"

    # Create corpus structure if it doesn't exist yet
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    (CORPUS_DIR / "data").mkdir(parents=True, exist_ok=True)

    os.chdir(str(REPO))   # serve static files relative to repo root

    print(f"Corpus:  {CORPUS_DIR}")
    print(f"Watching {NOTES_DIR} for changes...")
    login_url = f"http://localhost:{PORT}/login?token={TOKEN}"
    print(f"Serving  {login_url}")
    print(f"         (link includes this session's access token; it changes on every restart)")
    print(f"Press Ctrl-C to stop.\n")

    # Run an initial build so the page loads immediately
    print("Initial build...", end=" ", flush=True)
    r = subprocess.run(
        [sys.executable, str(BUILDER), "--corpus", str(CORPUS_DIR)],
        cwd=str(REPO), capture_output=True, text=True,
    )
    print("OK" if r.returncode == 0 else f"FAILED\n{r.stderr}")

    # webbrowser.open: launches the system default browser
    webbrowser.open(login_url)

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
