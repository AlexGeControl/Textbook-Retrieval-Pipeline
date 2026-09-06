import pytest

from src.toc import ChapterEntry, chapter_entries, level_stats, normalize_toc, number_from_sections

# BMA-like: Parts at 1, numbered chapters at 2
TITLED = [
    [1, "Part One", 1],
    [2, "1: Intro", 1],
    [3, "1-1: A", 1],
    [2, "2: Second", 3],
    [1, "Part Two", 5],
    [2, "3: Third", 5],
]
# STATS-like: unnumbered chapter titles at 1, numbered sections at 2, appendices interleaved
SECTIONED = [
    [1, "Preface", 1],
    [1, "Data and Statistics", 3],
    [2, "1.1  Applications", 3],
    [2, "1.2  Data", 4],
    [1, "Chapter 1 Appendix", 6],
    [2, "Appendix 1.1  JMP", 6],
    [1, "Descriptive Statistics", 7],
    [2, "2.1 Summarizing", 7],
]


def test_chapter_entries_from_titles():
    cfg = {"chapter_level": 2, "chapter_pattern": r"^(\d+):", "chapter_number_from": "title"}
    assert chapter_entries(TITLED, cfg) == [
        ChapterEntry(1, 1, "Intro"),
        ChapterEntry(3, 2, "Second"),
        ChapterEntry(5, 3, "Third"),
    ]


def test_no_normalize_key_means_titles_as_is():
    cfg = {"chapter_level": 2, "chapter_pattern": r"^(\d+):"}
    assert [e.number for e in chapter_entries(TITLED, cfg)] == [1, 2, 3]


def test_number_from_sections_preserves_positions_and_skips_numbered_titles():
    out = number_from_sections(SECTIONED, 1)
    assert len(out) == len(SECTIONED) and out[1][1] == "1: Data and Statistics"
    assert (
        out[0][1] == "Preface"
        and out[4][1] == "Chapter 1 Appendix"
        and out[6][1] == "2: Descriptive Statistics"
    )
    assert SECTIONED[1][1] == "Data and Statistics"  # input untouched


def test_unknown_normalizer_is_an_error():
    with pytest.raises(ValueError, match="unknown step"):
        normalize_toc(TITLED, {"chapter_level": 2, "normalize": ["nope"]})


def test_chapter_entries_after_number_from_sections_normalizer():
    cfg = {
        "chapter_level": 1,
        "chapter_pattern": r"^(\d+): ",
        "normalize": ["number_from_sections"],
    }
    assert chapter_entries(SECTIONED, cfg) == [
        ChapterEntry(1, 1, "Data and Statistics"),
        ChapterEntry(6, 2, "Descriptive Statistics"),
    ]  # Preface has no numbered child; "Chapter 1 Appendix" children start with "Appendix"


def test_unconfigured_level_yields_nothing():
    assert chapter_entries(TITLED, {"chapter_level": None, "chapter_pattern": None}) == []
    assert chapter_entries(TITLED, {"chapter_level": 2, "chapter_pattern": None}) == []


def test_level_stats_counts_entries_and_numbered_titles():
    stats = level_stats(TITLED)
    assert stats[1] == (2, 0) and stats[2] == (3, 3) and stats[3] == (1, 1)
    assert level_stats(SECTIONED)[2] == (4, 3)
