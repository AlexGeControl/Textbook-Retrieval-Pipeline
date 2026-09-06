"""Optional per-course reading lists (design §3).

config/readings/<course>.yaml maps book id -> chapter numbers. No file, or a book missing from
it, means every chapter the outline (or chapter_ranges) exposes.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config import READINGS_DIR
from src.toc import chapter_entries


def load_readings(course: str, readings_dir: Path = READINGS_DIR) -> dict[str, list[int]] | None:
    path = Path(readings_dir) / f"{course}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text()) or {}
    return {book: [int(n) for n in (chapters or [])] for book, chapters in data.items()}


def outline_chapters(toc: list[list], book_cfg: dict) -> list[int]:
    return [e.number for e in chapter_entries(toc, book_cfg["toc"])]


def list_chapters(
    book_id: str, book_cfg: dict, toc: list[list], readings: dict | None
) -> list[int]:
    if readings is not None and book_id in readings:
        return sorted(set(readings[book_id]))
    numbers = set(outline_chapters(toc, book_cfg))
    numbers |= {int(slug[2:]) for slug in (book_cfg.get("chapter_ranges") or {})}
    return sorted(numbers)
