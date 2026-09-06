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


def _chapter_matcher(cfg: dict, book_id: str) -> tuple[int, re.Pattern]:
    level = cfg["toc"].get("chapter_level")
    pattern = cfg["toc"].get("chapter_pattern")
    if level is None or pattern is None:
        raise SplitError(
            f"{book_id}: toc.chapter_level / toc.chapter_pattern not set in config/books.yaml"
        )
    return level, re.compile(pattern)


def _strip_number(rx: re.Pattern, title: str) -> str:
    return rx.sub("", title.strip(), count=1).strip()


def resolve_chapter(
    toc: list[list], cfg: dict, book_id: str, number: int, page_count: int
) -> ChapterRange:
    slug = chapter_slug(number)
    level, rx = _chapter_matcher(cfg, book_id)
    matches = [
        i
        for i, (lvl, title, _page) in enumerate(toc)
        if lvl == level and (m := rx.search(title.strip())) and int(m.group(1)) == number
    ]
    override = (cfg.get("chapter_ranges") or {}).get(slug)
    if override:
        first, last = int(override[0]), int(override[1])
        title = _strip_number(rx, toc[matches[0]][1]) if len(matches) == 1 else f"Chapter {number}"
        return ChapterRange(
            number, slug, title, first, last, matches[0] if len(matches) == 1 else None
        )
    if not toc:
        raise SplitError(
            f"{book_id} {slug}: PDF has no outline and no chapter_ranges[{slug}] in books.yaml"
        )
    if not matches:
        raise SplitError(
            f"{book_id} {slug}: no level-{level} outline entry matches {rx.pattern!r} "
            f"with number {number}"
        )
    if len(matches) > 1:
        titles = "; ".join(toc[i][1] for i in matches)
        raise SplitError(f"{book_id} {slug}: {len(matches)} outline entries match: {titles}")
    i = matches[0]
    first = toc[i][2] - 1
    next_start = next(
        (toc[j][2] - 1 for j in range(i + 1, len(toc)) if toc[j][0] <= level), page_count
    )
    last = next_start - 1
    if not 0 <= first <= last < page_count:
        raise SplitError(
            f"{book_id} {slug}: outline gives pages {first}..{last}, PDF has 0..{page_count - 1}"
        )
    return ChapterRange(number, slug, _strip_number(rx, toc[i][1]), first, last, i)


def printed_page(doc: pymupdf.Document, idx: int, cfg: dict, book_id: str) -> int:
    label = doc[idx].get_label().strip()
    if label.isdigit():
        return int(label)
    offset = cfg["toc"].get("page_offset")
    if offset is not None:
        return idx + 1 - int(offset)
    raise SplitError(
        f"{book_id}: page index {idx} has no numeric page label and toc.page_offset is null in "
        "books.yaml — set it (printed = pdf_1based - page_offset)"
    )


def subtree(toc: list[list], rng: ChapterRange, level: int) -> list[list]:
    """[[level, title, pdf_page0], ...] for outline entries inside the chapter below `level`."""
    if rng.toc_index is None:
        return []
    out = []
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
    toc = doc.get_toc()
    rng = resolve_chapter(toc, cfg, book_id, number, doc.page_count)
    level, _rx = _chapter_matcher(cfg, book_id)
    tree = subtree(toc, rng, level)
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
        cfg = book_cfg(args.book)
        number = chapter_number(args.chapter)
        pdf = ROOT / cfg["pdf"]
        if not pdf.exists():
            raise SplitError(f"{args.book}: {cfg['pdf']} missing — see books/README.md")
        doc = pymupdf.open(pdf)
        meta = build_meta(doc, cfg, args.book, number)
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
