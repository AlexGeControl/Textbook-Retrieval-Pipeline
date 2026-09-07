import pytest

from src.blocks import Block, Span, load_pages, v2_path
from src.sections import (
    SectionError,
    definition_marker,
    find_heading,
    heading_forms,
    references,
    resolve,
    subheading_entries,
)
from tests.helpers import work_chapter


def _b(id_, type_, text, level=None):
    return Block(
        id=id_,
        index=int(id_[-3:]),
        type=type_,
        page_idx=int(id_[1:4]),
        bbox=(0, 0, 10, 10),
        spans=(Span("text", text),) if text is not None else (),
        level=level,
    )


def _meta(sections, toc_subtree=(), pages=3, title="Chapter Title"):
    return {
        "book": "bma",
        "chapter": "ch05",
        "title": title,
        "pdf_pages": [149, 149 + pages - 1],
        "printed_pages": [119, 119 + pages - 1],
        "sections": sections,
        "toc_subtree": list(toc_subtree),
    }


def _sec(number, title, page_idx, level=3):
    return {
        "number": number,
        "title": title,
        "pdf_page": 149 + page_idx,
        "printed_page": 119 + page_idx,
        "level": level,
    }


def fold_in(forms, text):
    from src.fold import fold

    return fold(text) in forms


def test_heading_forms_cover_number_positions_and_markup():
    forms = heading_forms("Why Use Net Present Value?", "5.1")
    assert fold_in(forms, "Why Use Net Present Value?5.1")
    assert fold_in(forms, "5.1 Why Use Net Present Value?")
    assert fold_in(heading_forms("Normality<sup>*</sup>", "5.8"), "5.8 Normality")


def test_find_heading_prefers_exact_case_then_title_type_then_short_runs():
    page = [
        _b("p003-b001", "title", "Overall Cost Leadership", 2),
        _b("p003-b002", "paragraph", "body"),
        _b("p003-b008", "title", "overall cost leadership", 2),
    ]
    assert [b.id for b in find_heading(page, "Overall Cost Leadership", None)] == ["p003-b001"]
    split = [_b("p020-b005", "title", "KEY", 2), _b("p020-b006", "title", "TAKEAWAYS", 2)]
    assert [b.id for b in find_heading(split, "Key Takeaways", None)] == ["p020-b005", "p020-b006"]
    suspect = [_b("p006-b008", "page_header", "Analyzing the Financial Statements")]
    assert [b.id for b in find_heading(suspect, "Analyzing the Financial Statements", None)] == [
        "p006-b008"
    ]
    assert find_heading([_b("p000-b000", "paragraph", "nothing")], "Absent", None) is None


def test_find_heading_raises_on_true_ambiguity():
    page = [_b("p000-b000", "title", "Summary", 2), _b("p000-b003", "title", "Summary", 2)]
    with pytest.raises(SectionError, match="ambiguous"):
        find_heading(page, "Summary", None)


def test_footnote_marker_and_references():
    assert (
        definition_marker(_b("p004-b017", "page_footnote", "<sup>1</sup>Occasionally firms")) == "1"
    )
    assert definition_marker(_b("p012-b015", "page_footnote", "PV = 10/1.1<sup>2</sup>")) is None
    body = _b(
        "p000-b001",
        "paragraph",
        "cash flows.<sup>1</sup> Then 1.1<sup>2</sup> and (x)<sup>3</sup> again<sup>4</sup>",
    )
    assert references(body) == ["1", "4"]


def _pages_basic():
    return [
        [
            _b("p000-b000", "title", "Chapter Title", 1),
            _b("p000-b001", "paragraph", "opener"),
            _b("p000-b002", "title", "5-1 First Section", 2),
            _b("p000-b003", "paragraph", "first body<sup>1</sup>"),
            _b("p000-b004", "page_footnote", "<sup>1</sup>note one"),
            _b("p000-b005", "page_footnote", "continued"),
        ],
        [
            _b("p001-b000", "paragraph", "still first"),
            _b("p001-b001", "title", "Second Section", 2),
            _b("p001-b002", "paragraph", "second body"),
            _b("p001-b003", "title", "Third", 2),
            _b("p001-b004", "list", "item"),
            _b("p001-b005", "page_footnote", "*star note"),
        ],
        [_b("p002-b000", "paragraph", "tail")],
    ]


