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


def test_merge_number_only_with_next_joins_split_section_titles():
    toc = [
        [1, "Chapter 5 NPV", 1],
        [2, "5.1", 2],
        [2, "The Payback Period Method", 2],
        [3, "Sub", 2],
        [2, "5.2 Whole", 4],
    ]
    new, changes = patch_toc(toc, [{"rule": "merge_number_only_with_next", "level": 2}])
    assert new == [
        [1, "Chapter 5 NPV", 1],
        [2, "5.1 The Payback Period Method", 2],
        [3, "Sub", 2],
        [2, "5.2 Whole", 4],
    ]
    assert changes == [
        Change(2, 2, "5.1 | The Payback Period Method", "5.1 The Payback Period Method")
    ]


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
