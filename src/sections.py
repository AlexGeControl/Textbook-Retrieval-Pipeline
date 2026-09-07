"""Section slicing over patched blocks (design §9, amended 2026-09-07).

Anchors: (1) a run of up to four consecutive text-bearing blocks whose folded text equals the
section title, number+title or title+number — exact case preferred, then `title` type, then
the shorter run; running-matter suspects count (acct types a section title `page_header`);
(2) the section's first toc_subtree child printed on the same page; (3) for the first section
on the chapter's first page, the first body block after the chapter title. Anything else fails
naming the section and page: fix the outline with config/books.yaml toc.patches and re-split.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.blocks import TEXT_BEARING, Block
from src.fold import clean_title, fold

MAX_RUN = 4
BODY_TYPES = frozenset(
    {"paragraph", "list", "title", "page_aside_text", "page_header", "page_footer"}
)
_DEF = re.compile(r"^\s*<sup>\s*(\d+)\s*</sup>")
_REF = re.compile(r"<sup>\s*(\d+)\s*</sup>")
_STAR = re.compile(r"^\s*[*†‡]")


class SectionError(Exception):
    pass


@dataclass
class Chain:
    marker: str | None  # footnote number; None for a star or otherwise unmarked chain
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Section:
    ordinal: int  # 0 = hub / preamble, then meta.sections order
    number: str | None
    title: str
    page_idx: int
    anchor: str | None = None
    heading_blocks: tuple[str, ...] = ()  # consumed as the heading, not rendered as body
    rule: str = ""
    blocks: list[Block] = field(default_factory=list)
    footnotes: list[Chain] = field(default_factory=list)
    printed_pages: tuple[int, int] = (0, 0)


def printed_page(meta: dict, page_idx: int) -> int:
    return meta["printed_pages"][0] + page_idx


def heading_forms(title: str, number: str | None) -> set[str]:
    t = clean_title(title)
    forms = {fold(t)}
    if number:
        forms |= {fold(f"{number} {t}"), fold(f"{t} {number}")}
    return {f for f in forms if f}


def _exact_forms(title: str, number: str | None) -> set[str]:
    t = clean_title(title)
    forms = {t}
    if number:
        forms |= {f"{number} {t}", f"{number}: {t}", f"{t} {number}", f"{t}{number}"}
    return forms


def find_heading(page_blocks: list[Block], title: str, number: str | None) -> list[Block] | None:
    forms, exact = heading_forms(title, number), _exact_forms(title, number)
    text_blocks = [b for b in page_blocks if b.type in TEXT_BEARING]
    cands: list[tuple[tuple[int, int, int], list[Block]]] = []
    for i in range(len(text_blocks)):
        run: list[Block] = []
        for j in range(i, min(len(text_blocks), i + MAX_RUN)):
            b = text_blocks[j]
            if run and b.index != run[-1].index + 1:
                break
            run.append(b)
            joined = " ".join(clean_title(x.text()) for x in run)
            if fold(joined) in forms:
                score = (
                    0 if all(x.type == "title" for x in run) else 1,
                    0 if joined in exact else 1,
                    len(run),
                )
                cands.append((score, list(run)))
                break
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    best = [run for score, run in cands if score == cands[0][0]]
    if len(best) > 1:
        ids = [run[0].id for run in best]
        raise SectionError(f"heading {title!r} is ambiguous on page {best[0][0].page_idx}: {ids}")
    return best[0]


def definition_marker(block: Block) -> str | None:
    m = _DEF.match(block.text())
    return m.group(1) if m else None


def references(block: Block) -> list[str]:
    """Footnote numbers a body block references: <sup>n</sup> not preceded by a digit or ')'."""
    text = block.text()
    out: list[str] = []
    for m in _REF.finditer(text):
        prev = text[m.start() - 1] if m.start() else ""
        if not (prev.isdigit() or prev in ")]"):
            out.append(m.group(1))
    return out


def _section_level(meta: dict) -> int | None:
    levels = [e[0] for e in meta.get("toc_subtree", [])]
    return min(levels) if levels else None


def subheading_entries(meta: dict) -> list[tuple[str, int]]:
    """(title, page_idx) of every toc_subtree entry one level below the sections."""
    lvl = _section_level(meta)
    if lvl is None:
        return []
    first = meta["pdf_pages"][0]
    return [(clean_title(t), p - first) for level, t, p in meta["toc_subtree"] if level == lvl + 1]


def _first_child(meta: dict, entry: dict) -> tuple[str, int] | None:
    lvl = _section_level(meta)
    if lvl is None:
        return None
    first = meta["pdf_pages"][0]
    forms = heading_forms(entry["title"], entry.get("number"))
    tree = meta["toc_subtree"]
    for i, (level, t, _p) in enumerate(tree):
        if level == lvl and fold(t) in forms:
            for level2, t2, p2 in tree[i + 1 :]:
                if level2 <= lvl:
                    break
                if level2 == lvl + 1:
                    return clean_title(t2), p2 - first
            return None
    return None


def _after_chapter_title(page: list[Block]) -> Block | None:
    seen_title = False
    for b in page:
        if b.type == "title" and b.level == 1:
            seen_title = True
            continue
        if seen_title and b.type in TEXT_BEARING and b.text().strip():
            return b
    return None


def resolve(meta: dict, pages: list[list[Block]]) -> list[Section]:
    first = meta["pdf_pages"][0]
    where = f"{meta['book']} {meta['chapter']}"
    sections = [Section(0, None, clean_title(meta["title"]), 0)]
    for k, e in enumerate(meta["sections"], start=1):
        title, number = clean_title(e["title"]), e.get("number")
        pi = e["pdf_page"] - first
        if not 0 <= pi < len(pages):
            raise SectionError(
                f"{where}: section {title!r} starts on pdf page {e['pdf_page']}, outside the chapter"
            )
        hit, rule = find_heading(pages[pi], title, number), "heading"
        if hit is None:
            child = _first_child(meta, e)
            if child is not None and child[1] == pi:
                hit, rule = find_heading(pages[pi], child[0], None), "first_child"
        if hit is None and k == 1 and pi == 0:
            start = _after_chapter_title(pages[0])
            if start is not None:
                sections.append(Section(k, number, title, pi, start.id, (), "chapter_start"))
                continue
        if hit is None:
            raise SectionError(
                f"{where}: section {(number + ' ') if number else ''}{title!r} has no heading on "
                f"pdf page {e['pdf_page']} (chapter page {pi}); fix the outline with "
                "config/books.yaml toc.patches (rename/insert) and re-run make split"
            )
        consumed = (
            tuple(b.id for b in hit) if rule == "heading" else ()
        )  # a first-child heading stays
        sections.append(Section(k, number, title, pi, hit[0].id, consumed, rule))
    _slice(sections, pages, where)
    _footnotes(sections)
    for s in sections:
        idx = [b.page_idx for b in s.blocks] + ([s.page_idx] if s.ordinal else [])
        if idx:
            s.printed_pages = (printed_page(meta, min(idx)), printed_page(meta, max(idx)))
    return sections


def _slice(sections: list[Section], pages: list[list[Block]], where: str) -> None:
    anchors = {s.anchor: s for s in sections[1:]}
    consumed = {bid for s in sections[1:] for bid in s.heading_blocks}
    current = sections[0]
    seen = 0
    for page in pages:
        for b in page:
            if b.id in anchors:
                current = anchors[b.id]
                if current.ordinal != seen + 1:
                    raise SectionError(
                        f"{where}: section {current.title!r} appears out of outline order"
                    )
                seen += 1
            if b.id in consumed or (current.ordinal == 0 and b.type == "title" and b.level == 1):
                continue
            current.blocks.append(b)
    if seen != len(sections) - 1:
        raise SectionError(
            f"{where}: only {seen} of {len(sections) - 1} section anchors were reached"
        )


def _footnotes(sections: list[Section]) -> None:
    chains: list[tuple[Chain, Section]] = []  # (chain, section holding its first block)
    for s in sections:
        kept: list[Block] = []
        for b in s.blocks:
            if b.type != "page_footnote":
                kept.append(b)
                continue
            marker = definition_marker(b)
            if marker is not None or _STAR.match(b.text()) or not chains:
                chains.append((Chain(marker, [b]), s))
            else:
                chains[-1][0].blocks.append(b)
        s.blocks = kept
    ref_section: dict[str, Section] = {}
    for s in sections:
        for b in s.blocks:
            if b.type in BODY_TYPES:
                for n in references(b):
                    ref_section.setdefault(n, s)
    for chain, home in chains:
        target = ref_section.get(chain.marker, home) if chain.marker else home
        target.footnotes.append(chain)
