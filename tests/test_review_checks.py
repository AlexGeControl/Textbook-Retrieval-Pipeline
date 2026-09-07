import json
from collections import Counter

import pymupdf
import pytest

from src.blocks import Block, Span, load_blocks, v2_path
from src.review import Chapter
from src.review_checks import (
    bag,
    footnote_report,
    formula_textlayer,
    latex_ok,
    run,
    table_grid,
    table_textlayer,
    table_tokens,
)
from src.textlayer import page_words
from tests.helpers import make_work_dir, work_chapter


def test_latex_ok_strict_parse_and_pairing():
    assert latex_ok(
        r"\mathrm{NPV} = C _ {0} + \sum_ {t = 1} ^ {t = T} \frac {C _ {t}}{(1 + r) ^ {t}} \tag {5.1}"
    ) == (True, "")
    ok, why = latex_ok(r"\frac{a}{b")
    assert not ok and "expecting" in why
    assert latex_ok(r"\left( x \right") == (False, "\\left/\\right unbalanced")
    assert latex_ok(r"\begin{aligned} x \end{aligned}")[0]
    assert latex_ok(r"a $ b") == (False, "unescaped $")
    assert latex_ok(r"\$500")[0]


def test_table_grid_handles_spans_and_empty():
    assert table_grid(
        "<table><tr><td colspan='3'>h</td></tr><tr><td>a</td><td>b</td><td>c</td></tr></table>"
    ) == (2, 3, True)
    assert table_grid(
        "<table><tr><td rowspan='2'>a</td><td>b</td></tr><tr><td>c</td></tr></table>"
    ) == (2, 2, True)
    assert table_grid("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>") == (
        2,
        2,
        False,
    )
    assert table_grid("") == (0, 0, False)


def test_table_tokens_flatten_inline_math_and_breaks():
    toks = table_tokens(
        "<table><tr><td>Cash Flows ($)</td><td>$C_0$</td><td>1<br>2</td></tr></table>"
    )
    assert toks == ["Cash", "Flows", "($)", "C0", "1", "2"]
    assert bag(["−4,000", "-4,000", "+2,000", "."]) == Counter({"4000": 2, "+2000": 1})


def _tb(html, bbox=(0, 0, 1000, 200)):
    return Block(
        id="p000-b000",
        index=0,
        type="table",
        page_idx=0,
        bbox=bbox,
        html=html,
        sub_type="simple_table",
    )


def test_table_and_formula_textlayer_on_a_synthetic_page():
    doc = pymupdf.open()
    page = doc.new_page(width=1000, height=1000)
    page.insert_text((50, 100), "Asset Reject Accept", fontsize=12)
    page.insert_text((50, 130), "Cash 1 0", fontsize=12)
    page.insert_text((50, 400), "NPV = C0 + PV", fontsize=12)
    words = page_words(page)
    ok, diff = table_textlayer(
        _tb(
            "<table><tr><td>Asset</td><td>Reject</td><td>Accept</td></tr><tr><td>Cash</td><td>1</td><td>0</td></tr></table>"
        ),
        words,
        page.rect,
    )
    assert (ok, diff) == (True, [])
    ok, diff = table_textlayer(
        _tb(
            "<table><tr><td>Asset</td><td>Reject</td><td>Accept</td></tr><tr><td>Cash</td><td>1</td><td>9</td></tr></table>"
        ),
        words,
        page.rect,
    )
    assert (ok, diff) == (False, ["0", "9"])
    eq = Block(
        id="p000-b001",
        index=1,
        type="equation_interline",
        page_idx=0,
        bbox=(0, 380, 1000, 420),
        math=r"\mathrm{NPV} = C_{0} + PV",
    )
    assert formula_textlayer(eq, words, page.rect) is True
    assert formula_textlayer(eq, words, page.rect, enabled=False) is None
    off = Block(
        id="p000-b002",
        index=2,
        type="equation_interline",
        page_idx=0,
        bbox=(0, 800, 1000, 900),
        math="x",
    )
    assert formula_textlayer(off, words, page.rect) is None


def _b(id_, type_, text, level=None):
    return Block(
        id=id_,
        index=int(id_[-3:]),
        type=type_,
        page_idx=int(id_[1:4]),
        bbox=(0, 0, 10, 10),
        spans=(Span("text", text),),
        level=level,
    )


