"""Stage 4 — qa_report.json builder (design §7). The whole work order for stage 5."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from src.blocks import (
    FIGURES,
    RUNNING_MATTER,
    SCHEMA_TYPE,
    TEXT_BEARING,
    Block,
    load_blocks,
    v2_path,
)
from src.config import ConfigError, chapter_number, work_dir
from src.extract import STEM, hybrid_auto_dir
from src.normalize import join_letter_spaced_caps
from src.qa_schema import SchemaError, validate

SPOT_FRACTION = 0.05
SPOT_MIN = 3
BODY_TEXT = TEXT_BEARING - RUNNING_MATTER  # spot-check candidates
_FOLIO = re.compile(r"^(page\s+)?[0-9]+$|^[ivxlc]+$", re.IGNORECASE)  # `Page 81`: ops
_RUNNING_HEAD = re.compile(r"^(chapter|part)\b", re.IGNORECASE)


class ReportError(Exception):
    pass


def _fold(text: str) -> str:
    """Whitespace-collapsed, letter-spaced caps joined (`C H A P T E R` -> `CHAPTER`), casefolded."""
    return join_letter_spaced_caps(" ".join(text.split())).casefold()


def is_running_matter(text: str, repeated: bool, chapter_title: str = "") -> bool:
    """A folio, a `Chapter N`/`Part N` head, a head repeated on other pages, or the chapter title.

    Anything else typed page_header/page_footer/page_number is body text the layout model
    mislabeled (reflowed e-books have no running heads), and must not vanish silently.
    """
    t = _fold(text)
    if not t:
        return True  # nothing to lose
    return bool(
        _FOLIO.match(t)
        or _RUNNING_HEAD.match(t)
        or repeated
        or (chapter_title and _fold(chapter_title) in t)
    )


def running_matter_suspects(blocks: list[Block], chapter_title: str = "") -> list[Block]:
    matter = [b for b in blocks if b.type in RUNNING_MATTER]
    pages_by_text: dict[str, set[int]] = defaultdict(set)
    for b in matter:
        pages_by_text[_fold(b.text())].add(b.page_idx)
    return [
        b
        for b in matter
        if not is_running_matter(b.text(), len(pages_by_text[_fold(b.text())]) >= 2, chapter_title)
    ]


def spot_sample(candidates: list[Block], book: str, chapter: str) -> list[Block]:
    if not candidates:
        return []
    n = min(len(candidates), max(SPOT_MIN, round(SPOT_FRACTION * len(candidates))))
    seed = int(hashlib.sha256(f"{book}{chapter}".encode()).hexdigest(), 16)
    return sorted(random.Random(seed).sample(candidates, n), key=lambda b: (b.page_idx, b.index))


def render_crop(doc: pymupdf.Document, block: Block, out_dir: Path, zoom: float = 2.0) -> str:
    """Render the block's bbox (0-1000 coords) from chapter.pdf to crops/<id>.png."""
    page = doc[block.page_idx]
    sx, sy = page.rect.width / 1000, page.rect.height / 1000
    x0, y0, x1, y1 = block.bbox
    clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    crops = Path(out_dir) / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(zoom, zoom)).save(crops / f"{block.id}.png")
    return f"crops/{block.id}.png"


def build(
    meta: dict,
    guardrail: dict,
    blocks: list[Block],
    middle: dict,
    content_list_mtime: float,
    crop: Callable[[Block], str],
) -> dict:
    flagged = [
        {
            "id": b.id,
            "type": SCHEMA_TYPE[b.type],
            "crop": b.crop or crop(b),  # mineru's crop under images/; rendered only if absent
            "reason": "vlm_generated",
        }
        for b in blocks
        if b.is_vlm_generated()
    ]
    flagged += [
        {"id": b.id, "type": "text", "crop": crop(b), "reason": "running_matter_suspect"}
        for b in running_matter_suspects(blocks, meta.get("title", ""))
    ]
    flagged.sort(key=lambda f: f["id"])
    candidates = [b for b in blocks if b.type in BODY_TEXT]
    timestamp = datetime.fromtimestamp(content_list_mtime, tz=timezone.utc).isoformat(
        timespec="seconds"
    )
    report = {
        "book": meta["book"],
        "chapter": meta["chapter"],
        "pages": list(meta["printed_pages"]),
        "extraction": {
            "backend": "hybrid-http-client",
            "effort": str(middle.get("_effort", "")),
            "mineru_version": str(middle.get("_version_name", "")),
            "timestamp": timestamp,
        },
        "counts": {
            "blocks": len(blocks),
            "tables": sum(b.type == "table" for b in blocks),
            "formulas": sum(b.type == "equation_interline" for b in blocks),
            "figures": sum(b.type in FIGURES for b in blocks),
            "diff_hunks": len(guardrail["hunks"]),
        },
        "diff_hunks": list(guardrail["hunks"]),
        "flagged_blocks": flagged,
        "spot_check": [
            {"id": b.id, "crop": crop(b)}
            for b in spot_sample(candidates, meta["book"], meta["chapter"])
        ],
        "status": "pending_review",
    }
    validate(report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 4: build and validate qa_report.json")
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True, help="chapter number (5) or slug (ch05)")
    args = ap.parse_args(argv)
    try:
        wd = work_dir(args.book, chapter_number(args.chapter))
        hybrid_auto = hybrid_auto_dir(wd)
        content_list = v2_path(hybrid_auto, STEM)
        for needed in (wd / "meta.json", wd / "chapter.pdf", wd / "guardrail.json", content_list):
            if not needed.exists():
                raise ReportError(f"{needed} missing — run split/extract/guardrail first")
        meta = json.loads((wd / "meta.json").read_text())
        guardrail = json.loads((wd / "guardrail.json").read_text())
        middle = json.loads((hybrid_auto / f"{STEM}_middle.json").read_text())
        doc = pymupdf.open(wd / "chapter.pdf")
        report = build(
            meta,
            guardrail,
            load_blocks(content_list),
            middle,
            content_list.stat().st_mtime,
            lambda b: render_crop(doc, b, wd),
        )
    except (ReportError, SchemaError, ConfigError) as e:
        print(f"qa_report: {e}", file=sys.stderr)
        return 1
    (wd / "qa_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    c = report["counts"]
    suspects = sum(f["reason"] == "running_matter_suspect" for f in report["flagged_blocks"])
    print(
        f"qa_report: {args.book} {report['chapter']} pages {report['pages']} "
        f"-> {wd / 'qa_report.json'}"
    )
    print(
        f"  counts {c} | flagged {len(report['flagged_blocks'])} ({suspects} running-matter "
        f"suspects) | spot_check {len(report['spot_check'])} | status {report['status']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
