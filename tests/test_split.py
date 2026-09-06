import json

import pymupdf
import pytest

from src.split import SplitError, build_meta, resolve_chapter, write_chapter

TOC = [
    [1, "Part One", 1],
    [2, "1: Intro", 1],
    [3, "1-1: A", 1],
    [2, "2: Second", 3],
    [3, "2-1: B", 3],
    [3, "Key Takeaways", 4],
    [4, "Sub", 4],
    [1, "Part Two", 5],
    [2, "3: Third", 5],
]
CFG = {
    "toc": {
        "source": "outline",
        "chapter_level": 2,
        "chapter_pattern": r"^(\d+):",
        "page_offset": None,
    },
    "chapter_ranges": {},
}


def make_book(path, labels=True):
    doc = pymupdf.open()
    for i in range(6):
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, 40), f"page {i} body text")
    doc.set_toc(TOC)
    if labels:
        doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": 101}])
    doc.save(path)
    return pymupdf.open(path)


@pytest.fixture
def book(tmp_path):
    return make_book(tmp_path / "book.pdf")


@pytest.fixture
def unlabeled_book(tmp_path):
    return make_book(tmp_path / "plain.pdf", labels=False)


def test_resolve_chapter_in_the_middle(book):
    rng = resolve_chapter(book.get_toc(), CFG, "t", 2, book.page_count)
    assert (rng.slug, rng.title, rng.first, rng.last, rng.toc_index) == ("ch02", "Second", 2, 3, 3)


def test_last_chapter_runs_to_the_end(book):
    rng = resolve_chapter(book.get_toc(), CFG, "t", 3, book.page_count)
    assert (rng.first, rng.last) == (4, 5)


def test_missing_chapter_fails_loudly(book):
    with pytest.raises(SplitError, match=r"t ch09: no level-2 outline entry"):
        resolve_chapter(book.get_toc(), CFG, "t", 9, book.page_count)


def test_ambiguous_chapter_fails_loudly(book):
    toc = book.get_toc() + [[2, "2: Duplicate", 6]]
    with pytest.raises(SplitError, match=r"t ch02: 2 outline entries match"):
        resolve_chapter(toc, CFG, "t", 2, book.page_count)


def test_no_outline_fails_loudly():
    with pytest.raises(SplitError, match=r"t ch01: PDF has no outline"):
        resolve_chapter([], CFG, "t", 1, 6)


def test_chapter_ranges_override_wins(book):
    cfg = {**CFG, "chapter_ranges": {"ch02": [1, 4]}}
    rng = resolve_chapter(book.get_toc(), cfg, "t", 2, book.page_count)
    assert (rng.first, rng.last, rng.title) == (1, 4, "Second")


def test_unconfigured_chapter_level_fails_loudly(book):
    cfg = {"toc": {**CFG["toc"], "chapter_level": None}, "chapter_ranges": {}}
    with pytest.raises(SplitError, match="chapter_level"):
        resolve_chapter(book.get_toc(), cfg, "t", 2, book.page_count)


def test_printed_pages_come_from_labels(book):
    assert build_meta(book, CFG, "t", 2)["printed_pages"] == [103, 104]


def test_printed_pages_fall_back_to_offset(unlabeled_book):
    cfg = {"toc": {**CFG["toc"], "page_offset": 1}, "chapter_ranges": {}}
    assert build_meta(unlabeled_book, cfg, "t", 2)["printed_pages"] == [2, 3]


def test_no_labels_and_no_offset_fails_loudly(unlabeled_book):
    with pytest.raises(SplitError, match="page_offset"):
        build_meta(unlabeled_book, CFG, "t", 2)


def test_meta_records_sections_and_subtree(book):
    meta = build_meta(book, CFG, "t", 2)
    assert meta["book"] == "t" and meta["chapter"] == "ch02" and meta["number"] == 2
    assert meta["title"] == "Second" and meta["pdf_pages"] == [2, 3]
    assert meta["sections"] == [
        {"number": "2-1", "title": "B", "pdf_page": 2, "printed_page": 103, "level": 3},
        {"number": None, "title": "Key Takeaways", "pdf_page": 3, "printed_page": 104, "level": 3},
    ]
    assert meta["toc_subtree"] == [[3, "2-1: B", 2], [3, "Key Takeaways", 3], [4, "Sub", 3]]


def test_write_chapter_produces_pdf_and_meta(book, tmp_path):
    meta = build_meta(book, CFG, "t", 2)
    out = write_chapter(book, meta, tmp_path / "ch02")
    chapter = pymupdf.open(out)
    assert chapter.page_count == 2
    assert "page 2 body" in chapter[0].get_text() and "page 3 body" in chapter[1].get_text()
    assert json.loads((tmp_path / "ch02" / "meta.json").read_text()) == meta
