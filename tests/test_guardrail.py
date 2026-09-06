import pymupdf
import pytest

from src.blocks import Block, Span, load_pages, v2_path
from src.guardrail import (
    GuardrailError,
    align_blocks,
    block_masks,
    block_text,
    block_tokens,
    diff_page,
    pdf_page_text,
    pdf_tokens,
    run,
)
from tests.helpers import FIXTURES


def _para(idx, text, page=0, math=None):
    spans = [Span("text", text)]
    if math:
        spans += [Span("equation_inline", math), Span("text", "million.")]
    return Block(
        id=f"p{page:03d}-b{idx:03d}",
        index=idx,
        type="paragraph",
        page_idx=page,
        bbox=(0, 0, 1, 1),
        spans=tuple(spans),
    )


def test_control_page_aligns_every_block_with_zero_hunks(text_only_cache):
    r = run(FIXTURES / "bkm" / "text-only.pdf", text_only_cache, stem="text-only")
    c = r["counts"]
    assert r["pages"] == 4 and c["matched_blocks"] > 0
    assert (c["unmatched_blocks"], c["hunks"]) == (0, 0), r["hunks"]
    assert c["pdf_tokens"] == c["md_tokens"]


def test_masks_remove_exactly_the_words_inside_vlm_body_boxes(table_cache):
    doc = pymupdf.open(FIXTURES / "bma" / "table.pdf")
    pages = load_pages(v2_path(table_cache, "table"))
    masked_any = False
    for idx, page in enumerate(doc):
        masks = block_masks(pages[idx], page.rect)
        words = page.get_text("words")
        outside = [
            w[4]
            for w in words
            if not any(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2) in m for m in masks)
        ]
        assert pdf_page_text(page, masks).split() == " ".join(outside).split()
        masked_any |= len(outside) < len(words)
    assert masked_any


def test_fixture_hunks_are_anchored_and_inline_math_is_counted(formula_cache, table_cache):
    for pdf, cache, stem in (
        (FIXTURES / "bma" / "formula.pdf", formula_cache, "formula"),
        (FIXTURES / "bma" / "table.pdf", table_cache, "table"),
    ):
        r = run(pdf, cache, stem=stem)
        ids = {b.id for pg in load_pages(v2_path(cache, stem)) for b in pg}
        assert all(h["anchor"] in ids or h["anchor"].endswith("-none") for h in r["hunks"])
        assert (
            set(r["hunks"][0]) == {"page", "anchor", "pdf_text", "md_text"} if r["hunks"] else True
        )
        assert 0 <= r["counts"]["hunks_inline_math"] <= r["counts"]["hunks"]


def test_block_text_flattens_inline_math_and_spaces_spans():
    b = _para(1, "where ", math="C _ { 0 } = 1")
    assert block_text(b) == "where  C0=1 million."
    assert [t.text for t in block_tokens(b)] == ["where", "C0=1", "million."]
    assert all(t.block == b.id for t in block_tokens(b))
    chart = Block(
        id="p000-b002",
        index=2,
        type="chart",
        page_idx=0,
        bbox=(0, 0, 1, 1),
        captions=(Span("text", "Figure 1"),),
    )
    assert block_text(chart) == "Figure 1"
    assert (
        block_text(Block(id="p000-b003", index=3, type="table", page_idx=0, bbox=(0, 0, 1, 1)))
        == ""
    )


def test_align_blocks_matches_verbatim_in_any_order():
    pdf = pdf_tokens("boxed example text first.\nBody sentence here.")
    blocks = [_para(0, "Body sentence here."), _para(1, "boxed example text first.")]
    aln = align_blocks(pdf, blocks)
    assert set(aln.spans) == {"p000-b000", "p000-b001"} and aln.spans["p000-b001"] == (0, 4)
    assert aln.residual_pdf == [] and aln.residual_md == []


def test_diff_page_reports_a_hunk_with_anchor_and_context():
    pdf = pdf_tokens("one two three four five six seven")
    hunks, aln = diff_page(
        pdf, [_para(0, "one two three fuor five six seven")], page_label=119, page_idx=0
    )
    assert aln.spans == {} and len(hunks) == 1
    h = hunks[0]
    assert h["page"] == 119 and h["anchor"] == "p000-b000"
    assert "four" in h["pdf_text"] and "fuor" in h["md_text"] and "fuor" not in h["pdf_text"]


def test_pure_deletion_anchors_to_the_block_matched_just_before():
    pdf = pdf_tokens("alpha beta gamma delta epsilon")
    hunks, aln = diff_page(
        pdf, [_para(0, "alpha beta"), _para(1, "epsilon")], page_label=1, page_idx=0
    )
    assert len(aln.spans) == 2 and len(hunks) == 1
    assert hunks[0]["anchor"] == "p000-b000" and hunks[0]["md_text"] == ""
    assert hunks[0]["pdf_text"] == "gamma delta"  # context comes from the residual stream


def test_page_count_mismatch_fails_loudly(text_only_cache):
    with pytest.raises(GuardrailError, match="content_list_v2 has 4 pages, formula.pdf has 1"):
        run(FIXTURES / "bma" / "formula.pdf", text_only_cache, stem="text-only")
