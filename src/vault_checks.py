"""The mechanical gate-4 battery over a staging tree (design §10). Part of certification."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.review import Chapter
from src.review_checks import latex_ok, table_grid

NOTE_NAME = re.compile(r"^[a-z0-9]+-ch\d{2}-\d{2}-[a-z0-9-]+\.md$")
FIXED_KEYS = ("book", "chapter", "course", "source_pages", "certified")
ALL_KEYS = (*FIXED_KEYS, "title", "section", "book_title", "edition", "certified_at")
_EMBED = re.compile(r"!\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
_LINK = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
_FOOT_REF = re.compile(r"\[\^([^\]]+)\](?!:)")
_FOOT_DEF = re.compile(r"^\[\^([^\]]+)\]:", re.MULTILINE)
_DISPLAY = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_UNESCAPED = re.compile(r"(?<!\\)\$")  # `\$` is a literal dollar sign (currency)
_TABLE_HTML = re.compile(r"<table>.*?</table>", re.DOTALL)  # Obsidian renders HTML blocks as HTML
_CALLOUT_HEAD = re.compile(r"^> \[!\w+\](-|\+)?( .*)?$")
# Obsidian's own parse of a note over the Local REST API (plugin 4.1.3 offers no HTML rendering,
# measured 2026-09-07): note+json carries frontmatter, content and the *resolved* link/embed
# targets; document-map+json carries the heading tree. Rendering itself is the mobile pass.
NOTE_JSON = "application/vnd.olrapi.note+json"
DOCUMENT_MAP = "application/vnd.olrapi.document-map+json"
_HEADING = re.compile(r"(?m)^#{1,6} ")


@dataclass
class Problem:
    where: str
    msg: str


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end < 0:
        return None, text
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None, text
    return (data if isinstance(data, dict) else None), text[end + 4 :]


def check_note(text: str, name: str, tree: Path, certified: bool) -> list[Problem]:
    out: list[Problem] = []
    fm, body = _split_frontmatter(text)
    if fm is None or any(k not in fm for k in ALL_KEYS):
        out.append(Problem(name, f"frontmatter missing or lacks {ALL_KEYS}"))
    else:
        sp = fm["source_pages"]
        if not (
            isinstance(sp, list)
            and len(sp) == 2
            and all(isinstance(v, int) for v in sp)
            and sp[0] <= sp[1]
        ):
            out.append(Problem(name, "frontmatter source_pages must be two ascending ints"))
        if fm["certified"] is not certified:
            out.append(
                Problem(
                    name,
                    f"frontmatter certified {fm['certified']} but tree is certified={certified}",
                )
            )
        if not isinstance(fm["chapter"], int):
            out.append(Problem(name, "frontmatter chapter must be an int"))
    if len([ln for ln in body.splitlines() if ln.startswith("# ")]) != 1:
        out.append(Problem(name, "exactly one H1 expected"))
    if body.count("$$") % 2:
        out.append(Problem(name, "odd number of $$ delimiters"))
    if body.count("%%") % 2:
        out.append(Problem(name, "odd number of %% comment markers"))
    rest = _TABLE_HTML.sub(" ", _DISPLAY.sub(" ", body))
    for m in _DISPLAY.finditer(body):
        ok, why = latex_ok(m.group(1).strip())
        if not ok:
            out.append(Problem(name, f"display math does not parse: {why}"))
    for para in re.split(r"\n\s*\n", rest):
        dollars = [m.start() for m in _UNESCAPED.finditer(para)]
        if len(dollars) % 2:
            out.append(Problem(name, f"unbalanced inline $ in paragraph starting {para[:30]!r}"))
            continue
        for a, b in zip(dollars[0::2], dollars[1::2]):  # pairs in order, never across formulas
            content = para[a + 1 : b]
            if not content.strip() or content[0].isspace() or content[-1].isspace():
                out.append(Problem(name, "space inside an inline $ delimiter"))
                continue
            ok, why = latex_ok(content)
            if not ok:
                out.append(Problem(name, f"inline math does not parse: {why}"))
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            counts = {len(re.findall(r"(?<!\\)\|", ln)) for ln in block}
            if len(counts) != 1 or len(block) < 2 or not re.match(r"^\|( ---? ?\|)+$", block[1]):
                out.append(Problem(name, "pipe table rows differ in width or lack a separator row"))
            continue
        i += 1
    for m in re.finditer(r"<table>.*?</table>", body, re.DOTALL):
        rows, cols, rect_ok = table_grid(m.group(0))
        if not rect_ok:
            out.append(Problem(name, f"HTML table is not rectangular ({rows}x{cols})"))
    for m in _EMBED.finditer(body):
        if not (tree / "assets" / m.group(1)).exists():
            out.append(Problem(name, f"unresolved embed {m.group(1)}"))
    for m in _LINK.finditer(body):
        if not (tree / f"{m.group(1)}.md").exists():
            out.append(Problem(name, f"unresolved link {m.group(1)}"))
    refs, defs = set(_FOOT_REF.findall(body)), _FOOT_DEF.findall(body)
    if refs != set(defs) or len(defs) != len(set(defs)):
        out.append(Problem(name, f"footnote refs {sorted(refs)} vs defs {sorted(defs)}"))
    in_callout = False
    for ln in lines:
        if _CALLOUT_HEAD.match(ln):
            in_callout = True
            continue
        if in_callout:
            if not ln.strip():
                in_callout = False
            elif not ln.startswith(">"):
                out.append(Problem(name, f"callout line not quoted: {ln[:40]!r}"))
                in_callout = False
    return out


def check_tree(tree: Path, ch: Chapter, section: str | None = None) -> list[Problem]:
    out: list[Problem] = []
    manifest = json.loads((tree / "manifest.json").read_text())
    certified = manifest.get("status") == "certified"
    files = manifest["files"]
    for rel, info in files.items():
        p = tree / rel
        if not p.exists():
            out.append(Problem(rel, "listed in manifest but missing"))
        elif hashlib.sha256(p.read_bytes()).hexdigest() != info["sha256"]:
            out.append(Problem(rel, "sha256 differs from manifest"))
    on_disk = {p.name for p in tree.glob("*.md")} | {
        f"assets/{p.name}" for p in (tree / "assets").glob("*")
    }
    for rel in sorted(on_disk - set(files)):
        out.append(Problem(rel, "unlisted file in the staging tree"))
    if manifest.get("qa_report_sha256") != hashlib.sha256(ch.report_path.read_bytes()).hexdigest():
        out.append(
            Problem(
                "manifest.json",
                "qa_report_sha256 differs from the current qa_report.json (stale render)",
            )
        )
    notes = sorted(n for n in files if n.endswith(".md"))
    if section is None and len(notes) != len(ch.meta["sections"]) + 1:
        out.append(
            Problem(
                "manifest.json", f"{len(notes)} notes for {len(ch.meta['sections'])} sections + hub"
            )
        )
    referenced: set[str] = set()
    for n in notes:
        if not NOTE_NAME.match(n) or len(n) > 100:
            out.append(Problem(n, "note name does not match <book>-chNN-NN-<slug>.md"))
        if not (tree / n).exists():
            continue
        text = (tree / n).read_text()
        referenced |= set(_EMBED.findall(text))
        out += check_note(text, n, tree, certified)
    for rel in files:
        if rel.startswith("assets/") and rel[7:] not in referenced and section is None:
            out.append(Problem(rel, "asset referenced by no note"))
    return out


def note_json(client, path: str, retries: int = 3) -> dict:
    """Obsidian's note+json; waits briefly for the metadata cache to index a fresh file."""
    for attempt in range(retries + 1):
        r = client.get(path, accept=NOTE_JSON)
        if r.status_code != 200:
            raise LookupError(f"GET {path}: HTTP {r.status_code}")
        data = r.json()
        if data.get("links") or attempt == retries:
            return data
        time.sleep(1)
    return data


