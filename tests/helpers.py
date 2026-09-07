"""Fixture-cache lookup shared by unit tests.

The unit tier reads cached MinerU outputs under tests/fixtures/cache/<book>/<set>/hybrid_auto/
(gitignored). Seed it once from work/sanity/ (plan Task 1) or regenerate with
`uv run pytest -m integration` against the live server.
"""

import json
import shutil
from pathlib import Path

import pymupdf
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


def make_work_dir(
    root: Path,
    monkeypatch,
    *,
    pages: list[list[dict]],
    hunks: tuple | list = (),
    flagged: tuple | list = (),
    spot: tuple | list = (),
    sections: tuple | list = (),
    toc_subtree: tuple | list = (),
    pdf_lines: tuple | list = (),
    book: str = "bma",
    ch: int = 5,
    title: str = "Net Present Value and Other Investment Criteria",
) -> Path:
    """A complete fake work/<book>/chNN/ under `root`; src.config.WORK is pointed at `root`.

    `pages` is raw content_list_v2 (one list per page). `pdf_lines` puts one text line per
    page on a 1000x1000 pt page at y = 100, so block bboxes in 0-1000 units are also points.
    """
    import src.config
    from src.extract import hybrid_auto_dir

    monkeypatch.setattr(src.config, "WORK", root)
    monkeypatch.setattr("tests.helpers.WORK", root)
    monkeypatch.setenv("TRP_WORK", str(root))  # CLI subprocesses read the env, not the patch
    monkeypatch.setenv("TRP_VAULT", str(root / "vault"))
    try:
        import src.vault_commit

        monkeypatch.setattr(src.vault_commit, "VAULT", root / "vault")
    except ImportError:  # before Task 9
        pass
    wd = root / book / f"ch{ch:02d}"
    ha = hybrid_auto_dir(wd)
    (ha / "images").mkdir(parents=True)
    (wd / "crops").mkdir()
    doc = pymupdf.open()
    for i, _ in enumerate(pages):
        page = doc.new_page(width=1000, height=1000)
        if i < len(pdf_lines) and pdf_lines[i]:
            page.insert_text((80, 100), pdf_lines[i], fontsize=12)
    doc.save(wd / "chapter.pdf")
    for f in (*flagged, *spot):
        target = (ha / f["crop"]) if f["crop"].startswith("images/") else (wd / f["crop"])
        target.parent.mkdir(parents=True, exist_ok=True)
        pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False).save(target)
    (ha / "chapter_content_list_v2.json").write_text(json.dumps(pages))
    (ha / "chapter_middle.json").write_text(
        json.dumps({"_effort": "high", "_version_name": "3.4.5"})
    )
    first_pdf, first_printed = 149, 119
    meta = {
        "book": book,
        "chapter": f"ch{ch:02d}",
        "number": ch,
        "title": title,
        "pdf_pages": [first_pdf, first_pdf + len(pages) - 1],
        "printed_pages": [first_printed, first_printed + len(pages) - 1],
        "sections": list(sections),
        "toc_subtree": list(toc_subtree),
    }
    (wd / "meta.json").write_text(json.dumps(meta))
    blocks = sum(len(p) for p in pages)
    guardrail = {
        "pages": len(pages),
        "counts": {
            "pdf_tokens": 0,
            "md_tokens": 0,
            "matched_blocks": blocks,
            "unmatched_blocks": 0,
            "hunks": len(hunks),
            "hunks_inline_math": 0,
        },
        "hunks": list(hunks),
    }
    (wd / "guardrail.json").write_text(json.dumps(guardrail))
    report = {
        "book": book,
        "chapter": f"ch{ch:02d}",
        "pages": meta["printed_pages"],
        "extraction": {
            "backend": "hybrid-http-client",
            "effort": "high",
            "mineru_version": "3.4.5",
            "timestamp": "2026-09-06T13:03:00+00:00",
        },
        "counts": {
            "blocks": blocks,
            "tables": sum(b["type"] == "table" for p in pages for b in p),
            "formulas": sum(b["type"] == "equation_interline" for p in pages for b in p),
            "figures": sum(b["type"] in ("image", "chart") for p in pages for b in p),
            "diff_hunks": len(hunks),
        },
        "diff_hunks": list(hunks),
        "flagged_blocks": list(flagged),
        "spot_check": list(spot),
        "status": "pending_review",
    }
    (wd / "qa_report.json").write_text(json.dumps(report))
    return wd


def work_chapter_sandbox(book: str, chapter: str, root: Path, monkeypatch) -> Path:
    """A writable copy of work/<book>/<chNN>/ under `root`, with src.config.WORK redirected there.

    The stage-2 outputs and chapter.pdf are symlinked (read-only by contract); the stage 3-5
    JSON files are copied, so a test that runs the pre-pass or the checks never rewrites the real
    qa_report.json / patches.json (gate 4, 2026-09-07: a test run wiped a certified render's sha).
    """
    import src.config

    real = work_chapter(book, chapter)
    box = root / book / chapter
    box.mkdir(parents=True)
    for name in ("chapter.pdf", "chapter", "crops"):
        if (real / name).exists():
            (box / name).symlink_to((real / name).resolve())
    for name in ("meta.json", "guardrail.json", "qa_report.json", "patches.json"):
        if (real / name).exists():
            shutil.copyfile(real / name, box / name)
    monkeypatch.setattr(src.config, "WORK", root)
    monkeypatch.setenv("TRP_WORK", str(root))
    return box
