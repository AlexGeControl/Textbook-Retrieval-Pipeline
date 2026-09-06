import re
from pathlib import Path

import pytest
import yaml

from src.config import ConfigError, book_cfg, chapter_number, chapter_slug, load_books, work_dir

CFG = yaml.safe_load(Path("config/books.yaml").read_text())["books"]


def test_books_yaml_matches_landing_zone():
    assert set(CFG) == {"bkm", "bma", "ops", "strat", "stats", "corpfin", "acct"}
    for bid, b in CFG.items():
        assert b["pdf"] == f"books/{bid}/{bid}.pdf"


def test_every_book_has_the_stage1_keys():
    for bid, b in CFG.items():
        assert "manual_ranges" not in b, f"{bid}: manual_ranges was renamed body_range"
        assert set(b["body_range"]) == {"begin", "end"}
        assert {"source", "chapter_level", "chapter_pattern", "page_offset"} <= set(b["toc"])
        assert set(b["toc"]) <= {
            "source",
            "chapter_level",
            "chapter_pattern",
            "page_offset",
            "patches",
        }
        assert b["toc"]["chapter_pattern"] is not None, f"{bid}: every book is configured now"
        assert isinstance(b.get("chapter_ranges", {}), dict)
        pattern = b["toc"]["chapter_pattern"]
        if pattern is not None:
            assert re.compile(pattern).groups == 1, f"{bid}: pattern needs one capture group"


def test_benchmark_book_is_fully_configured():
    toc = CFG["bma"]["toc"]
    assert (toc["chapter_level"], toc["chapter_pattern"], toc["page_offset"]) == (2, r"^(\d+):", 31)
    assert CFG["bkm"]["toc"]["chapter_level"] == 2 and CFG["bkm"]["toc"]["page_offset"] == 29


def test_load_books_and_book_cfg():
    books = load_books()
    assert book_cfg("bma", books)["course"] == "mitx"
    with pytest.raises(ConfigError, match="nope"):
        book_cfg("nope", books)


def test_chapter_slug_accepts_number_and_slug():
    assert (
        chapter_slug(5)
        == chapter_slug("5")
        == chapter_slug("ch05")
        == chapter_slug("ch5")
        == "ch05"
    )
    assert chapter_number("ch12") == 12
    with pytest.raises(ConfigError, match="five"):
        chapter_slug("five")


def test_work_dir_layout():
    assert work_dir("bma", 5).as_posix().endswith("work/bma/ch05")
