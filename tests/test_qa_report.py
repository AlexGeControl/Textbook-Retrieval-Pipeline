import json
from collections import Counter
from copy import deepcopy

import pymupdf
import pytest

from src.blocks import Block, Span, load_blocks, v2_path
from src.qa_report import build, is_running_matter, render_crop, running_matter_suspects
from src.qa_schema import SchemaError, validate
from tests.helpers import FIXTURES

META = {
    "book": "bma",
    "chapter": "ch05",
    "title": "Net Present Value and Other Investment Criteria",
    "printed_pages": [119, 148],
}
GUARD = {
    "pages": 2,
    "counts": {
        "pdf_tokens": 10,
        "md_tokens": 10,
        "matched_blocks": 1,
        "unmatched_blocks": 1,
        "hunks": 1,
        "hunks_inline_math": 0,
    },
    "hunks": [{"page": 119, "anchor": "p000-b001", "pdf_text": "a b", "md_text": "a c"}],
}
MIDDLE = {"_effort": "high", "_version_name": "3.4.5"}


def _build(cache, crop=lambda b: f"crops/{b.id}.png"):
    blocks = load_blocks(v2_path(cache, "table"))
    middle = json.loads((cache / "table_middle.json").read_text())
    return build(META, GUARD, blocks, middle, 1_788_000_000.0, crop)


def _matter(idx, type_, text, page=0):
    return Block(
        id=f"p{page:03d}-b{idx:03d}",
        index=idx,
        type=type_,
        page_idx=page,
        bbox=(0, 0, 1, 1),
        spans=(Span("text", text),),
    )


def test_report_header_counts_and_flags(table_cache):
    r = _build(table_cache)
    assert (r["book"], r["chapter"], r["pages"], r["status"]) == (
        "bma",
        "ch05",
        [119, 148],
        "pending_review",
    )
    assert r["extraction"] == {
        "backend": "hybrid-http-client",
        "effort": "high",
        "mineru_version": "3.4.5",
        "timestamp": r["extraction"]["timestamp"],
    }
    assert r["extraction"]["timestamp"].startswith("2026-") and r["extraction"][
        "timestamp"
    ].endswith("+00:00")
    assert r["counts"] == {"blocks": 25, "tables": 5, "formulas": 1, "figures": 1, "diff_hunks": 1}
    assert r["diff_hunks"] == GUARD["hunks"]
    vlm = [f for f in r["flagged_blocks"] if f["reason"] == "vlm_generated"]
    assert Counter(f["type"] for f in vlm) == {"table": 5, "formula": 1, "chart": 1}
    assert all(f["crop"].startswith("images/") for f in vlm), "every VLM body has a mineru crop"
    assert [f["id"] for f in r["flagged_blocks"]] == sorted(f["id"] for f in r["flagged_blocks"])


def test_spot_check_is_seeded_sized_and_disjoint_from_flags(table_cache):
    r1, r2 = _build(table_cache), _build(table_cache)
    assert r1 == r2
    ids = [s["id"] for s in r1["spot_check"]]
    assert len(ids) == 3  # 5 % of the body-text blocks rounds below the minimum of 3
    assert not set(ids) & {f["id"] for f in r1["flagged_blocks"]}
    assert all(s["crop"] == f"crops/{s['id']}.png" for s in r1["spot_check"])


def test_render_crop_writes_a_png_for_a_text_block(table_cache, tmp_path):
    blocks = load_blocks(v2_path(table_cache, "table"))
    para = next(b for b in blocks if b.type == "paragraph")
    doc = pymupdf.open(FIXTURES / "bma" / "table.pdf")
    rel = render_crop(doc, para, tmp_path)
    assert rel == f"crops/{para.id}.png"
    pix = pymupdf.Pixmap(str(tmp_path / rel))
    assert pix.width > 100 and pix.height > 10


