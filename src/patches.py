"""Patch model for stage 5 (design §6, §11): surgical edits applied at render time.

Patches live in work/<book>/<chNN>/patches.json beside the stage-2 outputs, which are never
edited. `apply` returns new Block objects; a patch whose `old` is absent or ambiguous fails.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from src.blocks import CAPTIONED, TEXT_BEARING, Block, Span

OPS = ("replace", "drop_block", "set_math", "set_html", "set_content")
REVIEW_ONLY = frozenset({"set_math", "set_html", "set_content"})
SOURCES = ("prepass", "review")
PREFIX = {"prepass": "pp", "review": "rv"}


class PatchError(Exception):
    pass


@dataclass(frozen=True)
class Patch:
    id: str
    block: str
    op: str
    old: str
    new: str
    source: str
    rule: str
    hunk: int | None = None
    note: str = ""


def patches_path(work_dir: Path) -> Path:
    return Path(work_dir) / "patches.json"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(work_dir: Path, content_list: Path) -> list[Patch]:
    """Patches bound to the current content list; an absent file is an empty list."""
    p = patches_path(work_dir)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    sha = sha256_of(content_list)
    bound = data.get("content_list_sha256", "")
    if bound != sha:
        raise PatchError(
            f"{p}: bound to content list {bound[:12]}…, current is {sha[:12]}… — "
            "re-extracted; rerun prepass and review"
        )
    return [Patch(**rec) for rec in data["patches"]]


def save(work_dir: Path, patches: list[Patch], content_list: Path) -> None:
    ids = [p.id for p in patches]
    if len(ids) != len(set(ids)):
        raise PatchError(f"duplicate patch ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    data = {
        "content_list_sha256": sha256_of(content_list),
        "patches": [asdict(p) for p in patches],
    }
    patches_path(work_dir).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def next_id(patches: list[Patch], source: str) -> str:
    prefix = PREFIX[source]
    used = [int(p.id[3:]) for p in patches if p.id.startswith(prefix + "-")]
    return f"{prefix}-{(max(used) + 1) if used else 1:04d}"


def target_text(block: Block, op: str) -> str:
    """The text a `replace` searches: body text spans, LaTeX, HTML or caption spans."""
    if block.type in TEXT_BEARING:
        return "".join(s.content for s in block.spans if s.type == "text")
    if block.type == "equation_interline":
        return block.math
    if block.type == "table":
        return block.html
    if block.type in CAPTIONED:
        return "".join(s.content for s in block.captions if s.type == "text")
    raise PatchError(f"{block.id}: no text a {op} can target on a {block.type}")


def _span_field(block: Block) -> str | None:
    if block.type in TEXT_BEARING:
        return "spans"
    if block.type in CAPTIONED and block.type != "table":
        return "captions"
    return None


def validate(patch: Patch, blocks: dict[str, Block]) -> None:
    if patch.op not in OPS:
        raise PatchError(f"{patch.id}: unknown op {patch.op!r}")
    if patch.source not in SOURCES:
        raise PatchError(f"{patch.id}: unknown source {patch.source!r}")
    if not patch.id.startswith(PREFIX[patch.source] + "-"):
        raise PatchError(f"{patch.id}: id prefix does not match source {patch.source!r}")
    if patch.op in REVIEW_ONLY and patch.source != "review":
        raise PatchError(f"{patch.id}: {patch.op} is reviewer-only")
    block = blocks.get(patch.block)
    if block is None:
        raise PatchError(f"{patch.id}: block {patch.block} does not exist (or was dropped)")
    if patch.op == "set_math" and block.type != "equation_interline":
        raise PatchError(f"{patch.id}: set_math on a {block.type}")
    if patch.op == "set_html" and block.type != "table":
        raise PatchError(f"{patch.id}: set_html on a {block.type}")
    if patch.op == "set_content" and block.type not in ("chart", "image"):
        raise PatchError(f"{patch.id}: set_content on a {block.type}")
    if patch.op != "replace":
        return
    if not patch.old:
        raise PatchError(f"{patch.id}: replace needs a non-empty old")
    n = target_text(block, patch.op).count(patch.old)
    if n != 1:
        raise PatchError(f"{patch.id}: old occurs {n} times in {block.id}, need exactly 1")
    field = _span_field(block)
    if field is not None:
        spans = getattr(block, field)
        if not any(s.type == "text" and patch.old in s.content for s in spans):
            raise PatchError(f"{patch.id}: old crosses a span boundary in {block.id}")


def _replace_text(b: Block, old: str, new: str) -> Block:
    if b.type == "equation_interline":
        return replace(b, math=b.math.replace(old, new, 1))
    if b.type == "table":
        return replace(b, html=b.html.replace(old, new, 1))
    field = _span_field(b)
    spans = list(getattr(b, field))
    for i, s in enumerate(spans):
        if s.type == "text" and old in s.content:
            spans[i] = Span("text", s.content.replace(old, new, 1))
            return replace(b, **{field: tuple(spans)})
    raise PatchError(f"{b.id}: old not found in any span")


def apply(blocks: list[Block], patches: list[Patch]) -> list[Block]:
    """Apply patches in order, validating each against the already-patched state."""
    by_id = {b.id: b for b in blocks}
    for p in patches:
        validate(p, by_id)
        b = by_id[p.block]
        if p.op == "drop_block":
            del by_id[p.block]
        elif p.op == "set_math":
            by_id[p.block] = replace(b, math=p.new)
        elif p.op == "set_html":
            by_id[p.block] = replace(b, html=p.new)
        elif p.op == "set_content":
            by_id[p.block] = replace(b, content=p.new)
        else:
            by_id[p.block] = _replace_text(b, p.old, p.new)
    return [by_id[b.id] for b in blocks if b.id in by_id]
