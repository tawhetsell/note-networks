#!/usr/bin/env python3
"""
Parse tools/Aurelius_text.md (Project Gutenberg Casaubon translation of
Marcus Aurelius's Meditations) and write atomic notes to notes/.

Selection: top 6 passages per book ranked by word count (most substantive
passages per book), which correlates well with the themes Goodreads readers
cite most — the longer passages are where Aurelius develops the ideas that
get quoted. Books 4, 6, 7, 8 are longer so take 7 from those.

Result: ~76 atomic notes, one per passage, using the actual Gutenberg text.

Usage: python tools/seed_from_aurelius.py
"""

import re
from pathlib import Path

REPO      = Path(__file__).resolve().parent.parent
NOTES     = REPO / "notes"
SOURCE    = REPO / "tools" / "Aurelius_text.md"

# Ordinal word → book number
ORDINALS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4,
    "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8,
    "NINTH": 9, "TENTH": 10, "ELEVENTH": 11, "TWELFTH": 12,
}

# How many passages to take per book (longer books get one extra)
QUOTA = {1:5, 2:6, 3:6, 4:7, 5:6, 6:7, 7:7, 8:7, 9:6, 10:6, 11:6, 12:5}

# Stoic theme tags — mapped by keyword presence in passage text
THEME_KEYS = [
    ("death",       r"\b(death|die|dying|mortal|perish|dead)\b"),
    ("mind",        r"\b(mind|thought|soul|opinion|conceit|fancy)\b"),
    ("nature",      r"\b(nature|natural|universe|world|cosmos)\b"),
    ("virtue",      r"\b(virtue|virtuous|good|righteous|honour)\b"),
    ("reason",      r"\b(reason|rational|rational|understanding|wisdom)\b"),
    ("present",     r"\b(present|moment|now|day|morning|hour)\b"),
    ("body",        r"\b(body|flesh|blood|corporeal|bones)\b"),
    ("providence",  r"\b(god|gods|divine|providence|fate|destiny)\b"),
    ("society",     r"\b(men|man|mankind|fellow|neighbour|citizen|kinsman)\b"),
    ("passion",     r"\b(anger|passion|grief|fear|desire|lust|pain|pleasure)\b"),
]

# Roman numeral → integer (handles I–LXXV, enough for all Meditations passages)
def roman_to_int(s: str) -> int:
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100}
    result, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        result += v if v >= prev else -v
        prev = v
    return result


def parse_passages(text: str) -> list[dict]:
    """Return list of {book, passage, text} dicts parsed from Gutenberg source."""
    passages = []
    current_book = 0

    # Split on book headers ("THE FIRST BOOK" etc.)
    # re.split keeps the delimiter groups so we can track book numbers
    book_pattern = re.compile(r"THE ([A-Z]+) BOOK", re.IGNORECASE)
    passage_pattern = re.compile(r"^([IVXLC]+)\.\s+(.+)", re.DOTALL)

    # Walk line by line; passages are separated by blank lines after a roman numeral
    lines = text.split("\n")
    current_passage_num = 0
    current_passage_lines = []
    in_passage = False

    for line in lines:
        # Book header
        bm = book_pattern.search(line)
        if bm:
            # Flush any open passage
            if in_passage and current_passage_lines:
                body = " ".join(current_passage_lines).strip()
                if body:
                    passages.append({
                        "book": current_book,
                        "passage": current_passage_num,
                        "text": body,
                    })
            current_book = ORDINALS.get(bm.group(1).upper(), 0)
            current_passage_num = 0
            current_passage_lines = []
            in_passage = False
            continue

        # New passage: line starts with roman numeral + period
        pm = re.match(r"^([IVXLC]+)\.\s+(.*)", line.strip())
        if pm and current_book > 0:
            # Flush previous passage
            if in_passage and current_passage_lines:
                body = " ".join(current_passage_lines).strip()
                if body:
                    passages.append({
                        "book": current_book,
                        "passage": current_passage_num,
                        "text": body,
                    })
            current_passage_num = roman_to_int(pm.group(1))
            current_passage_lines = [pm.group(2).strip()]
            in_passage = True
            continue

        # Continuation of current passage
        if in_passage:
            stripped = line.strip()
            if stripped:
                current_passage_lines.append(stripped)

    # Flush last passage
    if in_passage and current_passage_lines:
        body = " ".join(current_passage_lines).strip()
        if body:
            passages.append({
                "book": current_book,
                "passage": current_passage_num,
                "text": body,
            })

    return passages


def extract_tags(text: str) -> list[str]:
    """Return Stoic theme tags found in passage text."""
    text_lower = text.lower()
    return [tag for tag, pattern in THEME_KEYS
            if re.search(pattern, text_lower, re.IGNORECASE)]


def select_passages(passages: list[dict]) -> list[dict]:
    """Select top-N per book by word count."""
    by_book: dict[int, list[dict]] = {}
    for p in passages:
        # Filter out very short passages (not enough for TF-IDF)
        if len(p["text"].split()) < 40:
            continue
        by_book.setdefault(p["book"], []).append(p)

    selected = []
    for book_num, quota in QUOTA.items():
        book_passages = by_book.get(book_num, [])
        # Sort by word count descending, take top quota
        ranked = sorted(book_passages, key=lambda x: len(x["text"].split()), reverse=True)
        selected.extend(ranked[:quota])

    # Re-sort by book then passage number for clean filenames
    selected.sort(key=lambda x: (x["book"], x["passage"]))
    return selected


def int_to_roman(n: int) -> str:
    """Integer to uppercase Roman numeral string."""
    val = [1000,900,500,400,100,90,50,40,10,9,5,4,1]
    syms = ["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
    result = ""
    for v, s in zip(val, syms):
        while n >= v:
            result += s
            n -= v
    return result


def main():
    if not SOURCE.exists():
        print(f"Source file not found: {SOURCE}")
        print("Expected: tools/Aurelius_text.md")
        return

    text = SOURCE.read_text(encoding="utf-8", errors="ignore")
    all_passages = parse_passages(text)
    selected    = select_passages(all_passages)

    NOTES.mkdir(parents=True, exist_ok=True)
    # Remove previously seeded Meditations notes
    for f in NOTES.glob("med-*.md"):
        f.unlink()

    for p in selected:
        book_num    = p["book"]
        passage_num = p["passage"]
        body        = p["text"]
        roman       = int_to_roman(book_num)
        note_id     = f"med-{book_num:02d}-{passage_num:03d}"
        speaker     = f"BOOK_{roman}"      # drives node color by book
        source      = f"Meditations {roman}.{passage_num}"
        tags        = extract_tags(body) or ["stoic"]
        wc          = len(body.split())

        fm = (
            f"---\n"
            f"id: {note_id}\n"
            f"speaker: {speaker}\n"
            f'source: "{source}"\n'
            f"tags: [{', '.join(tags)}]\n"
            f"word_count: {wc}\n"
            f"---\n\n"
            f"{body}\n"
        )
        fname = f"{note_id}.md"
        (NOTES / fname).write_text(fm, encoding="utf-8")

    print(f"Parsed {len(all_passages)} total passages from {SOURCE.name}")
    print(f"Selected {len(selected)} passages across 12 books")
    by_book = {}
    for p in selected:
        by_book[p["book"]] = by_book.get(p["book"], 0) + 1
    for b, cnt in sorted(by_book.items()):
        print(f"  Book {int_to_roman(b):>5s}  {cnt} passages")
    print(f"Notes written to {NOTES}")


if __name__ == "__main__":
    main()
