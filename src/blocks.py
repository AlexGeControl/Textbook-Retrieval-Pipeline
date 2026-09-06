"""Block model over MinerU's <stem>_content_list.json (design §6).

content_list is the anchor for stages 3-4: flat, typed, page_idx + bbox (0-1000 per axis),
headings carry text_level, and page_footnote blocks are present (the .md drops them).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RUNNING_TEXT = frozenset({"text", "list", "page_footnote"})
VLM_GENERATED = frozenset({"table", "equation", "chart"})
FIGURES = frozenset({"image", "chart"})
DISCARDED = frozenset({"header", "page_number"})
# blocks whose caption/footnote strings are text-layer running text around a non-text body
CAPTIONED = frozenset({"table", "chart", "image"})
# mineru type -> qa_report flagged_blocks.type
SCHEMA_TYPE = {"table": "table", "equation": "formula", "chart": "chart"}


def block_id(page_idx: int, index: int) -> str:
    return f"p{page_idx:03d}-b{index:03d}"


@dataclass(frozen=True)
class Block:
    id: str
    index: int  # position in content_list
    type: str
    page_idx: int
    bbox: tuple[int, int, int, int]  # content_list coordinates, 0-1000 per axis
    text: str = ""
    list_items: tuple[str, ...] = ()
    table_body: str = ""
    img_path: str = ""
    text_level: int | None = None
    sub_type: str | None = None
    captions: tuple[str, ...] = ()  # *_caption + *_footnote strings of a captioned block

    def running_text(self) -> str:
        return "\n".join(self.list_items) if self.type == "list" else self.text

    def caption_text(self) -> str:
        return "\n".join(self.captions)


def _captions(raw: dict) -> list[str]:
    out: list[str] = []
    for key in (
        "table_caption",
        "table_footnote",
        "chart_caption",
        "chart_footnote",
        "image_caption",
        "image_footnote",
    ):
        out += [s for s in raw.get(key, ()) if s]
    return out


def load_blocks(path: Path) -> list[Block]:
    raw = json.loads(Path(path).read_text())
    return [
        Block(
            id=block_id(b["page_idx"], i),
            index=i,
            type=b["type"],
            page_idx=b["page_idx"],
            bbox=tuple(round(v) for v in b["bbox"]),
            text=b.get("text", ""),
            list_items=tuple(b.get("list_items", ())),
            table_body=b.get("table_body", ""),
            img_path=b.get("img_path", ""),
            text_level=b.get("text_level"),
            sub_type=b.get("sub_type"),
            captions=tuple(_captions(b)),
        )
        for i, b in enumerate(raw)
    ]


def on_page(blocks: list[Block], page_idx: int) -> list[Block]:
    return [b for b in blocks if b.page_idx == page_idx]