def source_targets(text: str) -> tuple[set[str], int]:
    """Link and embed targets (note names, asset file names) and the heading count of a note."""
    _fm, body = _split_frontmatter(text)
    targets = {m.group(1) for m in _LINK.finditer(body)} | {
        m.group(1) for m in _EMBED.finditer(body)
    }
    return targets, len(_HEADING.findall(body))


def check_parsed(
    tree: Path, ch: Chapter, client, root: str, section: str | None = None
) -> list[Problem]:
    """Compare Obsidian's parse of each pushed note with the source: frontmatter, content, every
    link and embed resolved, heading count."""
    manifest = json.loads((tree / "manifest.json").read_text())
    push = manifest.get("push") or {}
    if not push:
        return [Problem("manifest.json", "not pushed yet — check --parsed needs a pushed chapter")]
    out: list[Problem] = []
    dest = f"{push['root']}{ch.book}/ch{ch.number:02d}/"
    for rel in sorted(n for n in manifest["files"] if n.endswith(".md")):
        text = (tree / rel).read_text()
        fm, _body = _split_frontmatter(text)
        targets, n_headings = source_targets(text)
        try:
            data = note_json(client, dest + rel)
        except LookupError as e:
            out.append(Problem(rel, str(e)))
            continue
        if data.get("frontmatter") != (fm or {}):
            out.append(Problem(rel, "Obsidian parsed the frontmatter differently"))
        if data.get("content") != text:
            out.append(Problem(rel, "content in the vault differs from the staging tree"))
        resolved = {p.rsplit("/", 1)[-1] for p in data.get("links", [])}
        resolved |= {n[:-3] for n in resolved if n.endswith(".md")}
        missing = sorted(t for t in targets if t not in resolved)
        if missing:
            out.append(Problem(rel, f"unresolved in Obsidian: {missing}"))
        dm = client.get(dest + rel, accept=DOCUMENT_MAP)
        if dm.status_code != 200:
            out.append(Problem(rel, f"document map GET returned {dm.status_code}"))
        elif len(dm.json().get("headings", [])) != n_headings:
            out.append(
                Problem(
                    rel,
                    f"Obsidian sees {len(dm.json()['headings'])} headings, source has {n_headings}",
                )
            )
    return out
