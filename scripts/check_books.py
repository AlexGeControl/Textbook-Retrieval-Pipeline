"""Intake check for the PDF landing zone.

For every book in config/books.yaml: verify the PDF is present, born-digital
(sampled pages have a text layer), and has a usable outline or manual ranges.
Writes books/manifest.json (hashes, page counts, outline size — safe to commit;
it contains no book content). Exits non-zero on any failure.

Run:  uv run scripts/check_books.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pymupdf
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "books.yaml"
MANIFEST = ROOT / "books" / "manifest.json"
SAMPLE_PAGES = 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_book(book_id: str, book: dict) -> tuple[dict | None, list[str]]:
    failures: list[str] = []
    pdf = ROOT / book["pdf"]
    if not pdf.exists():
        return None, [f"{book_id}: missing {book['pdf']}"]

    doc = pymupdf.open(pdf)
    start, end = (0, doc.page_count)
    if book.get("body_range"):
        start, end = book["body_range"]["begin"], book["body_range"]["end"]
    step = max(1, (end - start) // SAMPLE_PAGES)
    sampled = list(range(start, end, step))
    text_pages = sum(1 for i in sampled if doc[i].get_text().strip())
    toc = doc.get_toc()
    top_level = [t for t in toc if t[0] == 1]

    entry = {
        "pdf": book["pdf"],
        "sha256": sha256(pdf),
        "pages": doc.page_count,
        "text_layer_sample": f"{text_pages}/{len(sampled)}",
        "outline_entries": len(toc),
        "outline_top_level": len(top_level),
        "first_outline_titles": [t[1] for t in top_level[:5]],
    }

    if text_pages < len(sampled):
        failures.append(
            f"{book_id}: {len(sampled) - text_pages} of {len(sampled)} sampled pages "
            "have no text layer — not born-digital as assumed in HANDOVER §2"
        )
    if not toc and not book.get("chapter_ranges"):
        failures.append(
            f"{book_id}: no PDF outline and no chapter_ranges in books.yaml — "
            "stage 1 would have to guess page ranges"
        )
    return entry, failures


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text())
    manifest: dict[str, dict] = {}
    failures: list[str] = []

    for book_id, book in cfg["books"].items():
        entry, errs = check_book(book_id, book)
        if entry:
            manifest[book_id] = entry
        failures.extend(errs)

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    for book_id, e in manifest.items():
        print(
            f"OK   {book_id:8s} {e['pages']:5d} pages  text {e['text_layer_sample']:>6s}  "
            f"outline {e['outline_entries']:4d} ({e['outline_top_level']} top-level)"
        )
    for f in failures:
        print(f"FAIL {f}")
    print(f"\n{len(manifest)} present, {len(failures)} failures -> {MANIFEST.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
