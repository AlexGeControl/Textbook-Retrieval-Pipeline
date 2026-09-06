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
    note: str = (
        ""  # merged | merged, moved to chapter N | demoted to level L | unpaired id | inserted
    )


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


def _rebuild_numbered_sections(
    toc: list[list], level: int, id_pattern: str = r"(\d+)\.(\d+)"
) -> tuple[list[list], list[Change]]:
    """Rebuild sections at `level` whose numbers the publisher detached from their titles.

    The corpfin deviation: the outline stream at `level` reads "<title> <id>" with entry
    boundaries in the wrong places ("Taxes" | "2.3" | "Net Working Capital 2.4"), the first
    section of a chapter is hosted under the previous chapter ("Options 22.1" under Chapter 21),
    and a promoted subheading stands where the missing first section should be.

    1. Each `level` entry is split into a text token and id tokens (entries at other levels
       pass through untouched, so level+1 children keep following their section).
    2. A run of ids pairs with the tail of the run of titles right before it ("Bank Loans",
       "International Bonds", "15.4", "15.5"); earlier titles in the run are leftovers. A pair
       becomes one entry "<id> <title>" at the title's position and page; the id-only entry
       disappears. An entry that already reads "<id> <title>" is left alone.
    3. A merged section whose id chapter differs from its host chapter moves (with its
       trailing deeper entries) to just after the level-1 entry carrying that chapter number.
    4. Leftover text entries inside a chapter are demoted one level (they are subheadings or
       boxed features); leftovers outside any chapter, and ids nobody could pair, are left
       as-is and reported. Nothing is invented: a missing first section needs `insert`.
    """
    rx_id = re.compile(id_pattern)
    parent_level = level - 1

    def parent_number(title: str) -> int | None:
        m = re.search(r"\d+", title)
        return int(m.group()) if m else None

    # host chapter (parent index) of every entry
    host: list[int | None] = []
    cur: int | None = None
    for i, (lvl, _t, _p) in enumerate(toc):
        if lvl == parent_level:
            cur = i
        host.append(cur if lvl > parent_level else None)
    parents_by_number = {
        parent_number(t): i for i, (lvl, t, _p) in enumerate(toc) if lvl == parent_level
    }

    # tokens: ["other", toc index] | ["text", text, page, host, toc index] | ["id", id, page, host, toc index]
    tokens: list[list] = []
    for i, (lvl, title, page) in enumerate(toc):
        if lvl != level:
            tokens.append(["other", i])
            continue
        ids = [f"{m.group(1)}.{m.group(2)}" for m in rx_id.finditer(title)]
        text = re.sub(r"\s+", " ", rx_id.sub(" ", title)).strip()
        if text:
            tokens.append(["text", text, page, host[i], i])
        for sid in ids:
            tokens.append(["id", sid, page, host[i], i])

    # Pair each run of ids with the tail of the run of texts right before it: "Bank Loans",
    # "International Bonds", "15.4", "15.5" -> 15.4 Bank Loans, 15.5 International Bonds;
    # "THE FINANCIAL MANAGER", "The Corporate Firm", "1.2" -> 1.2 The Corporate Firm and the
    # earlier title is a leftover. Ids beyond the available texts stay unpaired.
    pair: dict[int, int] = {}  # id token index -> text token index
    used: set[int] = set()
    text_run: list[int] = []
    id_run: list[int] = []

    def flush() -> None:
        n = min(len(text_run), len(id_run))
        for t, k in zip(text_run[len(text_run) - n :], id_run[:n]):
            pair[k] = t
            used.add(t)
        text_run.clear()
        id_run.clear()

    for k, tok in enumerate(tokens):
        if tok[0] == "text":
            if id_run:
                flush()
            text_run.append(k)
        elif tok[0] == "id":
            id_run.append(k)
    flush()
    title_of: dict[int, str] = {t: tokens[k][1] for k, t in pair.items()}
    id_entry_of: dict[int, int] = {t: tokens[k][4] for k, t in pair.items()}

    out: list[list] = []
    changes: list[Change] = []
    moves: list[tuple[int, int]] = []  # (out index, target parent toc index)
    for k, tok in enumerate(tokens):
        if tok[0] == "other":
            out.append(list(toc[tok[1]]))
        elif tok[0] == "text":
            _, text, page, h, entry = tok
            in_chapter = h is not None and parent_number(toc[h][1]) is not None
            if k in used:
                sid = title_of[k]
                new_title = f"{sid} {text}"
                out.append([level, new_title, page])
                target = parents_by_number.get(int(sid.split(".")[0]))
                note = "merged"
                if target is not None and target != h:
                    moves.append((len(out) - 1, target))
                    note = f"merged, moved to chapter {sid.split('.')[0]}"
                same_entry = id_entry_of[k] == entry
                if not (same_entry and toc[entry][1].strip() == new_title and "moved" not in note):
                    old = text if same_entry else f"{text} | {sid}"
                    changes.append(
                        Change(
                            level,
                            page,
                            toc[entry][1].strip() if same_entry else old,
                            new_title,
                            note,
                        )
                    )
            elif in_chapter:
                out.append([level + 1, text, page])
                changes.append(Change(level, page, text, text, f"demoted to level {level + 1}"))
            else:
                out.append([level, text, page])
        else:  # id
            if k in pair:
                continue
            out.append([level, tok[1], tok[2]])
            changes.append(Change(level, tok[2], tok[1], tok[1], "unpaired id"))

    # re-parent: move [entry + following deeper entries] to just after the target parent entry
    for out_idx, target_toc_idx in sorted(moves, reverse=True):
        end = out_idx + 1
        while end < len(out) and out[end][0] > level:
            end += 1
        block = out[out_idx:end]
        del out[out_idx:end]
        target_entry = toc[target_toc_idx]
        t = next(i for i, e in enumerate(out) if e == target_entry)
        out[t + 1 : t + 1] = block
    return out, changes


def _insert(
    toc: list[list], level: int, title: str, page: int, after: dict
) -> tuple[list[list], list[Change]]:
    """Insert [level, title, page] right after the single entry matching `after`
    ({level, match}); zero or several matches is an error."""
    rx = re.compile(after["match"])
    hits = [i for i, (lvl, t, _p) in enumerate(toc) if lvl == after["level"] and rx.search(t)]
    if len(hits) != 1:
        raise PatchError(
            f"insert {title!r}: after={after} matched {len(hits)} entries, need exactly 1"
        )
    out = [list(e) for e in toc]
    out.insert(hits[0] + 1, [level, title, page])
    return out, [Change(level, page, "", title, "inserted")]


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
    "rebuild_numbered_sections": _rebuild_numbered_sections,
    "insert": _insert,
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
