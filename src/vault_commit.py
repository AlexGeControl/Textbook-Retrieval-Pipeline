"""Stage 5b — the staging tree vault/<book>/<chNN>/ and its manifest (design §10, §11).

`render` writes the hub, one note per section, assets/ and manifest.json; `check` runs the
battery; `push` (Task 10) copies the tree into the vault. Only certified trees are pushed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import sys
from pathlib import Path

import requests

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


class VaultClient:
    """Obsidian Local REST API (verified 2026-09-07: PUT creates parents, binary PUT is exact)."""

    def __init__(self):
        host, key = os.environ.get("OBSIDIAN_HOST"), os.environ.get("OBSIDIAN_API_KEY")
        missing = [n for n, v in (("OBSIDIAN_HOST", host), ("OBSIDIAN_API_KEY", key)) if not v]
        if missing:
            raise CommitError(f"missing {', '.join(missing)} in the environment")
        port = os.environ.get("OBSIDIAN_PORT", "27123")
        proto = os.environ.get("OBSIDIAN_PROTOCOL", "http")
        self.base = f"{proto}://{host}:{port}"
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {key}"

    def _call(self, method: str, path: str, **kw) -> requests.Response:
        try:
            return self.session.request(method, f"{self.base}/{path}", timeout=15, **kw)
        except requests.RequestException as e:
            raise CommitError(f"{self.base} unreachable: {type(e).__name__}") from e

    def ping(self) -> dict:
        info = self._call("GET", "").json()
        if not info.get("authenticated"):
            raise CommitError(f"{self.base}: authenticated false — this key is for another vault")
        return info

    def put(self, path: str, data: bytes, content_type: str) -> int:
        r = self._call("PUT", f"vault/{path}", data=data, headers={"Content-Type": content_type})
        if r.status_code not in (200, 204):
            raise CommitError(f"PUT {path}: HTTP {r.status_code} {r.text[:120]}")
        return r.status_code

    def get(self, path: str, accept: str | None = None) -> requests.Response:
        headers = {"Accept": accept} if accept else {}
        return self._call("GET", f"vault/{path}", headers=headers)

    def delete(self, path: str, permanent: bool = True) -> int:
        return self._call(
            "DELETE", f"vault/{path}", params={"permanent": str(permanent).lower()}
        ).status_code


def push_chapter(ch: Chapter, root: str, section: str | None = None, client=None) -> int:
    """PUT the certified tree (or one section's files) and read each file back. Returns failures."""
    from src.vault_checks import check_tree

    tree = staging_dir(ch)
    manifest = load_manifest(tree)
    if manifest.get("status") != "certified":
        raise CommitError(
            f"{tree} is {manifest.get('status', 'unrendered')}, not certified — nothing pushed"
        )
    problems = check_tree(tree, ch, section)
    if problems:
        raise CommitError(
            f"{len(problems)} battery problem(s), first: {problems[0].where}: {problems[0].msg}"
        )
    files = manifest["files"]
    if section:
        n_pages = ch.meta["pdf_pages"][1] - ch.meta["pdf_pages"][0] + 1
        picked = {
            s.ordinal
            for s in select(resolve(ch.meta, pages_of(ch.patched_blocks(), n_pages)), section)
        }
        files = {k: v for k, v in files.items() if v["section"] in picked}
    client = client or VaultClient()
    client.ping()
    root = root.strip("/")
    prefix = f"{root}/" if root else ""
    dest = f"{prefix}{ch.book}/ch{ch.number:02d}/"
    results: dict[str, dict] = {}
    for rel in sorted(files):
        data = (tree / rel).read_bytes()
        ctype = (
            "text/markdown"
            if rel.endswith(".md")
            else (mimetypes.guess_type(rel)[0] or "application/octet-stream")
        )
        status = client.put(dest + rel, data, ctype)
        back = client.get(dest + rel)
        results[rel] = {
            "status": status,
            "verified": back.status_code == 200 and back.content == data,
        }
    previous = (manifest.get("push") or {}).get("files", {})
    manifest["push"] = {
        "root": prefix,
        "host": client.base,
        "pushed_at": now(),
        "files": {**previous, **results},
    }
    (tree / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return sum(not r["verified"] for r in results.values())


def cmd_push(ch: Chapter, args) -> int:
    failed = push_chapter(ch, args.root, args.section)
    m = load_manifest(staging_dir(ch))
    n = len(m["push"]["files"])
    print(
        f"push: {n} file(s) to {m['push']['host']} {m['push']['root']}{ch.book}/ch{ch.number:02d}/"
        f" — {failed} failed read-back"
    )
    return 1 if failed else 0


def cmd_render(ch: Chapter, args) -> int:
    tree = render_chapter(ch, certified=False, section=args.section)
    m = load_manifest(tree)
    print(f"render: {tree} ({len(m['files'])} files, status {m['status']}, certified: false)")
    for line in m.get("render_log", []):
        print(f"  log: {line}")
    return 0


def cmd_check(ch: Chapter, args) -> int:
    from src.vault_checks import check_parsed, check_tree

    tree = staging_dir(ch)
    if not (tree / "manifest.json").exists():
        raise CommitError(f"{tree} has no manifest — run render first")
    problems = check_tree(tree, ch, args.section)
    if args.parsed:
        try:
            client = VaultClient()
            client.ping()
        except CommitError as e:
            print(f"check --parsed: skipped, host unreachable ({e})")
        else:
            problems += check_parsed(tree, ch, client, args.root, args.section)
    for p in problems:
        print(f"check: {p.where}: {p.msg}")
    print(f"check: {tree} {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 0 if not problems else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="src.vault_commit", description="Stage 5b staging tree")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--book", required=True)
        p.add_argument("--chapter", required=True)
        p.add_argument("--section", help="ordinal, slug or note name")

    p = sub.add_parser("render", help="write vault/<book>/<chNN>/")
    common(p)
    p.set_defaults(func=cmd_render)
    p = sub.add_parser("check", help="run the battery")
    common(p)
    p.add_argument(
        "--parsed", action="store_true", help="also compare Obsidian's parse of the pushed notes"
    )
    p.add_argument("--root", default="raw/textbooks/", help="vault folder the chapter is under")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("push", help="PUT the certified tree into the vault and read it back")
    common(p)
    p.add_argument("--root", default="raw/textbooks/", help="vault folder to push under")
    p.set_defaults(func=cmd_push)
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
