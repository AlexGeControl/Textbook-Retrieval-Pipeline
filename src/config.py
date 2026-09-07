"""Repo paths, config/books.yaml access and chapter slug helpers shared by all stages."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BOOKS_YAML = ROOT / "config" / "books.yaml"
READINGS_DIR = ROOT / "config" / "readings"
WORK = Path(os.environ.get("TRP_WORK", ROOT / "work"))


class ConfigError(Exception):
    pass


def load_books(path: Path = BOOKS_YAML) -> dict[str, dict]:
    return yaml.safe_load(Path(path).read_text())["books"]


def book_cfg(book_id: str, books: dict[str, dict] | None = None) -> dict:
    books = load_books() if books is None else books
    if book_id not in books:
        known = ", ".join(books)
        raise ConfigError(f"{book_id}: not in {BOOKS_YAML.relative_to(ROOT)} (known: {known})")
    return books[book_id]


def chapter_slug(chapter: int | str) -> str:
    """5 / '5' / 'ch5' / 'ch05' -> 'ch05'."""
    m = re.fullmatch(r"(?:ch)?0*(\d+)", str(chapter).strip())
    if not m:
        raise ConfigError(f"bad chapter {chapter!r}: expected a number or chNN")
    return f"ch{int(m.group(1)):02d}"


def chapter_number(chapter: int | str) -> int:
    return int(chapter_slug(chapter)[2:])


def work_dir(book_id: str, chapter: int | str) -> Path:
    return WORK / book_id / chapter_slug(chapter)