def test_resolve_slices_preamble_sections_and_two_sections_on_one_page():
    meta = _meta(
        [_sec("5-1", "First Section", 0), _sec(None, "Second Section", 1), _sec(None, "Third", 1)]
    )
    secs = resolve(meta, _pages_basic())
    assert [s.ordinal for s in secs] == [0, 1, 2, 3]
    assert [b.id for b in secs[0].blocks] == ["p000-b001"]  # chapter title dropped, opener kept
    assert secs[1].anchor == "p000-b002" and secs[1].rule == "heading"
    assert [b.id for b in secs[1].blocks] == ["p000-b003", "p001-b000"]
    assert [b.id for b in secs[2].blocks] == ["p001-b002"]
    assert [b.id for b in secs[3].blocks] == ["p001-b004", "p002-b000"]
    assert secs[1].printed_pages == (119, 120) and secs[3].printed_pages == (120, 121)


def test_resolve_assigns_footnote_chains_to_the_referencing_section():
    meta = _meta(
        [_sec("5-1", "First Section", 0), _sec(None, "Second Section", 1), _sec(None, "Third", 1)]
    )
    secs = resolve(meta, _pages_basic())
    assert [(c.marker, [b.id for b in c.blocks]) for c in secs[1].footnotes] == [
        ("1", ["p000-b004", "p000-b005"])
    ]
    assert [(c.marker, [b.id for b in c.blocks]) for c in secs[3].footnotes] == [
        (None, ["p001-b005"])
    ]
    assert not any(b.type == "page_footnote" for s in secs for b in s.blocks)


def test_resolve_first_child_and_chapter_start_rules():
    pages = [
        [_b("p000-b000", "title", "Chapter Title", 1), _b("p000-b001", "paragraph", "intro text")],
        [
            _b("p001-b000", "paragraph", "key terms continue"),
            _b("p001-b007", "title", "ETHICS in the Real World", 2),
        ],
    ]
    meta = _meta(
        [_sec(None, "Introduction", 0), _sec(None, "End-of-Chapter Homework Material", 1)],
        toc_subtree=[
            [3, "Introduction", 149],
            [3, "End-of-Chapter Homework Material", 150],
            [4, "ETHICS in the Real World", 150],
        ],
        pages=2,
    )
    secs = resolve(meta, pages)
    assert (secs[1].rule, secs[1].anchor, [b.id for b in secs[1].blocks]) == (
        "chapter_start",
        "p000-b001",
        ["p000-b001", "p001-b000"],
    )
    assert (secs[2].rule, secs[2].anchor, [b.id for b in secs[2].blocks]) == (
        "first_child",
        "p001-b007",
        ["p001-b007"],
    )
    assert secs[0].blocks == []


def test_resolve_fails_loudly_naming_section_and_page():
    meta = _meta([_sec(None, "End of Chapter Material", 1)], pages=2)
    pages = [
        [_b("p000-b000", "title", "Chapter Title", 1)],
        [_b("p001-b003", "title", "SUMMARY", 2)],
    ]
    with pytest.raises(SectionError, match="End of Chapter Material.*pdf page 150"):
        resolve(meta, pages)


def test_subheading_entries_take_the_level_below_sections():
    meta = _meta(
        [_sec("5-1", "A", 0)],
        toc_subtree=[[3, "5-1: A", 149], [4, "Sub One", 149], [4, "Sub Two", 150]],
    )
    assert subheading_entries(meta) == [("Sub One", 0), ("Sub Two", 1)]


@pytest.mark.workdir
@pytest.mark.parametrize(
    "book, expect",
    [
        ("bma", {"heading": 9}),
        ("acct", {"heading": 9, "first_child": 1}),
        ("ops", {"heading": 9, "chapter_start": 1}),
        ("corpfin", {"heading": 7}),
        ("stats", {"heading": 7}),
    ],
)
def test_real_chapters_resolve(book, expect):
    import json
    from collections import Counter

    wd = work_chapter(book, "ch05")
    meta = json.loads((wd / "meta.json").read_text())
    secs = resolve(meta, load_pages(v2_path(wd / "chapter" / "hybrid_auto", "chapter")))
    assert Counter(s.rule for s in secs[1:]) == Counter(expect)


@pytest.mark.workdir
def test_bkm_and_strat_need_outline_renames_until_gate_5():
    import json

    for book, title in (("bkm", "End of Chapter Material"), ("strat", "Experiential Exercise")):
        wd = work_chapter(book, "ch05")
        meta = json.loads((wd / "meta.json").read_text())
        pages = load_pages(v2_path(wd / "chapter" / "hybrid_auto", "chapter"))
        try:
            resolve(meta, pages)
        except SectionError as e:
            assert title in str(e)
        else:  # the outline was patched (Task 13): the rename must have taken
            assert not any(s["title"].startswith(title) for s in meta["sections"])
