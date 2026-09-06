import json
import re
from collections import Counter

import pytest

from src.blocks import (
    CAPTIONED,
    FIGURES,
    MASKED,
    RUNNING_MATTER,
    SCHEMA_TYPE,
    TEXT_BEARING,
    VLM_GENERATED,
    Block,
    BlockError,
    Span,
    block_id,
    load_blocks,
    load_pages,
    on_page,
    v2_path,
)


def _v2(tmp_path, pages):
    p = tmp_path / "x_content_list_v2.json"
    p.write_text(json.dumps(pages))
    return p


def test_control_page_has_no_table_or_formula_blocks(text_only_cache):
    blocks = load_blocks(v2_path(text_only_cache, "text-only"))
    assert [b for b in blocks if b.type in ("table", "equation_interline")] == []
    assert len(blocks) == 50  # decorative icons are typed image, and that is fine


def test_table_fixture_counts(table_cache):
    by_type = Counter(b.type for b in load_blocks(v2_path(table_cache, "table")))
    assert (by_type["table"], by_type["equation_interline"], by_type["chart"]) == (5, 1, 1)


def test_display_equations_carry_bare_latex_and_a_mineru_crop(formula_cache):
    eqs = [
        b for b in load_blocks(v2_path(formula_cache, "formula")) if b.type == "equation_interline"
    ]
    assert len(eqs) == 4
    for b in eqs:
        assert b.math and "$$" not in b.math and b.math.count("{") == b.math.count("}"), b.math
        assert b.crop.startswith("images/") and (formula_cache / b.crop).exists(), b.crop
        assert b.is_vlm_generated() and SCHEMA_TYPE[b.type] == "formula"


def test_ids_are_per_page_positional_and_unique(table_cache):
    pages = load_pages(v2_path(table_cache, "table"))
    assert len(pages) == 2
    blocks = [b for pg in pages for b in pg]
    assert blocks[0].id == "p000-b000" and pages[1][0].id == "p001-b000"
    assert len({b.id for b in blocks}) == len(blocks)
    assert all(b.id == block_id(b.page_idx, b.index) for b in blocks)
    assert all(0 <= v <= 1000 for b in blocks for v in b.bbox)


def test_blank_page_is_an_empty_list(tmp_path):
    para = {
        "type": "paragraph",
        "content": {"paragraph_content": [{"type": "text", "content": "x"}]},
        "bbox": [1, 2, 3, 4],
    }
    pages = load_pages(_v2(tmp_path, [[], [para]]))
    assert pages[0] == [] and pages[1][0].page_idx == 1 and pages[1][0].id == "p001-b000"
    assert load_blocks(_v2(tmp_path, [[], [para]])) == pages[1]


def test_spans_separate_text_from_inline_math():
    b = Block(
        id="p000-b001",
        index=1,
        type="paragraph",
        page_idx=0,
        bbox=(0, 0, 1, 1),
        spans=(
            Span("text", "where "),
            Span("equation_inline", "C _ { 0 }"),
            Span("text", "million."),
        ),
    )
    assert b.text() == "where million."
    assert b.inline_math() == ("C _ { 0 }",)
    assert not b.is_vlm_generated()


def test_list_items_are_newline_separated_spans(tmp_path):
    lst = {
        "type": "list",
        "content": {
            "list_type": "text_list",
            "list_items": [
                {"item_type": "text", "item_content": [{"type": "text", "content": "a"}]},
                {
                    "item_type": "text",
                    "item_content": [
                        {"type": "text", "content": "b "},
                        {"type": "equation_inline", "content": "x"},
                    ],
                },
            ],
        },
        "bbox": [0, 0, 1, 1],
    }
    (b,) = load_blocks(_v2(tmp_path, [[lst]]))
    assert b.type == "list" and b.sub_type == "text_list"
    assert b.text() == "a\nb " and b.inline_math() == ("x",)


def test_headings_carry_level(table_cache):
    heads = [b for b in load_blocks(v2_path(table_cache, "table")) if b.type == "title"]
    assert [(b.text(), b.level) for b in heads] == [("6.1 Self-Test", 2)]


def test_on_page_filters_by_page(table_cache):
    blocks = load_blocks(v2_path(table_cache, "table"))
    page1 = on_page(blocks, 1)
    assert page1 and all(b.page_idx == 1 for b in page1)
    assert len(on_page(blocks, 0)) + len(page1) == len(blocks)


def test_captioned_blocks_expose_caption_text_and_crop(chart_cache):
    charts = [b for b in load_blocks(v2_path(chart_cache, "chart")) if b.type == "chart"]
    assert charts and charts[0].caption_text().startswith("Figure 11.4")
    assert charts[0].text() == "" and charts[0].content and charts[0].crop.startswith("images/")
    assert charts[0].is_vlm_generated() and SCHEMA_TYPE["chart"] == "chart"


def test_image_is_vlm_generated_only_when_it_carries_content(tmp_path):
    def img(content, sub_type=None):
        raw = {
            "type": "image",
            "content": {
                "image_source": {"path": "images/a.jpg"},
                "content": content,
                "image_caption": [],
                "image_footnote": [{"type": "text", "content": "Source: x"}],
            },
            "bbox": [0, 0, 1, 1],
        }
        if sub_type:
            raw["sub_type"] = sub_type
        return raw

    flow, plain = load_blocks(
        _v2(tmp_path, [[img("```mermaid\ngraph TD\n```", "flowchart"), img("")]])
    )
    assert (
        flow.is_vlm_generated()
        and flow.sub_type == "flowchart"
        and SCHEMA_TYPE["image"] == "figure"
    )
    assert not plain.is_vlm_generated() and plain.caption_text() == "Source: x"
    assert {flow.type, plain.type} <= FIGURES and flow.crop == "images/a.jpg"


def test_unsupported_type_fails_loudly(tmp_path):
    code = {"type": "code", "content": {"code_content": []}, "bbox": [0, 0, 1, 1]}
    with pytest.raises(BlockError, match=r"p0 block 0: unsupported type 'code'"):
        load_blocks(_v2(tmp_path, [[code]]))
    with pytest.raises(BlockError, match="expected a list of pages"):
        load_blocks(_v2(tmp_path, [{"type": "paragraph"}]))


def test_type_classes_partition_the_v2_vocabulary():
    assert not TEXT_BEARING & (VLM_GENERATED | FIGURES)
    assert RUNNING_MATTER < TEXT_BEARING
    assert MASKED == VLM_GENERATED | {"image"} == frozenset(SCHEMA_TYPE)
    assert CAPTIONED == FIGURES | {"table"}


def test_v2_text_spans_are_not_markdown_escaped(
    table_cache, formula_cache, chart_cache, text_only_cache
):
    escaped_v1 = escaped_v2 = 0
    for cache, stem in (
        (table_cache, "table"),
        (formula_cache, "formula"),
        (chart_cache, "chart"),
        (text_only_cache, "text-only"),
    ):
        v1 = json.loads((cache / f"{stem}_content_list.json").read_text())
        escaped_v1 += sum(len(re.findall(r"\\[$%_#]", b.get("text", ""))) for b in v1)
        for b in load_blocks(v2_path(cache, stem)):
            escaped_v2 += len(re.findall(r"\\[$%_#]", b.text() + b.caption_text()))
    assert escaped_v1 > 0, "v1 is expected to escape literal $ % _ # — fixture set changed?"
    assert escaped_v2 == 0
