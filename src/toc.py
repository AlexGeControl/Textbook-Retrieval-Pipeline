"""PDF-outline helpers shared by stage 1 (split), the reading-list resolver and scripts/.

`doc.get_toc()` is a flat, depth-first list `[[level, title, page_1based], ...]`; see the primer
in src/split.py. Two jobs live here:

* chapter_entries(): which outline entries are chapters — one rule for every book: an entry at
  toc.chapter_level whose title matches toc.chapter_pattern (group 1 = chapter number).
* patch_toc(): the rules scripts/patch_toc.py applies ONCE to a book's PDF outline so that the
  single rule above holds. Outline quirks are fixed in the PDF, never at run time.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

# "1.1 Applications" / "5-1: Review" -> chapter prefix 1 / 5
_SECTION_PREFIX = re.compile(r"^\s*(\d+)[-.]\d+\b")
# "5.1" and nothing else: a section number the publisher split from its title (corpfin)
_NUMBER_ONLY = re.compile(r"^\s*(\d+[-.]\d+)\s*$")
# Anything that looks numbered, for the probe's per-level statistics only.
_NUMBERED_TITLE = re.compile(r"^\s*(?:chapter\s+)?\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class ChapterEntry:
    index: int  # position in toc
    number: int
    title: str  # chapter title with the leading number stripped


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


def chapter_entries(toc: list[list], toc_cfg: dict) -> list[ChapterEntry]:
    """Chapters = entries at toc.chapter_level whose title matches toc.chapter_pattern.

    Unconfigured (level or pattern null) -> []. Books whose outline does not fit this rule
    are patched once with scripts/patch_toc.py (toc.patches in books.yaml).
    """
    level, pattern = toc_cfg.get("chapter_level"), toc_cfg.get("chapter_pattern")
    if level is None or pattern is None:
        return []
    rx = re.compile(pattern)
    out: list[ChapterEntry] = []
    for i, (lvl, title, _page) in enumerate(toc):
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


# ---- outline patches (scripts/patch_toc.py) -----------------------------------------------------


class PatchError(Exception):
    pass


@dataclass(frozen=True)
class Change:
    level: int
    page: int  # 1-based, as in the outline
    old: str
    new: str


def _number_from_children(toc: list[list], level: int) -> tuple[list[list], list[Change]]:
    """Prefix "<N>: " to unnumbered titles at `level`, N = chapter prefix of the first child
    whose title matches ^\\d+[.-]\\d+. Entries without such a child are left alone."""
    out = [list(e) for e in toc]
    changes = []
    for i, (lvl, title, page) in enumerate(toc):
        if lvl != level or _NUMBERED_TITLE.match(title):
            continue
        prefix = next(
            (m.group(1) for j in children(toc, i) if (m := _SECTION_PREFIX.match(toc[j][1]))), None
        )
        if prefix is None:
            continue
        new = f"{int(prefix)}: {title.strip()}"
        out[i][1] = new
        changes.append(Change(lvl, page, title, new))
    return out, changes


def _merge_number_only_with_next(toc: list[list], level: int) -> tuple[list[list], list[Change]]:
    """Join a number-only entry ("5.1") at `level` with the next entry at the same level
    ("The Payback Period Method") into "5.1 The Payback Period Method"; the second entry is
    removed, its children stay (they now follow the merged entry)."""
    out: list[list] = []
    changes = []
    skip = -1
    for i, (lvl, title, page) in enumerate(toc):
        if i == skip:
            continue
        if lvl == level and (m := _NUMBER_ONLY.match(title)):
            j = i + 1
            if j < len(toc) and toc[j][0] == level and not _NUMBER_ONLY.match(toc[j][1]):
                new = f"{m.group(1)} {toc[j][1].strip()}"
                out.append([lvl, new, page])
                changes.append(Change(lvl, page, f"{title.strip()} | {toc[j][1].strip()}", new))
                skip = j
                continue
        out.append([lvl, title, page])
    return out, changes


def _rename(
    toc: list[list], level: int, match: str, replace: str
) -> tuple[list[list], list[Change]]:
    """re.sub(match, replace) on every title at `level` that matches; zero matches is an error
    so a typo in books.yaml cannot silently do nothing."""
    rx = re.compile(match)
    out = [list(e) for e in toc]
    changes = []
    hits = 0
    for i, (lvl, title, page) in enumerate(toc):
        if lvl != level or not rx.search(title):
            continue
        hits += 1
        new = rx.sub(replace, title, count=1)
        if new != title:
            out[i][1] = new
            changes.append(Change(lvl, page, title, new))
    if hits == 0:
        raise PatchError(f"rename {match!r} matched no level-{level} entries")
    return out, changes


RULES = {
    "number_from_children": _number_from_children,
    "merge_number_only_with_next": _merge_number_only_with_next,
    "rename": _rename,
}


def patch_toc(toc: list[list], patches: list[dict]) -> tuple[list[list], list[Change]]:
    """Apply toc.patches rules in order; returns (new toc, changes). Input is not mutated."""
    changes: list[Change] = []
    for spec in patches:
        spec = dict(spec)
        name = spec.pop("rule", None)
        if name not in RULES:
            raise PatchError(f"unknown rule {name!r}; known: {sorted(RULES)}")
        try:
            toc, made = RULES[name](toc, **spec)
        except TypeError as e:
            raise PatchError(f"rule {name}: bad arguments {spec}: {e}") from e
        changes += made
    return toc, changes
