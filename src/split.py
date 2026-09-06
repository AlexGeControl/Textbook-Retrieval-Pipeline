"""Stage 1 — chapter splitter (design §4).

Resolves a chapter's page range from the PDF outline (or a chapter_ranges override), writes
work/<book>/<chNN>/chapter.pdf and meta.json. Never guesses: every unresolved case raises
SplitError naming book and chapter.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from src.config import ROOT, ConfigError, book_cfg, chapter_number, chapter_slug, work_dir
from src.toc import chapter_entries

# ---------------------------------------------------------------------------------------------
# PyMuPDF TOC primer (the data structure everything below walks)
#
#   toc = doc.get_toc()   ->   [[level, title, page], ...]
#
# * It is the PDF's *outline* (the bookmark sidebar), read from the /Outlines tree; it is not
#   derived from the page text. If the publisher shipped no outline, get_toc() returns [].
# * The list is FLAT but ordered depth-first, exactly as the sidebar shows it. Hierarchy is
#   implied by `level`: a child directly follows its parent with level+1, and the next entry
#   whose level is <= L closes every open node at level >= L. So "the subtree of entry i" is
#   simply the run of entries after i until the first entry with level <= toc[i][0].
# * `level` starts at 1 (top of the sidebar). Publishers differ: BMA/BKM put Parts at 1 and
#   chapters at 2; OPS puts chapters at 1. That is why config carries toc.chapter_level.
# * `page` is 1-BASED (sidebar convention); PyMuPDF page indices (doc[i], insert_pdf) are
#   0-based, hence the `- 1` wherever a TOC page becomes an index. page can be 0/-1 for an
#   entry without a destination; such books would need chapter_ranges.
# * An outline entry marks where something STARTS. Its end is "the page before the next entry
#   at the same or a shallower level" — a chapter ends where the next chapter or next Part
#   begins; the last chapter runs to the end of the document.
# * Printed page numbers are a separate PDF feature (/PageLabels, read via page.get_label()):
#   "119" for body pages, "xi" for front matter, "" when the publisher set none. The outline
#   never carries them, so meta.json records both the 0-based index and the printed label.
# * get_toc(simple=True) (the default) drops the 4th element, a dict with the exact
#   destination on the page; we never need sub-page precision.
# ---------------------------------------------------------------------------------------------

# Leading "5-1" / "1.1" token in a section title (BMA uses "-", BKM/STATS use ".").
SECTION_NUMBER = re.compile(r"^\s*(\d+[-.]\d+)\s*:?\s*")


class SplitError(Exception):
    pass


@dataclass(frozen=True)
class ChapterRange:
    number: int
    slug: str
    title: str
    first: int  # 0-based, inclusive
    last: int
    toc_index: int | None  # index of the chapter's own outline entry, None for overrides


@dataclass(frozen=True)
class Section:
    number: str | None
    title: str
    pdf_page: int
    printed_page: int
    level: int


def _chapter_level(cfg: dict, book_id: str) -> int:
    toc_cfg = cfg["toc"]
    if toc_cfg.get("chapter_level") is None or toc_cfg.get("chapter_pattern") is None:
        raise SplitError(
            f"{book_id}: toc.chapter_level / toc.chapter_pattern not set in config/books.yaml "
            "(unnumbered chapter titles: fix the outline once with scripts/patch_toc.py)"
        )
    return toc_cfg["chapter_level"]


def resolve_chapter(
    toc: list[list], cfg: dict, book_id: str, number: int, page_count: int
) -> ChapterRange:
    slug = chapter_slug(number)
    level = _chapter_level(cfg, book_id)
    # Matching criteria: an outline entry at the chapter level whose (normalized) title matches
    # toc.chapter_pattern with group 1 == number. Outline quirks are fixed once in the PDF by
    # scripts/patch_toc.py (toc.patches), never handled here.
    matches = [e for e in chapter_entries(toc, cfg["toc"]) if e.number == number]
    # If override is provided, use override instead as shortcut
    override = (cfg.get("chapter_ranges") or {}).get(slug)
    if override:
        first, last = int(override[0]), int(override[1])
        title = matches[0].title if len(matches) == 1 else f"Chapter {number}"
        return ChapterRange(
            number, slug, title, first, last, matches[0].index if len(matches) == 1 else None
        )
    if not toc:
        raise SplitError(
            f"{book_id} {slug}: PDF has no outline and no chapter_ranges[{slug}] in books.yaml"
        )
    if not matches:
        raise SplitError(
            f"{book_id} {slug}: no level-{level} outline entry matches "
            f"{cfg['toc']['chapter_pattern']!r} with number {number}"
        )
    if len(matches) > 1:
        titles = "; ".join(toc[e.index][1] for e in matches)
        raise SplitError(f"{book_id} {slug}: {len(matches)} outline entries match: {titles}")
    i = matches[0].index
    # The chapter starts on its own entry's page (TOC pages are 1-based -> index with -1).
    first = toc[i][2] - 1
    # It ends just before the next entry at the chapter level or shallower (next chapter, or
    # the next Part header). No such entry => last chapter, runs to the end of the document.
    next_start = next(
        (toc[j][2] - 1 for j in range(i + 1, len(toc)) if toc[j][0] <= level), page_count
    )
    last = next_start - 1
    if not 0 <= first <= last < page_count:
        raise SplitError(
            f"{book_id} {slug}: outline gives pages {first}..{last}, PDF has 0..{page_count - 1}"
        )
    return ChapterRange(number, slug, matches[0].title, first, last, i)


def printed_page(doc: pymupdf.Document, idx: int, cfg: dict, book_id: str) -> int:
    # Preferred: the PDF's own page label (/PageLabels). Body pages label as "119"; front
    # matter labels as roman numerals or "" — those are not digits and fall through.
    label = doc[idx].get_label().strip()
    if label.isdigit():
        return int(label)
    # Fallback: a constant offset measured once per book (printed = pdf_1based - offset).
    offset = cfg["toc"].get("page_offset")
    if offset is not None:
        return idx + 1 - int(offset)
    raise SplitError(
        f"{book_id}: page index {idx} has no numeric page label and toc.page_offset is null in "
        "books.yaml — set it (printed = pdf_1based - page_offset)"
    )


def subtree(toc: list[list], rng: ChapterRange, level: int) -> list[list]:
    """[[level, title, pdf_page0], ...] for outline entries inside the chapter below `level`."""
    # A chapter resolved purely from chapter_ranges has no outline entry to hang a subtree on,
    # so it has no sections either (see design §4); fix the outline with scripts/patch_toc.py instead.
    if rng.toc_index is None:
        return []
    out = []
    # Depth-first flat list: everything after the chapter entry belongs to it until the first
    # entry that is as shallow as the chapter itself. Levels level+1 are sections, level+2
    # subsections, etc.; all of them are kept for stage-5 heading verification.
    for lvl, title, page in toc[rng.toc_index + 1 :]:
        if lvl <= level:
            break
        out.append([lvl, title, page - 1])
    return out


def _section(entry: list, doc: pymupdf.Document, cfg: dict, book_id: str) -> Section:
    lvl, title, pdf_page = entry
    m = SECTION_NUMBER.match(title)
    number = m.group(1) if m else None
    clean = title[m.end() :].strip() if m else title.strip()
    return Section(number, clean, pdf_page, printed_page(doc, pdf_page, cfg, book_id), lvl)


def build_meta(doc: pymupdf.Document, cfg: dict, book_id: str, number: int) -> dict:
    # Returns the PDF's outline (the bookmark sidebar), not anything derived from page text.
    # A flat list [[level, title, page], …] in depth-first sidebar order.
    # Empty list if the publisher shipped no outline.
    toc = doc.get_toc()
    # Get the chapter range
    rng = resolve_chapter(toc, cfg, book_id, number, doc.page_count)
    level = _chapter_level(cfg, book_id)
    tree = subtree(toc, rng, level)
    # Sections = the chapter's direct children (level + 1). Deeper entries stay in toc_subtree
    # only; the per-section note split in stage 5b uses `sections`.
    sections = [_section(e, doc, cfg, book_id) for e in tree if e[0] == level + 1]

    return {
        "book": book_id,
        "chapter": rng.slug,
        "number": number,
        "title": rng.title,
        "pdf_pages": [rng.first, rng.last],
        "printed_pages": [
            printed_page(doc, rng.first, cfg, book_id),
            printed_page(doc, rng.last, cfg, book_id),
        ],
        "sections": [asdict(s) for s in sections],
        "toc_subtree": tree,
    }


def write_chapter(doc: pymupdf.Document, meta: dict, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    first, last = meta["pdf_pages"]
    chapter = pymupdf.open()
    chapter.insert_pdf(doc, from_page=first, to_page=last)
    pdf = out_dir / "chapter.pdf"
    chapter.save(pdf)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return pdf


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1: cut one chapter out of a book PDF")
    ap.add_argument("--book", required=True, help="book id from config/books.yaml")
    ap.add_argument("--chapter", required=True, help="chapter number (5) or slug (ch05)")
    args = ap.parse_args(argv)
    try:
        # Parse books config from config/books.yaml.
        cfg = book_cfg(args.book)
        # Normalize target chapter.
        number = chapter_number(args.chapter)
        # Open the book PDF.
        pdf = ROOT / cfg["pdf"]
        if not pdf.exists():
            raise SplitError(f"{args.book}: {cfg['pdf']} missing — see books/README.md")
        #
        # Build per-chapter meta.json and excerpt
        # Using deterministic PyML PDF
        #
        # Prepare the document for processing
        doc = pymupdf.open(pdf)
        # Build the chapter metadata
        meta = build_meta(doc, cfg, args.book, number)
        # Write the chapter to disk
        out = write_chapter(doc, meta, work_dir(args.book, number))
    except (SplitError, ConfigError) as e:
        print(f"split: {e}", file=sys.stderr)
        return 1
    print(
        f"split: {args.book} {meta['chapter']} '{meta['title']}' pdf pages {meta['pdf_pages']} "
        f"(printed {meta['printed_pages']}), {len(meta['sections'])} sections -> {out.parent}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
