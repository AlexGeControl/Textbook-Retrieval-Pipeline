"""Stage 3 — text-layer guardrail (design §6).

Per page: PyMuPDF words (table / display-equation / chart / image regions masked) vs. every
text-bearing content_list_v2 block, both normalized to word tokens. Blocks whose tokens occur
contiguously anywhere in the page's PDF tokens are matched first (boxed examples, footnotes,
running heads and captions sit at different positions in the two orders); the residue is
word-diffed and every difference becomes a hunk anchored to a block. Hunks are data: exit 0.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from src.blocks import CAPTIONED, MASKED, TEXT_BEARING, Block, load_pages, v2_path
from src.config import ConfigError, chapter_number, work_dir
from src.extract import STEM, hybrid_auto_dir
from src.normalize import MD_RULES, PDF_RULES, flatten_latex, normalize, tokenize

CONTEXT = 3
MERGE_GAP = 2


class GuardrailError(Exception):
    pass


@dataclass(frozen=True)
class Tok:
    text: str
    block: str | None = None  # owning Block.id (md tokens)
    pos: int = -1  # index in the page's PDF token stream (pdf tokens)


@dataclass
class Alignment:
    residual_pdf: list[Tok]
    residual_md: list[Tok]
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)  # block id -> [start, end)


def block_masks(
    blocks: list[Block], page_rect: pymupdf.Rect, pad: float = 2.0
) -> list[pymupdf.Rect]:
    """Point-space rects of the VLM-body blocks: their glyphs are absent from the md side."""
    sx, sy = page_rect.width / 1000, page_rect.height / 1000
    return [
        pymupdf.Rect(b.bbox[0] * sx, b.bbox[1] * sy, b.bbox[2] * sx, b.bbox[3] * sy)
        + (-pad, -pad, pad, pad)
        for b in blocks
        if b.type in MASKED
    ]


def pdf_page_text(page: pymupdf.Page, masks: list[pymupdf.Rect]) -> str:
    """Words in PyMuPDF order: ' ' within a line, '\\n' between lines; masked words dropped."""
    parts: list[str] = []
    prev_line = None
    for x0, y0, x1, y1, word, block_no, line_no, _word_no in page.get_text("words"):
        centre = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if any(centre in m for m in masks):
            continue
        line = (block_no, line_no)
        if parts:
            parts.append(" " if line == prev_line else "\n")
        parts.append(word)
        prev_line = line
    return "".join(parts)


def pdf_tokens(text: str) -> list[Tok]:
    return [Tok(t, pos=i) for i, t in enumerate(tokenize(normalize(text, PDF_RULES)))]


def block_text(block: Block) -> str:
    """md-side text: body spans of a text-bearing block, caption spans of a captioned one.

    Inline-math spans are flattened to their glyphs. Spans are joined with a space because
    mineru puts none between a formula and the text that follows it.
    """
    if block.type in TEXT_BEARING:
        spans = block.spans
    elif block.type in CAPTIONED:
        spans = block.captions
    else:
        return ""
    return " ".join(
        flatten_latex(s.content) if s.type == "equation_inline" else s.content for s in spans
    )


def block_tokens(block: Block) -> list[Tok]:
    return [Tok(t, block.id) for t in tokenize(normalize(block_text(block), MD_RULES))]


def _find_free(hay: list[str], consumed: list[bool], needle: list[str], start: int) -> int:
    n = len(needle)
    for i in range(start, len(hay) - n + 1):
        if hay[i : i + n] == needle and not any(consumed[i : i + n]):
            return i
    return -1


def align_blocks(pdf: list[Tok], blocks: list[Block]) -> Alignment:
    """Match blocks that occur verbatim in the PDF stream, in reading order when possible."""
    texts = [t.text for t in pdf]
    consumed = [False] * len(pdf)
    aln = Alignment([], [])
    cursor = 0
    for b in blocks:
        toks = block_tokens(b)
        if not toks:
            continue
        needle = [t.text for t in toks]
        i = _find_free(texts, consumed, needle, cursor)
        if i < 0:
            i = _find_free(texts, consumed, needle, 0)
        if i < 0:
            aln.residual_md += toks
            continue
        consumed[i : i + len(needle)] = [True] * len(needle)
        aln.spans[b.id] = (i, i + len(needle))
        cursor = i + len(needle)
    aln.residual_pdf = [t for t, c in zip(pdf, consumed) if not c]
    return aln


def _merged_ranges(opcodes) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        if merged and i1 - merged[-1][1] <= MERGE_GAP:
            p = merged[-1]
            merged[-1] = (p[0], i2, p[2], j2)
        else:
            merged.append((i1, i2, j1, j2))
    return merged


def _anchor(
    md: list[Tok],
    j1: int,
    j2: int,
    pdf: list[Tok],
    i1: int,
    aln: Alignment,
    blocks: list[Block],
    page_idx: int,
) -> str:
    for tok in md[j1:j2]:
        if tok.block:
            return tok.block
    if i1 < len(pdf):  # pure deletion: the block matched just before this PDF position
        pos = pdf[i1].pos
        before = [(end, bid) for bid, (_start, end) in aln.spans.items() if end <= pos]
        if before:
            return max(before)[1]
    for tok in md[:j1][::-1]:
        if tok.block:
            return tok.block
    for b in blocks:
        if block_tokens(b):
            return b.id
    return f"p{page_idx:03d}-none"


def diff_page(
    pdf: list[Tok], blocks: list[Block], page_label: int, page_idx: int
) -> tuple[list[dict], Alignment]:
    aln = align_blocks(pdf, blocks)
    p, m = aln.residual_pdf, aln.residual_md
    sm = difflib.SequenceMatcher(None, [t.text for t in p], [t.text for t in m], autojunk=False)
    hunks = []
    for i1, i2, j1, j2 in _merged_ranges(sm.get_opcodes()):
        hunks.append(
            {
                "page": page_label,
                "anchor": _anchor(m, j1, j2, p, i1, aln, blocks, page_idx),
                "pdf_text": " ".join(t.text for t in p[max(0, i1 - CONTEXT) : i2 + CONTEXT]),
                "md_text": " ".join(t.text for t in m[max(0, j1 - CONTEXT) : j2 + CONTEXT]),
            }
        )
    return hunks, aln


def run(
    chapter_pdf: Path, hybrid_auto: Path, first_printed: int | None = None, stem: str = STEM
) -> dict:
    doc = pymupdf.open(chapter_pdf)
    pages = load_pages(v2_path(hybrid_auto, stem))
    if len(pages) != doc.page_count:
        raise GuardrailError(
            f"{hybrid_auto}: content_list_v2 has {len(pages)} pages, "
            f"{Path(chapter_pdf).name} has {doc.page_count}"
        )
    middle = json.loads((Path(hybrid_auto) / f"{stem}_middle.json").read_text())["pdf_info"]
    by_id = {b.id: b for pg in pages for b in pg}
    hunks: list[dict] = []
    counts = {
        "pdf_tokens": 0,
        "md_tokens": 0,
        "matched_blocks": 0,
        "unmatched_blocks": 0,
        "hunks": 0,
        "hunks_inline_math": 0,
    }
    for idx, page in enumerate(doc):
        w, h = middle[idx]["page_size"]
        if abs(w - page.rect.width) > 1 or abs(h - page.rect.height) > 1:
            raise GuardrailError(
                f"page {idx}: middle.json page_size {[w, h]} != PDF "
                f"{page.rect.width:.0f}x{page.rect.height:.0f}"
            )
        page_blocks = pages[idx]
        p = pdf_tokens(pdf_page_text(page, block_masks(page_blocks, page.rect)))
        label = first_printed + idx if first_printed is not None else idx
        page_hunks, aln = diff_page(p, page_blocks, label, idx)
        aligned = [b for b in page_blocks if block_tokens(b)]
        counts["pdf_tokens"] += len(p)
        counts["md_tokens"] += sum(len(block_tokens(b)) for b in aligned)
        counts["matched_blocks"] += len(aln.spans)
        counts["unmatched_blocks"] += len(aligned) - len(aln.spans)
        for hk in page_hunks:
            owner = by_id.get(hk["anchor"])
            if owner is not None and owner.inline_math():
                counts["hunks_inline_math"] += 1
            hunks.append(hk)
    counts["hunks"] = len(hunks)
    return {"pages": doc.page_count, "counts": counts, "hunks": hunks}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Stage 3: diff the PDF text layer against mineru's text-bearing blocks"
    )
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True, help="chapter number (5) or slug (ch05)")
    ap.add_argument("--show", type=int, default=20, help="print the first N hunks")
    args = ap.parse_args(argv)
    try:
        wd = work_dir(args.book, chapter_number(args.chapter))
        meta_path, pdf = wd / "meta.json", wd / "chapter.pdf"
        hybrid_auto = hybrid_auto_dir(wd)
        for needed in (meta_path, pdf, v2_path(hybrid_auto, STEM)):
            if not needed.exists():
                raise GuardrailError(f"{needed} missing — run split/extract first")
        meta = json.loads(meta_path.read_text())
        result = run(pdf, hybrid_auto, first_printed=meta["printed_pages"][0])
    except (GuardrailError, ConfigError) as e:
        print(f"guardrail: {e}", file=sys.stderr)
        return 1
    (wd / "guardrail.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    c = result["counts"]
    print(
        f"guardrail: {args.book} {meta['chapter']} {result['pages']} pages, "
        f"{c['pdf_tokens']}/{c['md_tokens']} tokens, "
        f"{c['matched_blocks']} blocks matched verbatim, {c['unmatched_blocks']} diffed, "
        f"{c['hunks']} hunks ({c['hunks_inline_math']} in inline-math blocks)"
    )
    per_page: dict[int, int] = {}
    for hk in result["hunks"]:
        per_page[hk["page"]] = per_page.get(hk["page"], 0) + 1
    print("  hunks per printed page: " + ", ".join(f"{p}:{n}" for p, n in sorted(per_page.items())))
    for hk in result["hunks"][: args.show]:
        print(
            f"  p{hk['page']} {hk['anchor']}\n    pdf: {hk['pdf_text']}\n    md : {hk['md_text']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
