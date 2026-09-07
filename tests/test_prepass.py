import json
from collections import Counter

import pytest

from src.blocks import Block, Span
from src.prepass import (
    duplicate_unit,
    edge_kind,
    is_folio_core,
    run,
    strip_context,
    strip_moved,
)
from src.review import Chapter
from tests.helpers import make_work_dir, work_chapter


def test_strip_context_keeps_only_the_core():
    assert strip_context(["a", "b", "capital", "c", "d"], ["a", "b", "capi", "tal", "c", "d"]) == (
        ["capital"],
        ["capi", "tal"],
    )
    assert strip_context(["x", "y"], ["x", "y"]) == ([], [])
    assert strip_context(
        ["project", "X.", "Third,"], ["project", "X.", "Third,", "use", "this"]
    ) == (
        [],
        ["use", "this"],
    )


def test_edge_kind_one_glyph_or_short_superscript_run():
    assert edge_kind(["company"], ["compan"]) == "end"
    assert edge_kind(["T", "he"], ["he"]) == "start"
    assert edge_kind(["flows.16"], ["flows."]) == "end"
    assert edge_kind(["company"], ["comp"]) is None
    assert edge_kind(["m"], ["μ"]) is None


def test_is_folio_core():
    assert is_folio_core(["Page", "83", "Page", "83"])
    assert not is_folio_core(["Page", "83", "is"])
    assert not is_folio_core([])


def _para(id_, text):
    return Block(
        id=id_,
        index=int(id_[-3:]),
        type="paragraph",
        page_idx=0,
        bbox=(0, 0, 10, 10),
        spans=(Span("text", text),),
    )


def test_duplicate_unit_collapses_repeats():
    unit = "Taxes and project NPV. Ms. Potts has a problem."
    assert duplicate_unit(_para("p000-b000", " ".join([unit] * 3))) == (" ".join([unit] * 3), unit)
    assert duplicate_unit(_para("p000-b001", "no repeat here")) is None
    assert duplicate_unit(_para("p000-b002", "a a")) == ("a a", "a")


def test_strip_moved_removes_prefix_and_suffix_found_in_pool():
    pool = Counter({"usethis": 1, "wherec0": 1})
    rest, moved = strip_moved(["use", "this", "opportunity", "cost"], pool)
    assert (rest, moved) == (["opportunity", "cost"], True)
    rest, moved = strip_moved(["opportunity", "cost", "where", "C0"], pool)
    assert (rest, moved) == (["opportunity", "cost"], True)
    assert strip_moved(["nothing"], pool) == (["nothing"], False)


def _page(*blocks):
    return list(blocks)


def _p(text, bbox=(70, 80, 600, 110)):
    return {
        "type": "paragraph",
        "bbox": list(bbox),
        "content": {"paragraph_content": [{"type": "text", "content": text}]},
    }


def _aside(text, bbox=(900, 900, 950, 950)):
    return {
        "type": "page_aside_text",
        "bbox": list(bbox),
        "content": {"page_aside_text_content": [{"type": "text", "content": text}]},
    }


def _hunk(anchor, pdf, md, page=119):
    return {"page": page, "anchor": anchor, "pdf_text": pdf, "md_text": md}


def _patches(wd):
    return json.loads((wd / "patches.json").read_text())["patches"]


def test_same_letters_patches_from_raw_pdf_words(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("the capi tal budget of Value’s firm"))],
        hunks=[_hunk("p000-b000", "the capital budget of", "the capi tal budget of")],
        pdf_lines=["the capital budget of Value’s firm"],
    )
    counts = run(Chapter("bma", 5))
    assert counts == Counter({"same_letters": 1})
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["review"]["hunks"][0]["verdict"] == "accepted_pdf"
    (patch,) = _patches(wd)
    assert (patch["op"], patch["old"], patch["new"], patch["source"]) == (
        "replace",
        "capi tal",
        "capital",
        "prepass",
    )


def test_edge_glyph_and_drop_cap(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("he payback rule says the compan pays"))],
        hunks=[
            _hunk("p000-b000", "T he payback rule", "he payback rule"),
            _hunk("p000-b000", "the company pays", "the compan pays"),
        ],
        pdf_lines=["T he payback rule says the company pays"],
    )
    counts = run(Chapter("bma", 5))
    assert counts == Counter({"edge_glyph": 2})
    news = sorted(p["new"] for p in _patches(wd))
    assert news == ["The payback", "company"]


def test_junk_drops_a_block_without_text_layer_words(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("body text here"), _aside("#"))],
        hunks=[_hunk("p000-b001", "", "#")],
        pdf_lines=["body text here"],
    )
    assert run(Chapter("bma", 5)) == Counter({"junk": 1})
    (patch,) = _patches(wd)
    assert (patch["op"], patch["block"]) == ("drop_block", "p000-b001")


