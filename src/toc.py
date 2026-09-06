"""PDF-outline helpers shared by stage 1 (split) and the reading-list resolver.

`doc.get_toc()` is a flat, depth-first list `[[level, title, page_1based], ...]`; see the primer
in src/split.py. This module answers one question for every book layout: which outline
entries are chapters, and what number does each carry?
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

# "1.1 Applications" / "5-1: Review" -> chapter prefix 1 / 5
_SECTION_PREFIX = re.compile(r"^\s*(\d+)[-.]\d+\b")
# Anything that looks numbered, for the probe's per-level statistics only.
_NUMBERED_TITLE = re.compile(r"^\s*(?:chapter\s+)?\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class ChapterEntry:
    index: int  # position in toc
    number: int
    title: str  # chapter title with any leading number stripped


def children(toc: list[list], index: int) -> list[int]:
    """Indices of the direct children (level + 1) of toc[index]."""
    level = toc[index][0]
    out = []
    for j in range(index + 1, len(toc)):
        lvl = toc[j][0]
        if lvl <= level:
            break
        if lvl == level + 1:
            out.append(j)
    return out


def number_from_sections(toc: list[list], level: int) -> list[list]:
    """Normalizer: give unnumbered chapter titles at `level` the number of their first child.

    STATS: "Data and Statistics" with first child "1.1 Applications" -> "1: Data and Statistics".
    Entries already starting with a number, or without a numbered first child (Preface,
    "Chapter 1 Appendix"), are left alone. Positions are preserved, so toc indices stay valid.
    """
    out = [list(e) for e in toc]
    for i, (lvl, title, _page) in enumerate(toc):
        if lvl != level or _NUMBERED_TITLE.match(title):
            continue
        kids = children(toc, i)
        if kids and (m := _SECTION_PREFIX.match(toc[kids[0]][1])):
            out[i][1] = f"{int(m.group(1))}: {title.strip()}"
    return out


# New outline layout? Add a normalizer here and list it under toc.normalize in books.yaml.
# The parser below stays single-strategy: every layout is normalized to "number in the title".
NORMALIZERS = {"number_from_sections": number_from_sections}


def normalize_toc(toc: list[list], toc_cfg: dict) -> list[list]:
    """Apply toc.normalize steps in order (in memory; the book PDF is never modified)."""
    for name in toc_cfg.get("normalize") or []:
        if name not in NORMALIZERS:
            raise ValueError(f"toc.normalize: unknown step {name!r}; known: {sorted(NORMALIZERS)}")
        toc = NORMALIZERS[name](toc, toc_cfg["chapter_level"])
    return toc


def chapter_entries(toc: list[list], toc_cfg: dict) -> list[ChapterEntry]:
    """Chapters = entries at toc.chapter_level whose (normalized) title matches
    toc.chapter_pattern; group 1 is the chapter number. Unconfigured -> []."""
    level, pattern = toc_cfg.get("chapter_level"), toc_cfg.get("chapter_pattern")
    if level is None or pattern is None:
        return []
    rx = re.compile(pattern)
    out: list[ChapterEntry] = []
    for i, (lvl, title, _page) in enumerate(normalize_toc(toc, toc_cfg)):
        if lvl == level and (m := rx.search(title.strip())):
            out.append(ChapterEntry(i, int(m.group(1)), rx.sub("", title.strip(), count=1).strip()))
    return out


def level_stats(toc: list[list]) -> dict[int, tuple[int, int]]:
    """{level: (entries, entries whose title starts with a number)} — probe evidence."""
    stats: dict[int, list[int]] = {}
    for lvl, title, _page in toc:
        s = stats.setdefault(lvl, [0, 0])
        s[0] += 1
        s[1] += bool(_NUMBERED_TITLE.match(title))
    return {lvl: (c, n) for lvl, (c, n) in sorted(stats.items())}


def offset_candidates(doc: pymupdf.Document, first_idx: int, last_idx: int) -> Counter:
    """Counter of (pdf_1based - printed) over page-number-looking text in the page range.

    Accepts a standalone number line anywhere, or a number at the start/end of the first or
    last two text lines (running headers like "2  PART I Overview" / "CHAPTER 1 ... 3"). The
    most common value is the likely toc.page_offset when the PDF has no page labels.
    """
    counts: Counter = Counter()
    for idx in range(first_idx, min(last_idx, doc.page_count - 1) + 1):
        lines = [ln.strip() for ln in doc[idx].get_text().splitlines() if ln.strip()]
        found: set[int] = set()
        for ln in lines:
            if re.fullmatch(r"\d{1,4}", ln):
                found.add(int(ln))
        for ln in lines[:2] + lines[-2:]:
            for m in (re.match(r"(\d{1,4})\b", ln), re.search(r"\b(\d{1,4})$", ln)):
                if m:
                    found.add(int(m.group(1)))
        for n in found:
            counts[idx + 1 - n] += 1
    return counts
