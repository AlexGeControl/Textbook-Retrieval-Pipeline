"""Block model over MinerU's <stem>_content_list_v2.json (design §6, amended 2026-09-06).

content_list_v2 is the anchor for stages 3-5: one list per page (a blank page is an empty
list), typed blocks with a bbox (0-1000 per axis) and nested `content`. Running text arrives as
spans (`text` | `equation_inline` | `phonetic`), so inline math is never parsed out of markdown
and text spans are unescaped; headings carry `level`; every VLM-generated body (table, display
equation, chart, image content) points at its crop under images/. This module only reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Text-layer blocks. Every one is aligned against the PDF text layer; nothing is dropped by type,
# because on reflowed e-books (acct, ops) mineru labels body text page_header / page_footer.
TEXT_BEARING = frozenset(
    {
        "paragraph",
        "title",
        "list",
        "page_footnote",
        "page_aside_text",
        "page_header",
        "page_footer",
        "page_number",
    }
)
# Running heads, feet and folios: aligned like any text; stage 4 flags the ones whose text is
# not running matter (a heading or sentence the layout model mislabeled) so stage 5 keeps them.
RUNNING_MATTER = frozenset({"page_header", "page_footer", "page_number"})
# Bodies written by the VLM/MFR, reviewed against their crop. An `image` joins when it carries
# `content` (flowchart -> mermaid, text_image -> transcription): see Block.is_vlm_generated().
VLM_GENERATED = frozenset({"table", "equation_interline", "chart"})
FIGURES = frozenset({"image", "chart"})
# Blocks whose caption/footnote spans are text-layer prose around a non-text body.
CAPTIONED = frozenset({"table", "chart", "image"})
# Regions whose text-layer glyphs are deliberately absent from the md side: masked on the PDF side.
MASKED = frozenset({"table", "equation_interline", "chart", "image"})
# v2 type -> qa_report flagged_blocks.type
SCHEMA_TYPE = {
    "table": "table",
    "equation_interline": "formula",
    "chart": "chart",
    "image": "figure",
}


class BlockError(Exception):
    pass


def block_id(page_idx: int, index: int) -> str:
    return f"p{page_idx:03d}-b{index:03d}"


def v2_path(hybrid_auto: Path, stem: str) -> Path:
    return Path(hybrid_auto) / f"{stem}_content_list_v2.json"


@dataclass(frozen=True)
class Span:
    type: str  # text | equation_inline | phonetic
    content: str


NEWLINE = Span("text", "\n")  # separates list items and caption from footnote


@dataclass(frozen=True)
class Block:
    id: str
    index: int  # position in the page's list
    type: str  # content_list_v2 type
    page_idx: int
    bbox: tuple[int, int, int, int]  # 0-1000 per axis
    spans: tuple[Span, ...] = ()  # body of a TEXT_BEARING block, list items NEWLINE-separated
    captions: tuple[Span, ...] = ()  # *_caption NEWLINE *_footnote spans of a CAPTIONED block
    level: int | None = None  # title level
    math: str = ""  # equation_interline LaTeX, no delimiters
    html: str = ""  # table body
    content: str = ""  # VLM content: chart data table, image mermaid / transcription
    crop: str = ""  # image_source.path, relative to hybrid_auto/
    sub_type: str | None = None  # image/chart sub_type, list_type, table_type

    def text(self) -> str:
        """Text spans of the body joined as written; inline math omitted (see inline_math)."""
        return "".join(s.content for s in self.spans if s.type == "text")

    def caption_text(self) -> str:
        return "".join(s.content for s in self.captions if s.type == "text")

    def inline_math(self) -> tuple[str, ...]:
        return tuple(
            s.content for s in (*self.spans, *self.captions) if s.type == "equation_inline"
        )

    def is_vlm_generated(self) -> bool:
        return self.type in VLM_GENERATED or (self.type == "image" and bool(self.content.strip()))


def _spans(raw: list[dict]) -> tuple[Span, ...]:
    return tuple(Span(s["type"], s["content"]) for s in raw if s.get("content"))


def _joined(groups: list[list[dict]]) -> tuple[Span, ...]:
    out: list[Span] = []
    for group in groups:
        spans = _spans(group)
        if spans:
            if out:
                out.append(NEWLINE)
            out += spans
    return tuple(out)


def _block(raw: dict, page_idx: int, index: int) -> Block:
    t, c = raw.get("type"), raw.get("content") or {}
    where = f"content_list_v2 p{page_idx} block {index}"
    if "bbox" not in raw:
        raise BlockError(f"{where}: no bbox")
    common = {
        "id": block_id(page_idx, index),
        "index": index,
        "type": t,
        "page_idx": page_idx,
        "bbox": tuple(round(v) for v in raw["bbox"]),
        "sub_type": raw.get("sub_type"),
    }
    if t == "paragraph":
        return Block(**common, spans=_spans(c.get("paragraph_content", [])))
    if t == "title":
        return Block(**common, spans=_spans(c.get("title_content", [])), level=c.get("level"))
    if t == "list":
        items = [item.get("item_content", []) for item in c.get("list_items", [])]
        return Block(**common | {"sub_type": c.get("list_type")}, spans=_joined(items))
    if t in RUNNING_MATTER or t in ("page_footnote", "page_aside_text"):
        return Block(**common, spans=_spans(c.get(f"{t}_content", [])))
    crop = (c.get("image_source") or {}).get("path", "")
    if t == "equation_interline":
        return Block(**common, math=c.get("math_content", ""), crop=crop)
    if t in CAPTIONED:
        captions = _joined([c.get(f"{t}_caption", []), c.get(f"{t}_footnote", [])])
        if t == "table":
            return Block(
                **common | {"sub_type": c.get("table_type")},
                html=c.get("html", ""),
                crop=crop,
                captions=captions,
            )
        return Block(**common, content=c.get("content") or "", crop=crop, captions=captions)
    raise BlockError(f"{where}: unsupported type {t!r} — extend src/blocks.py before using it")


def load_pages(path: Path) -> list[list[Block]]:
    """One list of blocks per page, blank pages included (as empty lists)."""
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list) or any(not isinstance(pg, list) for pg in raw):
        raise BlockError(f"{path}: not a content_list_v2 (expected a list of pages)")
    return [[_block(b, p, i) for i, b in enumerate(page)] for p, page in enumerate(raw)]


def load_blocks(path: Path) -> list[Block]:
    return [b for page in load_pages(path) for b in page]


def on_page(blocks: list[Block], page_idx: int) -> list[Block]:
    return [b for b in blocks if b.page_idx == page_idx]
