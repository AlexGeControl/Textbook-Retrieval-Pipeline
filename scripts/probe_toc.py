"""Inspect a book's PDF outline and check that config/books.yaml resolves its chapters.

  uv run scripts/probe_toc.py <book>            evidence for filling toc.* in books.yaml
  uv run scripts/probe_toc.py <book> --check    resolve every chapter in scope via stage 1

Evidence mode prints per-level entry counts, how many titles start with a number, sample
titles, page-label presence and page_offset candidates. Check mode runs build_meta for each
chapter the reading list (or the outline) exposes and exits 1 on any SplitError.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # run by path: uv run scripts/probe_toc.py

import pymupdf

from src.config import ROOT, ConfigError, book_cfg
from src.readings import list_chapters, load_readings
from src.split import SplitError, build_meta
from src.toc import chapter_entries, level_stats, offset_candidates


def evidence(book_id: str, cfg: dict, doc: pymupdf.Document, samples: int) -> None:
    toc = doc.get_toc()
    print(
        f"{book_id}: {doc.page_count} pages, {len(toc)} outline entries, toc config = {cfg['toc']}"
    )
    if not toc:
        print("  NO OUTLINE — only chapter_ranges can drive stage 1 for this book")
        return
    for lvl, (count, numbered) in level_stats(toc).items():
        titles = [t for l, t, _ in toc if l == lvl]
        print(f"  level {lvl}: {count:4d} entries, {numbered:4d} start with a number")
        for t in titles[:samples]:
            print(f"           {t[:90]}")
        if len(titles) > samples:
            print(f"           … {len(titles) - samples} more")
    entries = chapter_entries(toc, cfg["toc"])
    if entries:
        first, last = entries[0], entries[-1]
        print(
            f"  chapters under current config: {len(entries)} "
            f"({first.number} '{first.title[:40]}' p{toc[first.index][2]} … "
            f"{last.number} '{last.title[:40]}' p{toc[last.index][2]})"
        )
        start = toc[first.index][2] - 1
        labels = [doc[i].get_label() for i in range(start, min(start + 3, doc.page_count))]
        print(f"  page labels on the first chapter's pages: {labels!r}")
        if not any(lab.strip().isdigit() for lab in labels):
            cands = offset_candidates(doc, start, start + 8).most_common(3)
            print(f"  no numeric labels -> page_offset candidates (offset: hits): {cands}")
            if cands:
                print(f"  suggested: page_offset: {cands[0][0]}  (printed = pdf_1based - offset)")
    else:
        print(
            "  chapters under current config: none (set chapter_level + chapter_pattern, "
            "or a toc.patches rule + scripts/patch_toc.py)"
        )


def check(book_id: str, cfg: dict, doc: pymupdf.Document) -> int:
    toc = doc.get_toc()
    numbers = list_chapters(book_id, cfg, toc, load_readings(cfg["course"]))
    if not numbers:
        print(f"{book_id}: no chapters resolvable from the outline or reading list")
        return 1
    failures = 0
    for n in numbers:
        try:
            m = build_meta(doc, cfg, book_id, n)
        except SplitError as e:
            failures += 1
            print(f"FAIL ch{n:02d}: {e}")
            continue
        print(
            f"OK   {m['chapter']} pdf {m['pdf_pages']} printed {m['printed_pages']} "
            f"{len(m['sections']):2d} sections  {m['title'][:60]}"
        )
    print(f"{book_id}: {len(numbers)} chapters, {failures} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("book")
    ap.add_argument("--check", action="store_true", help="resolve every chapter in scope")
    ap.add_argument("--samples", type=int, default=6, help="sample titles per level")
    args = ap.parse_args(argv)
    try:
        cfg = book_cfg(args.book)
    except ConfigError as e:
        print(f"probe_toc: {e}", file=sys.stderr)
        return 1
    pdf = ROOT / cfg["pdf"]
    if not pdf.exists():
        print(f"probe_toc: {pdf} missing", file=sys.stderr)
        return 1
    doc = pymupdf.open(pdf)
    if args.check:
        return check(args.book, cfg, doc)
    evidence(args.book, cfg, doc, args.samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