def test_footnote_report_blocking_and_dangling():
    blocks = [
        _b("p000-b001", "paragraph", "flows.<sup>1</sup> and more<sup>3</sup> 1.1<sup>2</sup>"),
        _b("p000-b002", "page_footnote", "<sup>1</sup>note one"),
        _b("p000-b003", "page_footnote", "<sup>2</sup>never referenced"),
    ]
    rep = footnote_report(
        blocks, previous={"unmatched": [{"id": "2", "verdict": "accepted", "note": "in a table"}]}
    )
    assert rep == {
        "definitions": 2,
        "references": 2,
        "unmatched": [{"id": "2", "verdict": "accepted", "note": "in a table"}],
        "dangling": ["3"],
    }


PARA = {
    "type": "paragraph",
    "bbox": [80, 80, 600, 120],
    "content": {"paragraph_content": [{"type": "text", "content": "body one"}]},
}
TITLE = {
    "type": "title",
    "bbox": [80, 40, 600, 70],
    "content": {"title_content": [{"type": "text", "content": "5-1 First"}], "level": 2},
}
SUB = {
    "type": "title",
    "bbox": [80, 300, 600, 330],
    "content": {"title_content": [{"type": "text", "content": "Sub One"}], "level": 2},
}
TABLE = {
    "type": "table",
    "bbox": [80, 400, 600, 500],
    "content": {
        "html": "<table><tr><td>a</td><td>b</td></tr></table>",
        "table_type": "simple_table",
        "image_source": {"path": "images/t.jpg"},
        "table_caption": [],
        "table_footnote": [],
    },
}
EQ = {
    "type": "equation_interline",
    "bbox": [80, 600, 600, 650],
    "content": {"math_content": "\\frac{a}{b", "image_source": {"path": "images/e.jpg"}},
}
SECTIONS = [{"number": "5-1", "title": "First", "pdf_page": 149, "printed_page": 119, "level": 3}]
TREE = [[3, "5-1: First", 149], [4, "Sub One", 149], [4, "Sub Two", 149]]
FLAGS = [
    {"id": "p000-b003", "type": "table", "crop": "images/t.jpg", "reason": "vlm_generated"},
    {"id": "p000-b004", "type": "formula", "crop": "images/e.jpg", "reason": "vlm_generated"},
]


def test_run_writes_checks_headings_and_footnotes(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[TITLE, PARA, SUB, TABLE, EQ]],
        flagged=FLAGS,
        sections=SECTIONS,
        toc_subtree=TREE,
        pdf_lines=["a b"],
    )
    run(Chapter("bma", 5))
    r = json.loads((wd / "qa_report.json").read_text())["review"]
    table_checks, eq_checks = r["blocks"][0]["checks"], r["blocks"][1]["checks"]
    assert (table_checks["rectangular"], table_checks["rows"], table_checks["cols"]) == (True, 1, 2)
    assert table_checks["latex_parses"] is None
    assert eq_checks["latex_parses"] is False and eq_checks["rectangular"] is None
    assert r["headings"]["sections"] == [1, 1] and r["headings"]["subheadings"] == [1, 2]
    assert r["headings"]["missing"] == [
        {
            "title": "Sub Two",
            "page": 119,
            "kind": "subheading",
            "verdict": None,
            "block": None,
            "note": "",
        }
    ]
    assert r["footnotes"] == {"definitions": 0, "references": 0, "unmatched": [], "dangling": []}


def test_run_fails_loudly_when_a_section_anchor_is_missing(tmp_path, monkeypatch):
    make_work_dir(tmp_path, monkeypatch, pages=[[PARA]], sections=SECTIONS, pdf_lines=["x"])
    from src.sections import SectionError

    with pytest.raises(SectionError, match="First"):
        run(Chapter("bma", 5))


@pytest.mark.workdir
def test_bma_ch05_textlayer_rates():
    wd = work_chapter("bma", "ch05")
    ch = Chapter("bma", 5)
    doc = pymupdf.open(wd / "chapter.pdf")
    blocks = load_blocks(v2_path(wd / "chapter" / "hybrid_auto", "chapter"))
    words = {}
    tables = formulas = 0
    for b in blocks:
        if b.page_idx not in words:
            words[b.page_idx] = page_words(doc[b.page_idx])
        if b.type == "table":
            tables += table_textlayer(b, words[b.page_idx], doc[b.page_idx].rect)[0]
        if b.type == "equation_interline":
            formulas += formula_textlayer(b, words[b.page_idx], doc[b.page_idx].rect) is True
    assert tables >= 9 and formulas >= 19, (tables, formulas)
    assert table_textlayer(ch.by_id["p001-b006"], words[1], doc[1].rect) == (True, [])
