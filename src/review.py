"""Stage 5 review record: the `review` key of qa_report.json and the CLI that writes it.

Design §8, §11. Every write validates the whole report (qa_schema.validate + validate_review)
and applies the whole patch list before saving, so a bad verdict or patch never reaches disk.
`finalize` derives `status`; nobody types it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src import patches as patchmod
from src.blocks import Block, load_blocks, v2_path
from src.config import ConfigError, book_cfg, chapter_number, work_dir
from src.extract import STEM, hybrid_auto_dir
from src.qa_schema import (
    BLOCK_VERDICTS,
    CHECK_KEYS,
    FOOTNOTE_VERDICTS,
    HEADING_VERDICTS,
    HUNK_VERDICTS,
    SPOT_VERDICTS,
    SchemaError,
    validate,
    validate_review,
)


class ReviewError(Exception):
    pass


def now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def new_review(report: dict) -> dict:
    """A fresh review key: one unresolved entry per hunk, flagged block and spot check."""
    return {
        "prepass": {"timestamp": "", "counts": {}},
        "hunks": [
            {"verdict": "unresolved", "rule": "", "patches": [], "note": ""}
            for _ in report["diff_hunks"]
        ],
        "blocks": [
            {
                "id": f["id"],
                "verdict": "unresolved",
                "checks": dict.fromkeys(CHECK_KEYS),
                "patches": [],
                "note": "",
            }
            for f in report["flagged_blocks"]
        ],
        "spot_check": [
            {"id": s["id"], "verdict": "unresolved", "note": ""} for s in report["spot_check"]
        ],
        "headings": {"sections": [0, 0], "subheadings": [0, 0], "missing": []},
        "footnotes": {"definitions": 0, "references": 0, "unmatched": [], "dangling": []},
        "effort": {"started": "", "finished": "", "crops_opened": 0, "patches": 0, "notes": ""},
        "unresolved": [],
    }


def ensure_review(report: dict) -> dict:
    if "review" not in report:
        report["review"] = new_review(report)
    return report["review"]


class Chapter:
    """One work dir: paths, meta, report, blocks and patches; saved only after validation."""

    def __init__(self, book: str, chapter: int | str):
        self.book = book
        self.number = chapter_number(chapter)
        self.cfg = book_cfg(book)
        self.wd = work_dir(book, self.number)
        self.hybrid_auto = hybrid_auto_dir(self.wd)
        self.content_list = v2_path(self.hybrid_auto, STEM)
        self.report_path = self.wd / "qa_report.json"
        for path in (
            self.report_path,
            self.content_list,
            self.wd / "meta.json",
            self.wd / "chapter.pdf",
        ):
            if not path.exists():
                raise ReviewError(f"{path} missing — run make chapter BOOK={book} CH={self.number}")
        self.meta = json.loads((self.wd / "meta.json").read_text())
        self.report = json.loads(self.report_path.read_text())
        self.blocks: list[Block] = load_blocks(self.content_list)
        self.by_id = {b.id: b for b in self.blocks}
        self.patches = patchmod.load(self.wd, self.content_list)

    @property
    def review(self) -> dict:
        return ensure_review(self.report)

    def patched_blocks(self) -> list[Block]:
        return patchmod.apply(self.blocks, self.patches)

    def save(self) -> None:
        validate(self.report)
        validate_review(self.report)
        self.patched_blocks()  # PatchError if any patch cannot apply in order
        patchmod.save(self.wd, self.patches, self.content_list)
        self.report_path.write_text(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n")

    def hunk(self, index: int) -> dict:
        hunks = self.review["hunks"]
        if not 0 <= index < len(hunks):
            raise ReviewError(f"hunk {index} out of range 0..{len(hunks) - 1}")
        return hunks[index]

    def block_entry(self, block_id: str) -> dict:
        for b in self.review["blocks"]:
            if b["id"] == block_id:
                return b
        raise ReviewError(f"{block_id} is not a flagged block")

    def spot_entry(self, block_id: str) -> dict:
        for s in self.review["spot_check"]:
            if s["id"] == block_id:
                return s
        raise ReviewError(f"{block_id} is not a spot-check block")

    def crop_path(self, block_id: str) -> Path:
        for f in (*self.report["flagged_blocks"], *self.report["spot_check"]):
            if f["id"] == block_id:
                crop = f["crop"]
                return (self.hybrid_auto / crop) if crop.startswith("images/") else (self.wd / crop)
        raise ReviewError(f"{block_id} has no crop in qa_report.json (not flagged, not sampled)")

    def known_patches(self, ids: list[str] | None) -> list[str]:
        have = {p.id for p in self.patches}
        for i in ids or []:
            if i not in have:
                raise ReviewError(f"patch {i} does not exist in patches.json")
        return list(ids or [])


# --- CLI ------------------------------------------------------------------------------------


def cmd_start(ch: Chapter, args) -> None:
    if not ch.review["effort"]["started"]:
        ch.review["effort"]["started"] = now()
    ch.save()
    print(f"review: {ch.book} ch{ch.number:02d} started {ch.review['effort']['started']}")


def cmd_crop(ch: Chapter, args) -> None:
    path = ch.crop_path(args.id)
    if not path.exists():
        raise ReviewError(f"{path} missing")
    ch.review["effort"]["crops_opened"] += 1
    ch.save()
    print(path)


def cmd_hunk(ch: Chapter, args) -> None:
    h = ch.hunk(args.index)
    h["verdict"] = args.verdict
    if args.rule is not None:
        h["rule"] = args.rule
    if args.patch is not None:
        h["patches"] = ch.known_patches(args.patch)
    if args.note is not None:
        h["note"] = args.note
    ch.save()
    print(f"hunk {args.index}: {h['verdict']} ({h['rule']})")


def cmd_block(ch: Chapter, args) -> None:
    b = ch.block_entry(args.id)
    if args.verdict is not None:
        b["verdict"] = args.verdict
    if args.visual is not None:
        b["checks"]["visual"] = json.loads(args.visual)
    if args.patch is not None:
        b["patches"] = ch.known_patches(args.patch)
    if args.note is not None:
        b["note"] = args.note
    ch.save()
    print(f"block {args.id}: {b['verdict']}")


def cmd_spot(ch: Chapter, args) -> None:
    s = ch.spot_entry(args.id)
    s["verdict"] = args.verdict
    if args.note is not None:
        s["note"] = args.note
    ch.save()
    print(f"spot {args.id}: {s['verdict']}")


def cmd_heading(ch: Chapter, args) -> None:
    for m in ch.review["headings"]["missing"]:
        if m["title"] == args.title:
            m["verdict"], m["block"] = args.verdict, args.block
            if args.note is not None:
                m["note"] = args.note
            ch.save()
            print(f"heading {args.title!r}: {args.verdict}")
            return
    raise ReviewError(f"{args.title!r} is not in review.headings.missing")


def cmd_footnote(ch: Chapter, args) -> None:
    for u in ch.review["footnotes"]["unmatched"]:
        if u["id"] == args.id:
            u["verdict"] = args.verdict
            if args.note is not None:
                u["note"] = args.note
            ch.save()
            print(f"footnote {args.id}: {args.verdict}")
            return
    raise ReviewError(f"footnote {args.id} is not in review.footnotes.unmatched")


def cmd_patch(ch: Chapter, args) -> None:
    patch = patchmod.Patch(
        patchmod.next_id(ch.patches, "review"),
        args.block,
        args.op,
        args.old or "",
        args.new or "",
        "review",
        args.rule or "review",
        args.hunk,
        args.note or "",
    )
    ch.patches.append(patch)
    ch.review["effort"]["patches"] = sum(p.source == "review" for p in ch.patches)
    try:
        ch.save()
    except patchmod.PatchError:
        ch.patches.pop()
        raise
    print(patch.id)


def unresolved_items(report: dict) -> list[dict]:
    r = report["review"]
    out: list[dict] = []
    for i, h in enumerate(r["hunks"]):
        if h["verdict"] == "unresolved":
            out.append({"kind": "hunk", "ref": i, "reason": h["note"] or "no verdict"})
    for b in r["blocks"]:
        if b["verdict"] == "unresolved":
            out.append({"kind": "block", "ref": b["id"], "reason": b["note"] or "no verdict"})
    for s in r["spot_check"]:
        if s["verdict"] == "unresolved":
            out.append({"kind": "spot", "ref": s["id"], "reason": s["note"] or "no verdict"})
    for m in r["headings"]["missing"]:
        if m["verdict"] is None:
            out.append({"kind": "heading", "ref": m["title"], "reason": "subheading not found"})
    for u in r["footnotes"]["unmatched"]:
        if u["verdict"] is None:
            out.append(
                {"kind": "footnote", "ref": u["id"], "reason": "definition without a reference"}
            )
    return out


def finalize(ch: Chapter) -> str:
    """Derive status, render, check; certified only when all three pass (design §8, §12)."""
    from src.vault_checks import check_tree
    from src.vault_commit import render_chapter

    r = ch.review
    if not r["prepass"]["timestamp"]:
        raise ReviewError("prepass has not run — make prepass first")
    if not r["effort"]["started"]:
        raise ReviewError("review start was not recorded — run `review start` first")
    r["unresolved"] = unresolved_items(ch.report)
    status = "certified" if not r["unresolved"] else "needs_attention"
    ch.report["status"] = status
    r["effort"]["finished"] = now()
    r["effort"]["patches"] = sum(p.source == "review" for p in ch.patches)
    ch.save()
    tree = render_chapter(ch, certified=(status == "certified"))
    problems = check_tree(tree, ch)
    if problems:
        r["unresolved"] += [{"kind": "check", "ref": p.where, "reason": p.msg} for p in problems]
        status = "needs_attention"
        ch.report["status"] = status
        ch.save()
        render_chapter(ch, certified=False)
    return status


def cmd_finalize(ch: Chapter, args) -> int:
    status = finalize(ch)
    r = ch.review
    print(f"finalize: {ch.book} ch{ch.number:02d} -> {status}")
    for u in r["unresolved"]:
        print(f"  unresolved {u['kind']} {u['ref']}: {u['reason']}")
    return 0 if status == "certified" else 3


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="src.review", description="Stage 5 review record writer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--book", required=True)
        p.add_argument("--chapter", required=True)
        p.add_argument("--note")

    p = sub.add_parser("start", help="stamp effort.started")
    common(p)
    p.set_defaults(func=cmd_start)
    p = sub.add_parser("crop", help="print a crop path and count it as opened")
    common(p)
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_crop)
    p = sub.add_parser("hunk")
    common(p)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--verdict", choices=HUNK_VERDICTS, required=True)
    p.add_argument("--rule")
    p.add_argument("--patch", nargs="*")
    p.set_defaults(func=cmd_hunk)
    p = sub.add_parser("block")
    common(p)
    p.add_argument("--id", required=True)
    p.add_argument("--verdict", choices=BLOCK_VERDICTS)
    p.add_argument("--visual", help="tier-A answer as JSON")
    p.add_argument("--patch", nargs="*")
    p.set_defaults(func=cmd_block)
    p = sub.add_parser("spot")
    common(p)
    p.add_argument("--id", required=True)
    p.add_argument("--verdict", choices=SPOT_VERDICTS, required=True)
    p.set_defaults(func=cmd_spot)
    p = sub.add_parser("heading")
    common(p)
    p.add_argument("--title", required=True)
    p.add_argument("--verdict", choices=HEADING_VERDICTS, required=True)
    p.add_argument("--block")
    p.set_defaults(func=cmd_heading)
    p = sub.add_parser("footnote")
    common(p)
    p.add_argument("--id", required=True)
    p.add_argument("--verdict", choices=FOOTNOTE_VERDICTS, required=True)
    p.set_defaults(func=cmd_footnote)
    p = sub.add_parser("patch", help="add a reviewer patch; prints its id")
    common(p)
    p.add_argument("--block", required=True)
    p.add_argument("--op", choices=patchmod.OPS, required=True)
    p.add_argument("--old", default="")
    p.add_argument("--new", default="")
    p.add_argument("--rule")
    p.add_argument("--hunk", type=int)
    p.set_defaults(func=cmd_patch)
    p = sub.add_parser("finalize", help="derive status, render, check")
    common(p)
    p.set_defaults(func=cmd_finalize)
    return ap


def main(argv: list[str] | None = None) -> int:
    from src.render import RenderError  # local: vault_commit imports this module
    from src.sections import SectionError
    from src.vault_commit import CommitError

    args = build_parser().parse_args(argv)
    try:
        ch = Chapter(args.book, args.chapter)
        result = args.func(ch, args)
    except (
        ReviewError,
        SchemaError,
        SectionError,
        RenderError,
        CommitError,
        ConfigError,
        patchmod.PatchError,
        json.JSONDecodeError,
    ) as e:
        print(f"review: {e}", file=sys.stderr)
        return 1
    return result or 0


if __name__ == "__main__":
    sys.exit(main())
