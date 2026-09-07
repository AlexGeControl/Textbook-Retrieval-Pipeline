"""Block-to-Markdown rules and note assembly (design §9). Patches are applied before this.

Faithful and readable for a human reader; no reflow, no reordering, no sentence-level edits,
no text from chapter.md. Cosmetic refinements wait until a human has read a section.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from lxml import html as lxml_html

from src.blocks import RUNNING_MATTER, Block, Span
from src.fold import clean_title, fold
from src.sections import Chain, Section, printed_page

SLUG_MAX = 60
DECORATIVE_AREA = 0.015  # fraction of the page below which an uncaptioned image is dropped
_BULLET = re.compile(r"^\s*(?:[●•▪■◦∙]\s*|[-*] )")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s")
_SUP = re.compile(r"<sup>\s*(\d+)\s*</sup>")
_ORDERED_START = re.compile(r"^(\d+)([.)])(\s)")
_MARKER_START = re.compile(r"^(?:[#>]|[-*+]\s)")
_CELL_MATH = re.compile(r"\$(?=\S)((?:\\\$|[^$\n])+?)(?<=\S)\$")  # `\$` inside stays inside


class RenderError(Exception):
    pass


@dataclass
class Context:
    book: str
    chapter: int
    meta: dict
    cfg: dict
    certified: bool
    certified_at: str | None
    verdicts: dict[str, str] = field(default_factory=dict)  # flagged block id -> verdict
    suspects: set[str] = field(default_factory=set)  # running_matter_suspect ids
    dropped: set[str] = field(default_factory=set)  # suspects the reviewer dropped
    footnote_ids: set[str] = field(default_factory=set)
    subheadings: set[str] = field(default_factory=set)  # folded toc_subtree subheading titles
    log: list[str] = field(default_factory=list)
    assets: dict[str, tuple[str, int]] = field(default_factory=dict)  # name -> (crop, ordinal)
    current: int = 0  # ordinal of the section being rendered


def slug(title: str) -> str:
    s = unicodedata.normalize("NFKC", clean_title(title)).casefold()
    s = re.sub(r"[’'`]", "", s)  # Vegetron’s -> vegetrons, not vegetron-s
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > SLUG_MAX:
        cut = s[:SLUG_MAX]
        s = cut.rsplit("-", 1)[0] if "-" in cut else cut
    return s or "untitled"


def note_name(ctx: Context, section: Section) -> str:
    return f"{ctx.book}-ch{ctx.chapter:02d}-{section.ordinal:02d}-{slug(section.title)}"


def asset_name(ctx: Context, block: Block) -> str:
    return f"{ctx.book}-ch{ctx.chapter:02d}-{block.id}{Path(block.crop).suffix or '.jpg'}"


def heading_text(section: Section) -> str:
    return f"{section.number} {section.title}" if section.number else section.title


def escape_start(text: str) -> str:
    m = _ORDERED_START.match(text)
    if m:
        return f"{m.group(1)}\\{m.group(2)}{m.group(3)}{text[m.end() :]}"
    return "\\" + text if _MARKER_START.match(text) else text


def footnote_refs(text: str, ctx: Context) -> str:
    def sub(m: re.Match) -> str:
        prev = text[m.start() - 1] if m.start() else ""
        n = m.group(1)
        if n in ctx.footnote_ids and not (prev.isdigit() or (prev and prev in ")]")):
            return f"[^{n}]"
        return m.group(0)

    return _SUP.sub(sub, text)


def escape_dollars(text: str) -> str:
    """A `$` in a text span is currency (math lives in equation_inline spans): `\\$` for Obsidian."""
    return text.replace("$", "\\$")


def md_text(text: str, ctx: Context) -> str:
    """A text span or caption as Markdown: currency escaped, footnote markers converted."""
    return footnote_refs(escape_dollars(text), ctx)


def _cell_is_math(content: str) -> bool:
    """`$…$` in a VLM table cell reads as LaTeX when it opens with a letter, `\\`, `(` or `{`, or with
    a digit followed somewhere by `\\`, `^`, `_` or `=` (`$1,949^a$`); `$4,000-$6,000` does not."""
    c0 = content[0]
    if c0.isalpha() or c0 in "\\({":
        return True
    if not c0.isdigit() or not any(ch in content for ch in "\\^_="):
        return False
    # `$4,000 × 1.01 = -$4,040`: two currency signs paired by accident around an `=` that has
    # nothing but a sign after it (bkm ch22 p016-b003); a real formula continues past `=`.
    return not re.search(r"=\s*[-+−]?\s*$", content)


def escape_cell_dollars(text: str) -> str:
    """Pipe-table cells are Markdown: keep LaTeX `$…$` pairs, escape every other `$`."""
    out: list[str] = []
    pos = 0
    while True:
        m = _CELL_MATH.search(text, pos)
        if m is None:
            out.append(escape_dollars(text[pos:]))
            return "".join(out)
        out.append(escape_dollars(text[pos : m.start()]))
        if _cell_is_math(m.group(1)):
            out.append(m.group(0))
            pos = m.end()
        else:  # a currency `$` paired by accident: escape it and rescan from the next `$`
            out.append("\\$")
            pos = m.start() + 1


def inline(spans: tuple[Span, ...], ctx: Context) -> str:
    out: list[str] = []
    after_math = False
    for s in spans:
        if s.type == "equation_inline":
            if after_math:
                out.append(" ")  # back-to-back formulas would otherwise read as `$$`
            out.append(f"${s.content.strip()}$")
            after_math = True
        elif s.type == "text":
            if after_math and s.content[:1].isalnum():
                out.append(" ")  # mineru drops the space after an inline formula
            out.append(md_text(s.content, ctx))
            after_math = False
    return "".join(out)


def strip_ornament(text: str) -> str:
    i = 0
    while i < len(text) and (unicodedata.category(text[i]) == "So" or text[i].isspace()):
        i += 1
    return text[i:]


def paragraph(block: Block, ctx: Context) -> str:
    text = inline(block.spans, ctx).strip()
    return escape_start(text) if text else ""


def list_block(block: Block, ctx: Context) -> str:
    items: list[list[Span]] = [[]]
    for s in block.spans:
        if s.type == "text" and s.content == "\n":
            items.append([])
        else:
            items[-1].append(s)
    lines: list[str] = []
    for item in items:
        text = inline(tuple(item), ctx).strip()
        if not text:
            continue
        text = _BULLET.sub("", text, count=1)
        lines.append(text if _NUMBERED.match(text) else f"- {text}")
    return "\n".join(lines)


def title(block: Block, ctx: Context, in_hub: bool) -> str:
    text = clean_title(inline(block.spans, ctx))
    if not text:
        return ""
    if in_hub:
        return f"**{text}**"
    return f"## {text}" if fold(text) in ctx.subheadings else f"### {text}"


def equation(block: Block) -> str:
    return f"$$\n{block.math.strip()}\n$$"


def has_spans(html_text: str) -> bool:
    tree = lxml_html.fromstring(html_text)
    return any(td.get("colspan") or td.get("rowspan") for td in tree.xpath(".//td|.//th"))


def _cells(tr) -> list[str]:
    out = []
    for td in tr.xpath("./td|./th"):
        for br in td.xpath(".//br"):
            br.tail = " " + (br.tail or "")
        out.append(escape_cell_dollars(" ".join(td.text_content().split()).replace("|", "\\|")))
    return out


def pipe_table(html_text: str) -> str:
    tree = lxml_html.fromstring(html_text)
    rows = [_cells(tr) for tr in tree.xpath(".//tr")]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _caption_parts(block: Block) -> tuple[str, str]:
    cap: list[Span] = []
    foot: list[Span] = []
    target = cap
    for s in block.captions:
        if s.type == "text" and s.content == "\n":
            target = foot
            continue
        target.append(s)
    return "".join(s.content for s in cap).strip(), "".join(s.content for s in foot).strip()


def embed(block: Block, ctx: Context) -> str:
    name = asset_name(ctx, block)
    prev = ctx.assets.get(name)
    ctx.assets[name] = (block.crop, min(ctx.current, prev[1]) if prev else ctx.current)
    return f"![[{name}]]"


def table(block: Block, ctx: Context) -> str:
    cap, foot = _caption_parts(block)
    parts = [strip_ornament(md_text(cap, ctx))] if cap else []
    if not block.html.strip():
        ctx.log.append(f"{block.id}: empty table body, crop embedded")
        parts += [embed(block, ctx), "> [!warning] Table body missing from the extraction"]
    elif block.sub_type == "simple_table" and not has_spans(block.html):
        parts.append(pipe_table(block.html))
    else:
        if block.sub_type == "simple_table":
            ctx.log.append(f"{block.id}: simple_table with colspan/rowspan rendered as HTML")
        parts.append(block.html.strip())
    if foot:
        parts.append(md_text(foot, ctx))
    return "\n\n".join(p for p in parts if p)


def figure(block: Block, ctx: Context) -> str:
    cap, foot = _caption_parts(block)
    parts = [embed(block, ctx)]
    if cap:
        parts.append(strip_ornament(md_text(cap, ctx)))
    if foot:
        parts.append(md_text(foot, ctx))
    content = block.content.strip()
    if content and ctx.verdicts.get(block.id) in ("verified", "patched"):
        label = (
            "Flowchart (VLM transcription)"
            if block.type == "image"
            else "Chart data (VLM transcription)"
        )
        body = "\n".join("> " + line for line in content.splitlines())
        parts.append(f"> [!note]- {label}\n{body}")
    return "\n\n".join(parts)


def image(block: Block, ctx: Context) -> str:
    cap, _foot = _caption_parts(block)
    if block.content.strip() or cap:
        return figure(block, ctx)
    x0, y0, x1, y1 = block.bbox
    if (x1 - x0) * (y1 - y0) / 1_000_000 < DECORATIVE_AREA:
        return ""
    ctx.log.append(f"{block.id}: large uncaptioned image embedded")
    return embed(block, ctx)


def aside_callout(run: list[Block], ctx: Context) -> str:
    lines = [t for b in run for t in (ln.strip() for ln in inline(b.spans, ctx).splitlines()) if t]
    if not lines:
        return ""
    return "\n".join([f"> [!info] {lines[0]}", *(f"> {t}" for t in lines[1:])])


def render_block(block: Block, ctx: Context, in_hub: bool = False) -> str:
    if block.id in ctx.dropped:
        return ""
    if block.type == "paragraph":
        return paragraph(block, ctx)
    if block.type == "list":
        return list_block(block, ctx)
    if block.type == "title":
        return title(block, ctx, in_hub)
    if block.type in RUNNING_MATTER:
        return paragraph(block, ctx) if block.id in ctx.suspects else ""
    if block.type == "page_footnote":
        return ""  # footnote chains are rendered by footnote_defs
    if block.type == "page_aside_text":
        return aside_callout([block], ctx)
    if block.type == "equation_interline":
        return equation(block)
    if block.type == "table":
        return table(block, ctx)
    if block.type == "chart":
        return figure(block, ctx)
    if block.type == "image":
        return image(block, ctx)
    raise RenderError(f"{block.id}: no rendering rule for {block.type}")


def render_body(blocks: list[Block], ctx: Context, in_hub: bool = False) -> list[str]:
    out: list[str] = []
    page = None
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b.page_idx != page:
            page = b.page_idx
            out.append(f"%% p. {printed_page(ctx.meta, page)} %%")
        if b.type == "page_aside_text":
            run = [b]
            while (
                i + 1 < len(blocks)
                and blocks[i + 1].type == "page_aside_text"
                and blocks[i + 1].page_idx == b.page_idx
                and blocks[i + 1].index == run[-1].index + 1
            ):
                i += 1
                run.append(blocks[i])
            out.append(aside_callout(run, ctx))
        else:
            out.append(render_block(b, ctx, in_hub))
        i += 1
    return [p for p in out if p]


def footnote_defs(chains: list[Chain], ctx: Context) -> str:
    marked: list[str] = []
    plain: list[str] = []
    for c in chains:
        texts = [inline(b.spans, ctx) for b in c.blocks]
        if c.marker:
            # the definition's own leading marker: `<sup>n</sup>` if it did not convert, else `[^n]`
            first = re.sub(
                rf"^\s*(\[\^{re.escape(c.marker)}\]|<sup>\s*{re.escape(c.marker)}\s*</sup>)",
                "",
                texts[0].strip(),
                count=1,
            ).strip()
            lines = [f"[^{c.marker}]: {first}"] + [
                f"    {t.strip()}" for t in texts[1:] if t.strip()
            ]
            marked.append("\n".join(lines))
        else:
            plain.append(" ".join(t.strip() for t in texts if t.strip()))
    out: list[str] = []
    if plain:
        out.append("---\n\n" + "\n\n".join(plain))
    if marked:
        out.append("\n\n".join(marked))
    return "\n\n".join(out)


def frontmatter(section: Section, ctx: Context) -> str:
    data = {
        "book": ctx.book,
        "chapter": ctx.chapter,
        "course": ctx.cfg.get("course"),
        "source_pages": list(section.printed_pages),
        "certified": ctx.certified,
        "title": section.title,
        "section": section.number,
        "book_title": ctx.cfg.get("title"),
        "edition": ctx.cfg.get("edition"),
        "certified_at": ctx.certified_at,
    }
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=None)
    return "---\n" + body.strip() + "\n---"


def navigation(section: Section, sections: list[Section], ctx: Context) -> str:
    hub = sections[0]
    parts: list[str] = []
    if section.ordinal > 1:
        prev = sections[section.ordinal - 1]
        parts.append(f"[[{note_name(ctx, prev)}|← {heading_text(prev)}]]")
    parts.append(f"[[{note_name(ctx, hub)}|↑ {hub.title}]]")
    if section.ordinal < len(sections) - 1:
        nxt = sections[section.ordinal + 1]
        parts.append(f"[[{note_name(ctx, nxt)}|{heading_text(nxt)} →]]")
    return " · ".join(parts)


def render_section(section: Section, sections: list[Section], ctx: Context) -> str:
    ctx.current = section.ordinal
    parts = [
        frontmatter(section, ctx),
        f"# {heading_text(section)}",
        *render_body(section.blocks, ctx),
    ]
    fn = footnote_defs(section.footnotes, ctx)
    if fn:
        parts.append(fn)
    parts.append(navigation(section, sections, ctx))
    return "\n\n".join(parts) + "\n"


def render_hub(sections: list[Section], ctx: Context) -> str:
    ctx.current = 0
    hub = sections[0]
    lo, hi = ctx.meta["printed_pages"]
    parts = [
        frontmatter(hub, ctx),
        f"# {hub.title}",
        f"*{ctx.cfg.get('title')}*, {ctx.cfg.get('edition')} — chapter {ctx.chapter}, pp. {lo}–{hi}",
        *render_body(hub.blocks, ctx, in_hub=True),
        "## Sections",
        "\n".join(f"- [[{note_name(ctx, s)}|{heading_text(s)}]]" for s in sections[1:]),
    ]
    fn = footnote_defs(hub.footnotes, ctx)
    if fn:
        parts.append(fn)
    return "\n\n".join(p for p in parts if p) + "\n"
