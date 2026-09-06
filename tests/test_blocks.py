from collections import Counter

from src.blocks import Block, block_id, load_blocks, on_page


def test_control_page_has_no_table_or_formula_blocks(text_only_cache):
    blocks = load_blocks(text_only_cache / "text-only_content_list.json")
    assert [b for b in blocks if b.type in ("table", "equation")] == []
    assert len(blocks) == 50  # decorative icons are typed image, and that is fine


def test_table_fixture_counts(table_cache):
    by_type = Counter(b.type for b in load_blocks(table_cache / "table_content_list.json"))
    assert (by_type["table"], by_type["equation"], by_type["chart"]) == (5, 1, 1)


def test_formula_fixture_equations_are_delimited_latex(formula_cache):
    blocks = load_blocks(formula_cache / "formula_content_list.json")
    eqs = [b for b in blocks if b.type == "equation"]
    assert len(eqs) == 4
    for b in eqs:
        s = b.text.strip()
        assert s.startswith("$$") and s.endswith("$$"), s
        assert s.count("{") == s.count("}"), s


def test_ids_are_positional_and_unique(table_cache):
    blocks = load_blocks(table_cache / "table_content_list.json")
    assert blocks[0].id == "p000-b000"
    assert len({b.id for b in blocks}) == len(blocks)
    assert all(b.id == block_id(b.page_idx, b.index) for b in blocks)
    assert all(0 <= v <= 1000 for b in blocks for v in b.bbox)


def test_running_text_joins_list_items():
    b = Block(
        id="p000-b001", index=1, type="list", page_idx=0, bbox=(0, 0, 1, 1), list_items=("a", "b")
    )
    assert b.running_text() == "a\nb"
    t = Block(id="p000-b002", index=2, type="text", page_idx=0, bbox=(0, 0, 1, 1), text="x")
    assert t.running_text() == "x"


def test_headings_carry_text_level(table_cache):
    heads = [b for b in load_blocks(table_cache / "table_content_list.json") if b.text_level]
    assert [(b.text, b.text_level) for b in heads] == [("6.1 Self-Test", 2)]


def test_on_page_filters_by_page(table_cache):
    blocks = load_blocks(table_cache / "table_content_list.json")
    page1 = on_page(blocks, 1)
    assert page1 and all(b.page_idx == 1 for b in page1)
    assert len(on_page(blocks, 0)) + len(page1) == len(blocks)


def test_captioned_blocks_expose_caption_text(chart_cache):
    charts = [b for b in load_blocks(chart_cache / "chart_content_list.json") if b.type == "chart"]
    assert charts and charts[0].captions[0].startswith("Figure 11.4")
    assert charts[0].caption_text().startswith("Figure 11.4")
    assert charts[0].running_text() == ""
