"""Optional per-course reading lists (design §3).

config/readings/<course>.yaml maps book id -> chapter numbers. No file, or a book missing from
it, means every chapter the outline (or chapter_ranges) exposes.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.config import READINGS_DIR


def load_readings(course: str, readings_dir: Path = READINGS_DIR) -> dict[str, list[int]] | None:
    path = Path(readings_dir) / f"{course}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text()) or {}
    return {book: [int(n) for n in (chapters or [])] for book, chapters in data.items()}


def outline_chapters(toc: list[list], book_cfg: dict) -> list[int]:
    level = book_cfg["toc"].get("chapter_level")
    pattern = book_cfg["toc"].get("chapter_pattern")
    if level is None or pattern is None:
        return []
    rx = re.compile(pattern)
    numbers = []
    for lvl, title, _page in toc:
        if lvl == level and (m := rx.search(title.strip())):
            numbers.append(int(m.group(1)))
    return numbers


def list_chapters(
    book_id: str, book_cfg: dict, toc: list[list], readings: dict | None
) -> list[int]:
    if readings is not None and book_id in readings:
        return sorted(set(readings[book_id]))
    numbers = set(outline_chapters(toc, book_cfg))
    numbers |= {int(slug[2:]) for slug in (book_cfg.get("chapter_ranges") or {})}
    return sorted(numbers)
