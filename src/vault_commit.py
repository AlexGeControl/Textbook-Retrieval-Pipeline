"""Stage 5b — the staging tree vault/<book>/<chNN>/ and its manifest (design §10, §11).

`render` writes the hub, one note per section, assets/ and manifest.json; `check` runs the
battery; `push` (Task 10) copies the tree into the vault. Only certified trees are pushed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from src import patches as patchmod
from src.blocks import Block
from src.config import ROOT, ConfigError
from src.fold import fold
from src.render import Context, RenderError, note_name, render_hub, render_section, slug
from src.review import Chapter, ReviewError, now
from src.sections import Section, SectionError, resolve, subheading_entries

VAULT = Path(os.environ.get("TRP_VAULT", ROOT / "vault"))  # tests redirect it


class CommitError(Exception):
    pass


def staging_dir(ch: Chapter) -> Path:
    return VAULT / ch.book / f"ch{ch.number:02d}"


def pages_of(blocks: list[Block], n_pages: int) -> list[list[Block]]:
    pages: list[list[Block]] = [[] for _ in range(n_pages)]
    for b in blocks:
        pages[b.page_idx].append(b)
    return pages


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_context(ch: Chapter, certified: bool, sections: list[Section]) -> Context:
    review = ch.review
    verdicts = {b["id"]: b["verdict"] for b in review["blocks"]}
    suspects = {
        f["id"] for f in ch.report["flagged_blocks"] if f["reason"] == "running_matter_suspect"
    }
    return Context(
        book=ch.book,
        chapter=ch.number,
        meta=ch.meta,
        cfg=ch.cfg,
        certified=certified,
        certified_at=now()[:10] if certified else None,
        verdicts=verdicts,
        suspects=suspects,
        dropped={i for i in suspects if verdicts.get(i) == "dropped"},
        footnote_ids={c.marker for s in sections for c in s.footnotes if c.marker},
        subheadings={fold(t) for t, _ in subheading_entries(ch.meta)},
    )


def select(sections: list[Section], arg: str) -> list[Section]:
    if arg.isdigit():
        picked = [s for s in sections if s.ordinal == int(arg)]
    else:
        picked = [
            s
            for s in sections
            if arg in (slug(s.title), f"{s.ordinal:02d}-{slug(s.title)}")
            or arg.endswith(f"-{s.ordinal:02d}-{slug(s.title)}")
        ]
    if not picked:
        raise ValueError(f"no section matches {arg!r}; use the ordinal, the slug or the note name")
    return picked


def load_manifest(tree: Path) -> dict:
    p = tree / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {"files": {}, "push": None}


def _asset_source(ch: Chapter, crop: str) -> Path:
    return (ch.hybrid_auto / crop) if crop.startswith("images/") else (ch.wd / crop)


def render_chapter(ch: Chapter, certified: bool, section: str | None = None) -> Path:
    n_pages = ch.meta["pdf_pages"][1] - ch.meta["pdf_pages"][0] + 1
    sections = resolve(ch.meta, pages_of(ch.patched_blocks(), n_pages))
    ctx = build_context(ch, certified, sections)
    tree = staging_dir(ch)
    (tree / "assets").mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(tree)
    files: dict[str, dict] = dict(manifest["files"]) if section else {}
    targets = select(sections, section) if section else sections
    for s in targets:
        text = render_hub(sections, ctx) if s.ordinal == 0 else render_section(s, sections, ctx)
        name = f"{note_name(ctx, s)}.md"
        (tree / name).write_text(text)
        files[name] = {"sha256": _sha(text.encode()), "section": s.ordinal}
    for name, (crop, ordinal) in ctx.assets.items():
        src = _asset_source(ch, crop)
        if not src.exists():
            raise CommitError(f"asset {crop} for {name} is missing under {src.parent}")
        shutil.copyfile(src, tree / "assets" / name)
        files[f"assets/{name}"] = {"sha256": _sha(src.read_bytes()), "section": ordinal}
    if not section:
        for p in [*tree.glob("*.md"), *(tree / "assets").iterdir()]:
            rel = p.name if p.parent == tree else f"assets/{p.name}"
            if rel not in files:
                p.unlink()
    manifest.update(
        {
            "book": ch.book,
            "chapter": ch.number,
            "status": "certified" if certified else ch.report["status"],
            "rendered_at": now(),
            "qa_report_sha256": _sha(ch.report_path.read_bytes()),
            "files": dict(sorted(files.items())),
            "render_log": ctx.log,
        }
    )
    manifest.setdefault("push", None)
    (tree / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return tree


def cmd_render(ch: Chapter, args) -> int:
    tree = render_chapter(ch, certified=False, section=args.section)
    m = load_manifest(tree)
    print(f"render: {tree} ({len(m['files'])} files, status {m['status']}, certified: false)")
    for line in m.get("render_log", []):
        print(f"  log: {line}")
    return 0


def cmd_check(ch: Chapter, args) -> int:
    from src.vault_checks import check_tree

    tree = staging_dir(ch)
    if not (tree / "manifest.json").exists():
        raise CommitError(f"{tree} has no manifest — run render first")
    problems = check_tree(tree, ch, args.section)
    for p in problems:
        print(f"check: {p.where}: {p.msg}")
    print(f"check: {tree} {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 0 if not problems else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="src.vault_commit", description="Stage 5b staging tree")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, func, help_ in (
        ("render", cmd_render, "write vault/<book>/<chNN>/"),
        ("check", cmd_check, "run the battery"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--book", required=True)
        p.add_argument("--chapter", required=True)
        p.add_argument("--section", help="ordinal, slug or note name")
        p.set_defaults(func=func)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        ch = Chapter(args.book, args.chapter)
        return args.func(ch, args)
    except (
        ReviewError,
        SectionError,
        RenderError,
        CommitError,
        ConfigError,
        ValueError,
        patchmod.PatchError,
    ) as e:
        print(f"vault_commit: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
