#!/usr/bin/env python3
"""
Fetch the Federalist Papers from Project Gutenberg (public domain, ~1787).
Parses individual papers by number, author, title, and full text.
Outputs: federalist_papers.json at repo root.

Usage: python tools/fed_papers_fetch.py
Analog to bsg_33_fetch.py but for the Federalist Papers corpus.
"""

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup            # HTML parser

REPO = Path(__file__).resolve().parent.parent   # repo root via script location

# Project Gutenberg plain-text edition of the Federalist Papers (EBook #1404)
SOURCES = [
    "https://www.gutenberg.org/cache/epub/1404/pg1404.txt",
    "https://www.gutenberg.org/files/1404/1404-0.txt",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (research; personal use)"}

# Author pseudonym -> real name mapping (Hamilton, Madison, Jay all wrote as "Publius")
AUTHORS = {
    "HAMILTON":        "Alexander Hamilton",
    "MADISON":         "James Madison",
    "JAY":             "John Jay",
    "HAMILTON OR MADISON": "Hamilton or Madison",
}


def fetch(url: str) -> str:
    """GET url, raise on HTTP errors, return decoded text."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()                # throws on 4xx/5xx
    return r.text


def parse_papers(text: str) -> list[dict]:
    """
    Split the Gutenberg plain text into individual Federalist Papers.
    The file uses headers like 'FEDERALIST No. 10.' or 'FEDERALIST No. X.'
    Returns list of dicts: {number, title, author, text}
    """
    # Normalize Windows line endings
    text = text.replace("\r\n", "\n")

    # Locate the start of the actual content (past Gutenberg boilerplate)
    start = text.find("FEDERALIST No. 1")
    if start == -1:
        start = text.find("FEDERALIST No 1")
    if start == -1:
        return []
    text = text[start:]

    # Split on paper headers: "FEDERALIST No. N." or "FEDERALIST No N"
    # re.split with a capturing group keeps the delimiters in the result list
    parts = re.split(r"(FEDERALIST(?:,? No\.?|,? No) \d+\.?)", text, flags=re.IGNORECASE)

    papers = []
    i = 1
    while i < len(parts) - 1:
        header = parts[i].strip()
        body   = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2

        # Extract paper number from header
        m = re.search(r"(\d+)", header)
        if not m:
            continue
        number = int(m.group(1))

        # First non-empty lines of body: title then blank then author then blank then "To the People..."
        lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]

        # Try to find an author name among known authors
        author = "UNKNOWN"
        title  = ""
        for idx, ln in enumerate(lines[:8]):
            up = ln.upper()
            for key in AUTHORS:
                if key in up:
                    author = key
                    break
            if author != "UNKNOWN":
                # Title is likely the line(s) before the author line
                title = " ".join(lines[:idx]).strip()
                break
        if not title and lines:
            title = lines[0]

        # Body text: skip header lines, keep main prose
        # Strip trailing Gutenberg end-of-ebook notice
        prose = body.strip()
        end_mark = prose.find("End of the Project Gutenberg")
        if end_mark != -1:
            prose = prose[:end_mark]

        papers.append({
            "number": number,
            "title":  title,
            "author": author,
            "text":   prose.strip(),
        })

    return papers


def main():
    raw = None
    for url in SOURCES:
        try:
            print(f"Fetching: {url}", file=sys.stderr)
            raw = fetch(url)
            print(f"  got {len(raw):,} chars", file=sys.stderr)
            break
        except Exception as e:
            print(f"  failed: {e}", file=sys.stderr)

    if not raw:
        sys.exit("All Gutenberg sources failed. Check connectivity or update SOURCES.")

    papers = parse_papers(raw)
    if not papers:
        raw_out = REPO / "federalist_raw.txt"
        raw_out.write_text(raw, encoding="utf-8")
        sys.exit(f"Parser found no papers. Raw text saved to {raw_out} — inspect format.")

    out = REPO / "federalist_papers.json"
    out.write_text(json.dumps(papers, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n--- Federalist Papers fetch stats ---")
    print(f"Papers parsed:    {len(papers)}")
    print(f"Avg text length:  {sum(len(p['text']) for p in papers) // len(papers):,} chars")
    print(f"Authors found:    {sorted({p['author'] for p in papers})}")
    print(f"\nWrote → {out}")


if __name__ == "__main__":
    main()
