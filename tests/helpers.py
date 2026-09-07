"""Fixture-cache lookup shared by unit tests.

The unit tier reads cached MinerU outputs under tests/fixtures/cache/<book>/<set>/hybrid_auto/
(gitignored). Seed it once from work/sanity/ (plan Task 1) or regenerate with
`uv run pytest -m integration` against the live server.
"""

from pathlib import Path

import pytest

FIXTURES = Path("tests/fixtures")
CACHE = FIXTURES / "cache"
# (book, set) -> page count of tests/fixtures/<book>/<set>.pdf
FIXTURE_SETS = {
    ("bma", "table"): 2,
    ("bma", "formula"): 1,
    ("bkm", "chart"): 3,
    ("bkm", "text-only"): 4,
}


def cached_hybrid_auto(book: str, name: str) -> Path:
    d = CACHE / book / name / "hybrid_auto"
    if not (d / f"{name}_content_list.json").exists():
        pytest.skip(
            f"fixture cache missing: {d} — seed from work/sanity or run pytest -m integration"
        )
    return d


WORK = Path("work")


def work_chapter(book: str, chapter: str) -> Path:
    """work/<book>/<chNN>/ with a qa_report.json, or skip (the dirs are machine-local)."""
    d = WORK / book / chapter
    if not (d / "qa_report.json").exists():
        pytest.skip(f"work dir missing: {d} — run make chapter BOOK={book} CH={int(chapter[2:])}")
    return d
