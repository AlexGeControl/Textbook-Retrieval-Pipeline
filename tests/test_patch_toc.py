import pymupdf
import pytest

from scripts.patch_toc import PatchError, apply, dry_run
from src.toc import Change, patch_toc

SECTIONED_TOC = [
    [1, "Preface", 1],
    [1, "Data and Statistics", 2],
    [2, "1.1  Applications", 2],
    [2, "1.2  Data", 3],
    [1, "Chapter 1 Appendix", 4],
    [2, "Appendix 1.1  JMP", 4],
    [1, "Descriptive Statistics", 5],
    [2, "2.1 Summarizing", 5],
]
NUMBER_FROM_CHILDREN = [{"rule": "number_from_children", "level": 1}]


def make_book(path, toc=SECTIONED_TOC):
    doc = pymupdf.open()
    for i in range(6):
        doc.new_page(width=200, height=200).insert_text((20, 40), f"page {i} body")
    doc.set_toc(toc)
    doc.save(path)
    return path


# ---- pure rules -------------------------------------------------------------------------------


def test_number_from_children_prefixes_unnumbered_chapter_titles():
    new, changes = patch_toc(SECTIONED_TOC, NUMBER_FROM_CHILDREN)
    assert new[1] == [1, "1: Data and Statistics", 2] and new[6] == [
        1,
        "2: Descriptive Statistics",
        5,
    ]
    assert new[0] == SECTIONED_TOC[0] and new[4] == SECTIONED_TOC[4]  # Preface, Appendix untouched
    assert changes == [
        Change(1, 2, "Data and Statistics", "1: Data and Statistics"),
        Change(1, 5, "Descriptive Statistics", "2: Descriptive Statistics"),
    ]
    assert SECTIONED_TOC[1][1] == "Data and Statistics"  # input not mutated
    assert patch_toc(new, NUMBER_FROM_CHILDREN)[1] == []  # idempotent


def test_rename_rewrites_matching_titles_and_rejects_zero_matches():
    new, changes = patch_toc(
        SECTIONED_TOC,
        [{"rule": "rename", "level": 1, "match": r"^Preface$", "replace": "Front matter"}],
    )
    assert new[0] == [1, "Front matter", 1] and len(changes) == 1
    with pytest.raises(PatchError, match="matched no level-1 entries"):
        patch_toc(
            SECTIONED_TOC, [{"rule": "rename", "level": 1, "match": r"^Prefaec$", "replace": "x"}]
        )


def test_unknown_rule_is_an_error():
    with pytest.raises(PatchError, match="unknown rule"):
        patch_toc(SECTIONED_TOC, [{"rule": "nope", "level": 1}])


# ---- script: dry run and apply -----------------------------------------------------------------


def test_dry_run_reports_changes_and_writes_nothing(tmp_path):
    pdf = make_book(tmp_path / "s.pdf")
    before = pdf.read_bytes()
    changes = dry_run(pdf, NUMBER_FROM_CHILDREN)
    assert [c.new for c in changes] == ["1: Data and Statistics", "2: Descriptive Statistics"]
    assert pdf.read_bytes() == before and not (tmp_path / "s.orig.pdf").exists()


def test_apply_rewrites_outline_only_and_keeps_the_original(tmp_path):
    pdf = make_book(tmp_path / "s.pdf")
    before = pdf.read_bytes()
    text0 = pymupdf.open(pdf)[0].get_text()
    changes = apply(pdf, NUMBER_FROM_CHILDREN)
    assert len(changes) == 2
    assert (tmp_path / "s.orig.pdf").read_bytes() == before
    doc = pymupdf.open(pdf)
    assert doc.page_count == 6 and doc[0].get_text() == text0
    assert doc.get_toc()[1] == [1, "1: Data and Statistics", 2]
    assert doc.get_toc()[6] == [1, "2: Descriptive Statistics", 5]


def test_apply_refuses_to_stack_without_force(tmp_path):
    pdf = make_book(tmp_path / "s.pdf")
    apply(pdf, NUMBER_FROM_CHILDREN)
    with pytest.raises(PatchError, match="orig.pdf"):
        apply(pdf, [{"rule": "rename", "level": 1, "match": "^1: ", "replace": "One: "}])
    apply(pdf, [{"rule": "rename", "level": 1, "match": "^1: ", "replace": "One: "}], force=True)
    assert pymupdf.open(pdf).get_toc()[1][1] == "One: Data and Statistics"


