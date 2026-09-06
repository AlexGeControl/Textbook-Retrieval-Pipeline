"""Permanently fix a book's PDF outline so stage 1 parses it with the plain chapter_pattern.

  uv run scripts/patch_toc.py <book>            dry run: table of every outline entry that would change
  uv run scripts/patch_toc.py <book> --apply    write the patched outline into books/<id>/<id>.pdf
  uv run scripts/patch_toc.py <book> --apply --force   even if <id>.orig.pdf exists and differs

Rules come from toc.patches in config/books.yaml (see src/toc.py: number_from_children,
merge_number_only_with_next, rename). --apply copies the current PDF to books/<id>/<id>.orig.pdf
first, rewrites only the outline (incremental save: page objects and the text layer keep their
bytes), then re-opens the file and asserts the outline and page count. Afterwards run
`uv run scripts/check_books.py` so books/manifest.json records the new sha256 and outline size.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # run by path: uv run scripts/patch_toc.py

import pymupdf

from src.config import ROOT, ConfigError, book_cfg
from src.toc import Change, PatchError, patch_toc


def orig_path(pdf: Path) -> Path:
    return pdf.with_name(pdf.stem + ".orig.pdf")


def dry_run(pdf: Path, patches: list[dict]) -> list[Change]:
    doc = pymupdf.open(pdf)
    _new, changes = patch_toc(doc.get_toc(), patches)
    return changes


def apply(pdf: Path, patches: list[dict], force: bool = False) -> list[Change]:
    pdf = Path(pdf)
    orig = orig_path(pdf)
    if orig.exists() and not filecmp.cmp(pdf, orig, shallow=False) and not force:
        raise PatchError(
            f"{orig.name} exists and differs from {pdf.name}: the PDF is already patched. "
            "Re-run with --force to stack patches on it (dry-run first)."
        )
    doc = pymupdf.open(pdf)
    old_toc, page_count = doc.get_toc(), doc.page_count
    new_toc, changes = patch_toc(old_toc, patches)
    if not changes:
        doc.close()
        return []
    if not orig.exists():  # never overwrite an existing original, even with --force
        shutil.copy2(pdf, orig)
    doc.set_toc(new_toc)
    # Incremental save appends the new outline objects; every existing byte (pages, text
    # layer) is untouched. Fall back to a plain save without recompression if refused.
    try:
        doc.save(str(pdf), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    except (RuntimeError, ValueError):
        tmp = pdf.with_suffix(".tmp.pdf")
        doc.save(str(tmp), garbage=0, deflate=False)
        doc.close()
        tmp.replace(pdf)
    else:
        doc.close()
    check = pymupdf.open(pdf)
    if check.get_toc() != new_toc:
        raise PatchError(f"{pdf}: outline after save differs from the patched list")
    if check.page_count != page_count:
        raise PatchError(f"{pdf}: page count changed {page_count} -> {check.page_count}")
    return changes


def print_table(changes: list[Change], total: int) -> None:
    for c in changes:
        print(f"  L{c.level} p{c.page:5d}  {c.old!r} -> {c.new!r}")
    print(f"{len(changes)} of {total} outline entries change")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("book")
    ap.add_argument("--apply", action="store_true", help="write the patched outline into the PDF")
    ap.add_argument("--force", action="store_true", help="allow stacking on an already patched PDF")
    args = ap.parse_args(argv)
    try:
        cfg = book_cfg(args.book)
        pdf = ROOT / cfg["pdf"]
        if not pdf.exists():
            raise PatchError(f"{pdf} missing")
        patches = cfg["toc"].get("patches") or []
        if not patches:
            print(f"{args.book}: no toc.patches configured — nothing to do")
            return 0
        total = len(pymupdf.open(pdf).get_toc())
        if not args.apply:
            changes = dry_run(pdf, patches)
            print(f"{args.book}: dry run of {len(patches)} rule(s) on {pdf.relative_to(ROOT)}")
            print_table(changes, total)
            return 0
        changes = apply(pdf, patches, force=args.force)
        print(
            f"{args.book}: applied {len(patches)} rule(s) to {pdf.relative_to(ROOT)}; original kept as {orig_path(pdf).name}"
        )
        print_table(changes, total)
        if changes:
            print(
                "next: uv run scripts/check_books.py   (records the new sha256 / outline size in books/manifest.json)"
            )
    except (PatchError, ConfigError) as e:
        print(f"patch_toc: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