def test_running_matter_heuristic():
    assert is_running_matter("119", repeated=False)
    assert is_running_matter("xii", repeated=False)
    assert is_running_matter("Chapter 5  Net Present Value", repeated=False)
    assert is_running_matter("PART 2 :: STRATEGIC FORMULATION", repeated=False)
    assert is_running_matter("Some Title", repeated=True)
    assert is_running_matter(
        "Discrete Probability Distributions",
        repeated=False,
        chapter_title="Discrete Probability Distributions",
    )
    assert is_running_matter("", repeated=False)
    assert is_running_matter("Page 81", repeated=False)  # ops: folios written as words
    assert is_running_matter("C H A P T E R", repeated=False)  # bma opener, letter-spaced
    assert not is_running_matter("Analyzing the Financial Statements", repeated=False)
    assert not is_running_matter("Comment on the company’s solvency trend.", repeated=False)
    assert not is_running_matter("15,860 15,478 25,739 25,641", repeated=False)


def test_running_matter_suspects_are_body_text_typed_as_head_or_foot():
    blocks = [
        _matter(0, "page_header", "Chapter 5  Net Present Value and Other Investment Criteria"),
        _matter(1, "page_number", "119"),
        _matter(2, "page_header", "Analyzing the Financial Statements"),
        _matter(3, "page_footer", "PART 2 :: STRATEGIC FORMULATION"),
        _matter(0, "page_footer", "PART 2 :: STRATEGIC FORMULATION", page=1),
        _matter(1, "page_header", "Comment on the company’s solvency trend.", page=1),
        _matter(2, "paragraph", "Comment on the company’s solvency trend.", page=1),
    ]
    assert [b.id for b in running_matter_suspects(blocks, META["title"])] == [
        "p000-b002",
        "p001-b001",
    ]
    r = build(META, GUARD, blocks, MIDDLE, 1_788_000_000.0, lambda b: f"crops/{b.id}.png")
    suspects = [f for f in r["flagged_blocks"] if f["reason"] == "running_matter_suspect"]
    assert [(f["id"], f["type"], f["crop"]) for f in suspects] == [
        ("p000-b002", "text", "crops/p000-b002.png"),
        ("p001-b001", "text", "crops/p001-b001.png"),
    ]
    assert (
        r["counts"]["blocks"] == 7
        and r["spot_check"]
        and all(s["id"] == "p001-b002" for s in r["spot_check"])
    )


def test_image_with_vlm_content_is_flagged_as_figure_with_its_crop():
    img = Block(
        id="p000-b000",
        index=0,
        type="image",
        page_idx=0,
        bbox=(0, 0, 1, 1),
        content="```mermaid\n```",
        crop="images/f.jpg",
        sub_type="flowchart",
    )
    plain = Block(
        id="p000-b001", index=1, type="image", page_idx=0, bbox=(0, 0, 1, 1), crop="images/g.jpg"
    )
    r = build(META, GUARD, [img, plain], MIDDLE, 1_788_000_000.0, lambda b: f"crops/{b.id}.png")
    assert r["flagged_blocks"] == [
        {"id": "p000-b000", "type": "figure", "crop": "images/f.jpg", "reason": "vlm_generated"}
    ]
    assert r["counts"]["figures"] == 2


def test_validate_reports_the_first_violation_path(table_cache):
    good = _build(table_cache)
    validate(good)
    cases = [
        (lambda r: r["counts"].pop("tables"), r"^counts: missing tables"),
        (
            lambda r: r["flagged_blocks"][0].__setitem__("type", "image"),
            r"^flagged_blocks\[0\]\.type",
        ),
        (
            lambda r: r["flagged_blocks"][0].__setitem__("reason", "low_confidence"),
            r"^flagged_blocks\[0\]\.reason",
        ),
        (lambda r: r.__setitem__("status", "done"), r"^status"),
        (lambda r: r["counts"].__setitem__("diff_hunks", 7), r"^counts\.diff_hunks"),
        (lambda r: r.__setitem__("pages", [148]), r"^pages"),
        (lambda r: r["diff_hunks"][0].pop("anchor"), r"^diff_hunks\[0\]: missing anchor"),
        (lambda r: r["extraction"].__setitem__("effort", 1), r"^extraction\.effort"),
    ]
    for mutate, pattern in cases:
        bad = deepcopy(good)
        mutate(bad)
        with pytest.raises(SchemaError, match=pattern):
            validate(bad)