def test_folio_injection_is_removed(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("in setup mode, it Page 83 Page 83 is fairly intuitive"))],
        hunks=[
            _hunk(
                "p000-b000",
                "setup mode, it is fairly intuitive",
                "setup mode, it Page 83 Page 83 is fairly intuitive",
            )
        ],
        pdf_lines=["in setup mode, it is fairly intuitive"],
    )
    assert run(Chapter("bma", 5)) == Counter({"folio": 1})
    (patch,) = _patches(wd)
    assert (patch["old"], patch["new"]) == ("Page 83 Page 83 ", "")


def test_move_pair_across_pages_needs_no_patch(tmp_path, monkeypatch):
    make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[
            _page(_p("project X. Third, use this opportunity cost")),
            _page(_p(""), _p("where C0 is")),
        ],
        hunks=[
            _hunk("p000-b000", "project X. Third,", "project X. Third, use this opportunity cost"),
            _hunk("p001-b001", "use this opportunity cost where C0 is", "where C0 is", page=120),
        ],
        pdf_lines=["project X. Third,", "use this opportunity cost where C0 is"],
    )
    assert run(Chapter("bma", 5)) == Counter({"move": 2})


def test_duplicate_block_is_collapsed(tmp_path, monkeypatch):
    unit = "Ms. Potts has a problem."
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p(" ".join([unit] * 3)))],
        hunks=[_hunk("p000-b000", "Ms. Potts has a problem.", " ".join([unit] * 3))],
        pdf_lines=[unit],
    )
    assert run(Chapter("bma", 5)) == Counter({"duplicate": 1})
    (patch,) = _patches(wd)
    assert patch["new"] == unit


def test_unanchorable_hunk_stays_for_the_reviewer(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("the the budget"))],
        hunks=[_hunk("p000-b000", "the the budget", "the the budget")],
        pdf_lines=["the the budget"],
    )
    assert run(Chapter("bma", 5)) == Counter({"needs_eyes": 1})
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["review"]["hunks"][0]["verdict"] == "unresolved"
    assert _patches(wd) == []


def test_rerun_replaces_prepass_patches_and_keeps_review_ones(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("the capi tal budget"))],
        hunks=[_hunk("p000-b000", "the capital budget", "the capi tal budget")],
        pdf_lines=["the capital budget"],
    )
    ch = Chapter("bma", 5)
    run(ch)
    from src.patches import Patch

    ch = Chapter("bma", 5)
    ch.patches.append(
        Patch("rv-0001", "p000-b000", "replace", "budget", "budgets", "review", "manual")
    )
    ch.save()
    run(Chapter("bma", 5))
    ids = sorted(p["id"] for p in _patches(wd))
    assert ids == ["pp-0001", "rv-0001"]


def test_duplicate_unit_collapses_line_repeats_with_different_periods():
    # mineru emitted each line of bma ch06 p026-b007 fifteen times before the next line
    line1, line2 = "Ms. Potts has a problem.", "The kiln costs $400,000 to install."
    raw = " ".join([line1] * 3 + [line2] * 4)
    assert duplicate_unit(_para("p000-b000", raw)) == (raw, f"{line1} {line2}")


def test_duplicate_needs_text_layer_confirmation(tmp_path, monkeypatch):
    unit = "Ms. Potts has a problem."
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p(" ".join([unit] * 3)))],
        hunks=[_hunk("p000-b000", unit, " ".join([unit] * 3))],
        pdf_lines=["Ms. Potts has a problem indeed."],
    )
    assert run(Chapter("bma", 5)) == Counter({"needs_eyes": 1})
    report = json.loads((wd / "qa_report.json").read_text())
    assert "text layer" in report["review"]["hunks"][0]["note"]
    assert _patches(wd) == []


def test_junk_hunk_spanning_two_blocks_drops_both(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_p("body text here"), _aside("#"), _aside("#", bbox=(900, 700, 950, 750)))],
        hunks=[_hunk("p000-b001", "", "# #")],
        pdf_lines=["body text here"],
    )
    assert run(Chapter("bma", 5)) == Counter({"junk": 1})
    patches = _patches(wd)
    assert [(p["op"], p["block"]) for p in patches] == [
        ("drop_block", "p000-b001"),
        ("drop_block", "p000-b002"),
    ]
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["review"]["hunks"][0]["patches"] == ["pp-0001", "pp-0002"]


@pytest.mark.workdir
def test_bma_ch05_prepass_numbers():
    work_chapter("bma", "ch05")
    counts = run(Chapter("bma", 5))
    assert sum(counts.values()) == 57
    assert counts["needs_eyes"] <= 20, counts
    ch = Chapter("bma", 5)
    dropped = {p.block for p in ch.patches if p.op == "drop_block"}
    assert {"p009-b015", "p009-b019"} <= dropped  # the `#` margin icons


@pytest.mark.workdir
def test_bma_ch06_duplicate_and_ops_folio():
    work_chapter("bma", "ch06")
    run(Chapter("bma", 6))
    ch = Chapter("bma", 6)
    assert any(p.rule == "duplicate" and p.block == "p026-b007" for p in ch.patches)
    work_chapter("ops", "ch05")
    run(Chapter("ops", 5))
    ch = Chapter("ops", 5)
    assert sum(p.rule == "folio" for p in ch.patches) >= 5