def test_apply_with_nothing_to_change_is_a_noop(tmp_path):
    pdf = make_book(tmp_path / "s.pdf")
    before = pdf.read_bytes()
    assert (
        apply(pdf, [{"rule": "rename", "level": 1, "match": "^Preface$", "replace": "Preface"}])
        == []
    )
    assert pdf.read_bytes() == before and not (tmp_path / "s.orig.pdf").exists()


# ---- rebuild_numbered_sections + insert (corpfin) ---------------------------------------------

CORPFIN_LIKE = [
    [1, "Preface", 1],
    [2, "New to this edition", 1],  # front matter: outside any numbered chapter, left alone
    [1, "Chapter 1 Intro", 2],
    [2, "THE FINANCIAL MANAGER", 2],  # promoted subheading -> demoted to level 3
    [2, "The Corporate Firm", 3],
    [3, "THE SOLE PROPRIETORSHIP", 3],
    [2, "1.2", 3],  # id split from its title
    [3, "THE CORPORATION", 4],
    [2, "The Agency Problem 1.3", 5],  # title and id glued in one entry
    [2, "The Balance Sheet 2.1", 7],  # first section of chapter 2 hosted under chapter 1
    [1, "Chapter 2 Statements", 7],
    [2, "LIQUIDITY", 8],
    [2, "The Income Statement 2.2", 9],
    [2, "Bank Loans", 10],  # two titles then two ids: pair the id run with the title run's tail
    [2, "International Bonds", 10],
    [2, "2.3", 10],
    [2, "2.4", 10],
    [2, "2.5 Already Fine", 11],  # already "<id> <title>": untouched, no change reported
]
REBUILD = [{"rule": "rebuild_numbered_sections", "level": 2}]


def test_rebuild_pairs_merges_reparents_and_demotes():
    new, changes = patch_toc(CORPFIN_LIKE, REBUILD)
    assert new == [
        [1, "Preface", 1],
        [2, "New to this edition", 1],
        [1, "Chapter 1 Intro", 2],
        [3, "THE FINANCIAL MANAGER", 2],
        [2, "1.2 The Corporate Firm", 3],
        [3, "THE SOLE PROPRIETORSHIP", 3],
        [3, "THE CORPORATION", 4],
        [2, "1.3 The Agency Problem", 5],
        [1, "Chapter 2 Statements", 7],
        [2, "2.1 The Balance Sheet", 7],
        [3, "LIQUIDITY", 8],
        [2, "2.2 The Income Statement", 9],
        [2, "2.3 Bank Loans", 10],
        [2, "2.4 International Bonds", 10],
        [2, "2.5 Already Fine", 11],
    ]
    notes = sorted(c.note for c in changes)
    assert notes.count("merged") == 5 and notes.count("merged, moved to chapter 2") == 1
    assert notes.count("demoted to level 3") == 2 and "unpaired id" not in notes
    assert Change(2, 3, "The Corporate Firm | 1.2", "1.2 The Corporate Firm", "merged") in changes
    assert not any(c.new == "2.5 Already Fine" for c in changes)
    assert patch_toc(new, REBUILD)[1] == []  # idempotent


def test_rebuild_reports_an_id_it_cannot_pair():
    toc = [[1, "Chapter 4 X", 1], [2, "4.1 Fine", 1], [2, "4.2", 3], [1, "Chapter 5 Y", 4]]
    new, changes = patch_toc(toc, REBUILD)
    assert new == toc  # nothing to pair with: entry left as-is, not invented
    assert [c.note for c in changes] == ["unpaired id"] and changes[0].old == "4.2"


def test_insert_after_a_unique_match():
    toc = [[1, "Chapter 1 Intro", 2], [2, "1.2 Firm", 3], [1, "Chapter 10 Other", 9]]
    rule = [
        {
            "rule": "insert",
            "level": 2,
            "title": "1.1 What Is Corporate Finance?",
            "page": 2,
            "after": {"level": 1, "match": r"^Chapter 1\b"},
        }
    ]
    new, changes = patch_toc(toc, rule)
    assert new == [
        [1, "Chapter 1 Intro", 2],
        [2, "1.1 What Is Corporate Finance?", 2],
        [2, "1.2 Firm", 3],
        [1, "Chapter 10 Other", 9],
    ]
    assert changes == [Change(2, 2, "", "1.1 What Is Corporate Finance?", "inserted")]
    with pytest.raises(PatchError, match="matched 0"):
        patch_toc(toc, [{**rule[0], "after": {"level": 1, "match": "^Nope"}}])
    with pytest.raises(PatchError, match="matched 2"):
        patch_toc(toc, [{**rule[0], "after": {"level": 1, "match": "^Chapter"}}])
