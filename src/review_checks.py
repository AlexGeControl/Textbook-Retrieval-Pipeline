"""Mechanical checks that run before the reviewer reads anything (design §7, amended).

Writes review.blocks[*].checks, review.headings and review.footnotes. A section anchor that
cannot be found is a SectionError, which the CLI reports and exits 1 on: fix the outline first.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

import pymupdf
from lxml import html as lxml_html
from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError

from src import patches as patchmod
from src.blocks import Block
from src.config import ConfigError
from src.fold import fold, letters
from src.normalize import (
    MD_RULES,
    PDF_RULES,
    flatten_latex,
    normalize,
    punctuation_variants,
    tokenize,
)
from src.review import Chapter, ReviewError
from src.sections import (
    BODY_TYPES,
    SectionError,
    definition_marker,
    find_heading,
    references,
    resolve,
    subheading_entries,
)
from src.textlayer import Word, page_words, stream_text, words_in_bbox

_INLINE_MATH = re.compile(r"\$(?=\S)([^$]+?)(?<=\S)\$")  # `($)` in a cell is not math
_UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$")
_LEFT, _RIGHT = re.compile(r"\\left(?![A-Za-z])"), re.compile(r"\\right(?![A-Za-z])")
_DELIM = r"\s*(?:\\[A-Za-z]+|\\\S|[^\s\\A-Za-z])"  # ( [ \{ | . \langle after \left/\right
_LEFT_D, _RIGHT_D = re.compile(_LEFT.pattern + _DELIM), re.compile(_RIGHT.pattern + _DELIM)


def latex_ok(latex: str) -> tuple[bool, str]:
    if _UNESCAPED_DOLLAR.search(latex):
        return False, "unescaped $"  # before the parser, which would report an unclosed math mode
    try:
        LatexWalker(latex, tolerant_parsing=False).get_latex_nodes()
    except LatexWalkerParseError as e:
        return False, str(e).splitlines()[0]
    lefts, rights = len(_LEFT_D.findall(latex)), len(_RIGHT_D.findall(latex))
    if (
        lefts != rights
        or lefts != len(_LEFT.findall(latex))
        or rights != len(_RIGHT.findall(latex))
    ):
        return False, "\\left/\\right unbalanced"  # counts differ or a delimiter is missing
    if latex.count(r"\begin{") != latex.count(r"\end{"):
        return False, "\\begin/\\end unbalanced"
    return True, ""


def table_grid(html_text: str) -> tuple[int, int, bool]:
    """(rows, cols, rectangular) with colspan/rowspan honoured; empty HTML is (0, 0, False)."""
    if not html_text.strip():
        return 0, 0, False
    rows = lxml_html.fromstring(html_text).xpath(".//tr")
    if not rows:
        return 0, 0, False
    reserved: Counter = Counter()
    widths: list[int] = []
    for r_idx, tr in enumerate(rows):
        width = reserved[r_idx]
        for cell in tr.xpath("./td|./th"):
            cs = int(cell.get("colspan") or 1)
            for k in range(1, int(cell.get("rowspan") or 1)):
                reserved[r_idx + k] += cs
            width += cs
        widths.append(width)
    return len(rows), max(widths), len(set(widths)) == 1


def table_tokens(html_text: str) -> list[str]:
    tree = lxml_html.fromstring(html_text)
    for br in tree.xpath(".//br"):
        br.tail = " " + (br.tail or "")
    cells = " ".join(" ".join(td.text_content().split()) for td in tree.xpath(".//td|.//th"))
    text = _INLINE_MATH.sub(lambda m: f" {flatten_latex(m.group(1))} ", cells)
    return tokenize(normalize(text, MD_RULES))


def bag(tokens: list[str]) -> Counter:
    """Folded token multiset; U+2212 and the dashes map to `-` first, as the guardrail rules do."""
    return Counter(f for f in (fold(punctuation_variants(t)) for t in tokens) if f)


def table_textlayer(
    block: Block, words: list[Word], page_rect: pymupdf.Rect
) -> tuple[bool, list[str]]:
    if not block.html.strip():
        return False, []
    html_bag = bag(table_tokens(block.html))
    masked = stream_text(words_in_bbox(words, block.bbox, page_rect))
    pdf_bag = bag(tokenize(normalize(masked, PDF_RULES)))
    diff = sorted(((html_bag - pdf_bag) + (pdf_bag - html_bag)).elements())
    return not diff, diff


def formula_textlayer(
    block: Block, words: list[Word], page_rect: pymupdf.Rect, enabled: bool = True
) -> bool | None:
    if not enabled:
        return None
    masked = words_in_bbox(words, block.bbox, page_rect)
    if not masked:
        return None
    return letters(flatten_latex(block.math)) == letters(stream_text(masked))


def heading_report(ch: Chapter, pages: list[list[Block]], previous: dict | None = None) -> dict:
    sections = resolve(ch.meta, pages)  # SectionError names a missing section anchor
    keep = {m["title"]: m for m in (previous or {}).get("missing", [])}
    subs = subheading_entries(ch.meta)
    found = 0
    missing: list[dict] = []
    for title, pi in subs:
        try:
            hit = find_heading(pages[pi], title, None) if 0 <= pi < len(pages) else None
        except SectionError as e:
            hit, note = None, str(e)
        else:
            note = ""
        if hit is not None:
            found += 1
            continue
        old = keep.get(title)
        missing.append(
            old
            if old is not None
            else {
                "title": title,
                "page": ch.meta["printed_pages"][0] + pi,
                "kind": "subheading",
                "verdict": None,
                "block": None,
                "note": note,
            }
        )
    return {
        "sections": [len(sections) - 1, len(ch.meta["sections"])],
        "subheadings": [found, len(subs)],
        "missing": missing,
    }


def footnote_report(blocks: list[Block], previous: dict | None = None) -> dict:
    defs = [m for b in blocks if b.type == "page_footnote" for m in [definition_marker(b)] if m]
    refs = [n for b in blocks if b.type in BODY_TYPES for n in references(b)]
    keep = {u["id"]: u for u in (previous or {}).get("unmatched", [])}
    unmatched = [
        keep.get(n, {"id": n, "verdict": None, "note": ""})
        for n in sorted(set(defs) - set(refs), key=int)
    ]
    return {
        "definitions": len(defs),
        "references": len(refs),
        "unmatched": unmatched,
        "dangling": sorted(set(refs) - set(defs), key=int),
    }


def _pages(blocks: list[Block], n_pages: int) -> list[list[Block]]:
    pages: list[list[Block]] = [[] for _ in range(n_pages)]
    for b in blocks:
        pages[b.page_idx].append(b)
    return pages


def run(ch: Chapter) -> dict:
    review = ch.review
    blocks = ch.patched_blocks()
    by_id = {b.id: b for b in blocks}
    doc = pymupdf.open(ch.wd / "chapter.pdf")
    n_pages = ch.meta["pdf_pages"][1] - ch.meta["pdf_pages"][0] + 1
    pages = _pages(blocks, n_pages)
    words: dict[int, list[Word]] = {}
    math_enabled = ch.cfg.get("review", {}).get("textlayer_math", True)
    summary: Counter = Counter()
    for entry in review["blocks"]:
        b = by_id.get(entry["id"])
        checks = entry["checks"]
        for k in (
            "latex_parses",
            "rectangular",
            "rows",
            "cols",
            "textlayer_match",
            "textlayer_diff",
        ):
            checks[k] = None
        if b is None:
            continue  # dropped by a patch
        if b.page_idx not in words:
            words[b.page_idx] = page_words(doc[b.page_idx])
        rect = doc[b.page_idx].rect
        if b.type == "equation_interline":
            checks["latex_parses"] = latex_ok(b.math)[0]
            checks["textlayer_match"] = formula_textlayer(b, words[b.page_idx], rect, math_enabled)
            summary["formulas"] += 1
            summary["formulas_textlayer"] += checks["textlayer_match"] is True
            summary["formulas_parse"] += checks["latex_parses"]
        elif b.type == "table":
            rows, cols, rect_ok = table_grid(b.html)
            checks.update({"rows": rows, "cols": cols, "rectangular": rect_ok})
            ok, diff = table_textlayer(b, words[b.page_idx], rect)
            checks["textlayer_match"], checks["textlayer_diff"] = ok, diff
            summary["tables"] += 1
            summary["tables_textlayer"] += ok
            summary["tables_rectangular"] += rect_ok
            summary["tables_empty"] += not b.html.strip()
    review["headings"] = heading_report(ch, pages, review.get("headings"))
    review["footnotes"] = footnote_report(blocks, review.get("footnotes"))
    ch.save()
    summary["subheadings_missing"] = len(review["headings"]["missing"])
    summary["footnotes_unmatched"] = len(review["footnotes"]["unmatched"])
    return dict(summary)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 5: mechanical checks into qa_report.review")
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    args = ap.parse_args(argv)
    try:
        ch = Chapter(args.book, args.chapter)
        summary = run(ch)
    except (ReviewError, SectionError, ConfigError, patchmod.PatchError) as e:
        print(f"review-checks: {e}", file=sys.stderr)
        return 1
    print(f"review-checks: {args.book} ch{ch.number:02d} {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
