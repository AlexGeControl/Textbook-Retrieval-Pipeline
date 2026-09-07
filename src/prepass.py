"""Stage 5a — deterministic pre-pass over qa_report.diff_hunks (design §6, amended).

Classifies every hunk, writes one verdict per hunk into qa_report.review.hunks and surgical
`pp-` patches into patches.json. Never edits content_list_v2.json, never touches a VLM body,
never pastes the normalized hunk text: accepted PDF text is rebuilt from raw PyMuPDF spans.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass

import pymupdf

from src import patches as patchmod
from src.blocks import TEXT_BEARING, Block
from src.config import ConfigError
from src.fold import fold, letters
from src.normalize import MD_RULES, PDF_RULES, normalize, tokenize
from src.review import Chapter, ReviewError, now
from src.textlayer import Word, find_run, page_words, render_words, stream_text, words_in_bbox

FOLIO_WORD = re.compile(r"^page$", re.IGNORECASE)
CONTEXT_WIDEN = 3  # extra context tokens tried on each side when a window is not unique


@dataclass
class Verdict:
    verdict: str
    rule: str
    block_id: str = ""
    spec: tuple[str, str, str] | None = None  # (op, old, new)
    note: str = ""
    also: tuple[str, ...] = ()  # further blocks dropped under the same rule (merged junk)


def strip_context(pdf: list[str], md: list[str]) -> tuple[list[str], list[str]]:
    """Drop the common token prefix and suffix (the guardrail's context) to leave the core."""
    i = 0
    while i < len(pdf) and i < len(md) and pdf[i] == md[i]:
        i += 1
    pdf, md = pdf[i:], md[i:]
    j = 0
    while j < len(pdf) and j < len(md) and pdf[-1 - j] == md[-1 - j]:
        j += 1
    return (pdf[: len(pdf) - j], md[: len(md) - j]) if j else (pdf, md)


def edge_kind(pdf: list[str], md: list[str]) -> str | None:
    """'start'/'end' when the PDF fold is the md fold plus one glyph or a short digit run."""
    fp, fm = fold(" ".join(pdf)), fold(" ".join(md))
    if not fm or len(fp) <= len(fm):
        return None
    if fp.endswith(fm):
        extra, where = fp[: len(fp) - len(fm)], "start"
    elif fp.startswith(fm):
        extra, where = fp[len(fm) :], "end"
    else:
        return None
    if len(extra) == 1 or (where == "end" and extra.isdigit() and len(extra) <= 2):
        return where
    return None


def is_folio_core(md: list[str]) -> bool:
    """`Page N [Page N …]` and nothing else (ops injects the reflowed folio into body text)."""
    if not md or len(md) % 2:
        return False
    pairs = list(zip(md[0::2], md[1::2]))
    return all(FOLIO_WORD.match(a) and b.isdigit() for a, b in pairs)


def _md_tokens(block: Block) -> list[str]:
    return tokenize(normalize(patchmod.target_text(block, "replace"), MD_RULES))


def duplicate_unit(block: Block) -> tuple[str, str] | None:
    """(old, new) collapsing every run of adjacently repeated token segments to one copy.

    mineru duplicates line by line (bma ch06 p026-b007: seven line segments of 6–18 tokens, each
    emitted 15 times), so no whole-block period exists; at each position the repeat consuming
    the most tokens wins. A proposal only: classify() confirms it against the text layer.
    """
    if block.inline_math():
        return None
    raw = patchmod.target_text(block, "replace")
    spans = [m.span() for m in re.finditer(r"\S+", raw)]
    toks = tokenize(normalize(raw, MD_RULES))
    n = len(toks)
    if n < 2 or len(spans) != n:
        return None
    keep: list[int] = []
    i = 0
    while i < n:
        best_p, best_r = 0, 0
        for p in range(1, (n - i) // 2 + 1):
            if toks[i : i + p] == toks[i + p : i + 2 * p]:
                r = 2
                while toks[i + r * p : i + (r + 1) * p] == toks[i : i + p]:
                    r += 1
                if p * r > best_p * best_r:
                    best_p, best_r = p, r
        if best_r:
            keep.extend(range(i, i + best_p))
            i += best_p * best_r
        else:
            keep.append(i)
            i += 1
    if len(keep) == n:
        return None
    runs: list[str] = []
    start, last = 0, -2
    for k in keep:
        if k != last + 1:
            start = spans[k][0]
            runs.append("")
        runs[-1] = raw[start : spans[k][1]]
        last = k
    return raw, " ".join(runs)


def strip_moved(tokens: list[str], pool: Counter) -> tuple[list[str], bool]:
    """Remove leading/trailing token runs whose fold another hunk inserted or deleted."""
    side = list(tokens)
    moved = False
    changed = True
    while changed and side:
        changed = False
        for k in range(len(side), 0, -1):
            if fold(" ".join(side[:k])) in pool:
                side, changed, moved = side[k:], True, True
                break
        for k in range(len(side), 0, -1):
            if side and fold(" ".join(side[-k:])) in pool:
                side, changed, moved = side[:-k], True, True
                break
    return side, moved


class Prepass:
    def __init__(self, ch: Chapter):
        self.ch = ch
        self.doc = pymupdf.open(ch.wd / "chapter.pdf")
        self._words: dict[int, list[Word]] = {}
        self._dup: dict[str, tuple[str, str] | None] = {}
        self._pending_note = ""
        self.hunks = ch.report["diff_hunks"]
        self.tokens = [(h["pdf_text"].split(), h["md_text"].split()) for h in self.hunks]
        self.cores = [strip_context(p, m) for p, m in self.tokens]
        self.insertions = Counter(fold(" ".join(md)) for pdf, md in self.cores if md and not pdf)
        self.deletions = Counter(fold(" ".join(pdf)) for pdf, md in self.cores if pdf and not md)
        self.insertions.pop("", None)  # punctuation-only cores fold to nothing
        self.deletions.pop("", None)

    def words(self, page_idx: int) -> list[Word]:
        if page_idx not in self._words:
            self._words[page_idx] = page_words(self.doc[page_idx])
        return self._words[page_idx]

    def textlayer_words(self, block: Block) -> list[Word]:
        return words_in_bbox(self.words(block.page_idx), block.bbox, self.doc[block.page_idx].rect)

    def textlayer_confirms(self, block: Block, text: str) -> bool:
        """The text-layer words in the block's bbox normalize to exactly the tokens of `text`."""
        want = tokenize(normalize(text, MD_RULES))
        have = tokenize(normalize(stream_text(self.textlayer_words(block)), PDF_RULES))
        return bool(want) and want == have

    def duplicate(self, block: Block) -> tuple[str, str] | None:
        if block.id not in self._dup:
            self._dup[block.id] = duplicate_unit(block)
        return self._dup[block.id]

    def junk_siblings(self, block: Block, md: list[str]) -> list[str] | None:
        """Following blocks on the page without text-layer words that hold the rest of the core.

        The guardrail merges adjacent unmatched blocks into one hunk (bma ch05: two `#` margin
        icons, one hunk). None when the core is not fully accounted for.
        """
        rest = md[len(_md_tokens(block)) :]
        out: list[str] = []
        for c in self.ch.blocks:
            if not rest:
                break
            if c.page_idx != block.page_idx or c.index <= block.index:
                continue
            if c.type not in TEXT_BEARING:
                continue
            toks = _md_tokens(c)
            if toks and rest[: len(toks)] == toks and not self.textlayer_words(c):
                out.append(c.id)
                rest = rest[len(toks) :]
        return None if rest else out

    def md_window(self, block: Block, tokens: list[str]) -> str | None:
        """Smallest raw substring of the block whose normalized tokens equal `tokens`, if unique."""
        if not tokens:
            return None
        raw = patchmod.target_text(block, "replace")
        spans = [m.span() for m in re.finditer(r"\S+", raw)]
        hits: list[tuple[int, int]] = []
        for i in range(len(spans)):
            for j in range(i, min(len(spans), i + 3 * len(tokens) + 3)):
                got = tokenize(normalize(raw[spans[i][0] : spans[j][1]], MD_RULES))
                if len(got) >= len(tokens):
                    if got == tokens:
                        hits.append((spans[i][0], spans[j][1]))
                    break
        if len({e for _, e in hits}) != 1:
            return None
        return raw[max(s for s, _ in hits) : hits[0][1]]

    def widened(self, index: int, k: int) -> tuple[list[str], list[str]]:
        """The core plus k shared context tokens on each side (k = 0 is the core itself)."""
        pdf_all, md_all = self.tokens[index]
        _pdf_core, md_core = self.cores[index]
        lead = self._prefix_len(index)
        trail = len(md_all) - lead - len(md_core)
        a, b = max(0, lead - k), max(0, trail - k)
        return pdf_all[a : len(pdf_all) - b], md_all[a : len(md_all) - b]

    def pdf_wins(
        self,
        index: int,
        block: Block,
        pdf: list[str],
        md: list[str],
        rule: str,
        widen: bool = True,
    ) -> Verdict:
        """A `replace` from the raw PDF run, widened with shared context until the run is unique
        on the page and the window is unique in the block. Move remainders try the core only."""
        raw = patchmod.target_text(block, "replace")
        for k in range(CONTEXT_WIDEN + 1 if widen else 1):
            pdf_k, md_k = (pdf, md) if k == 0 else self.widened(index, k)
            if not pdf_k or not md_k:
                continue
            run = find_run(self.words(block.page_idx), pdf_k, PDF_RULES)
            window = self.md_window(block, md_k)
            if run is None or window is None or raw.count(window) != 1:
                continue
            new = render_words(run)
            if (
                rule.endswith("edge_glyph")
                and len(run) > 1
                and len(run[0].text) == 1
                and run[0].text.isalpha()
                and not window.startswith(run[0].text)
            ):
                new = run[0].text + render_words(run[1:])  # drop cap glued to its word
            if new == window:
                return Verdict("accepted_pdf", rule, block.id, note="raw texts agree")
            return Verdict("accepted_pdf", rule, block.id, ("replace", window, new))
        return Verdict(
            "unresolved", "needs_eyes", block.id, note=f"{rule}: raw run or md window not unique"
        )

    def _prefix_len(self, index: int) -> int:
        pdf_all, md_all = self.tokens[index]
        i = 0
        while i < len(pdf_all) and i < len(md_all) and pdf_all[i] == md_all[i]:
            i += 1
        return i

    def classify(self, index: int) -> Verdict:
        self._pending_note = ""
        v = self._classify(index)
        if v.verdict == "unresolved" and self._pending_note:
            v.note = f"{self._pending_note}; {v.note}" if v.note else self._pending_note
        return v

    def _classify(self, index: int) -> Verdict:
        h = self.hunks[index]
        pdf, md = self.cores[index]
        block = self.ch.by_id.get(h["anchor"])
        if block is None:
            return Verdict("unresolved", "needs_eyes", note="anchor block missing")
        if block.type not in TEXT_BEARING:
            return Verdict(
                "unresolved",
                "needs_eyes",
                block.id,
                note=f"anchored to a {block.type} (masking gap)",
            )
        if md and not pdf and not self.textlayer_words(block):
            also = self.junk_siblings(block, md)
            if also is None:
                return Verdict(
                    "unresolved",
                    "needs_eyes",
                    block.id,
                    note="junk core spans blocks with text-layer words",
                )
            return Verdict("dropped", "junk", block.id, ("drop_block", "", ""), also=tuple(also))
        if md and not pdf:
            dup = self.duplicate(block)
            if dup is not None:
                if self.textlayer_confirms(block, dup[1]):
                    return Verdict("patched", "duplicate", block.id, ("replace", *dup))
                self._pending_note = "duplicate collapse not confirmed by the text layer"
        if not pdf and is_folio_core(md):
            window = self.md_window(block, md)
            if window is not None:
                raw = patchmod.target_text(block, "replace")
                end = raw.find(window) + len(window)
                old = window + " " if end < len(raw) and raw[end] == " " else window
                return Verdict("patched", "folio", block.id, ("replace", old, ""))
        prefix = ""
        pdf2, m1 = strip_moved(pdf, self.insertions) if pdf else (pdf, False)
        md2, m2 = strip_moved(md, self.deletions) if md else (md, False)
        if m1 or m2:
            if not pdf2 and not md2:
                return Verdict("move", "move", block.id)
            pdf, md, prefix = pdf2, md2, "move+"
        if (not pdf) != (not md):  # one-sided: a drop cap or a lone glyph next to its word
            pdf1, md1 = self.widened(index, 1)
            if not prefix and pdf1 and md1 and edge_kind(pdf1, md1) is not None:
                return self.pdf_wins(index, block, pdf1, md1, "edge_glyph")
            return Verdict("unresolved", "needs_eyes", block.id, note=f"{prefix}one-sided core")
        if not pdf and not md:
            return Verdict("unresolved", "needs_eyes", block.id, note="empty core")
        if block.inline_math():
            if letters(" ".join(pdf)) == letters(" ".join(md)):
                return Verdict("verified", prefix + "inline_math", block.id)
            return Verdict(
                "unresolved", "needs_eyes", block.id, note=f"{prefix}inline math differs"
            )
        if fold(" ".join(pdf)) == fold(" ".join(md)):
            return self.pdf_wins(index, block, pdf, md, prefix + "same_letters", widen=not prefix)
        if edge_kind(pdf, md) is not None:
            return self.pdf_wins(index, block, pdf, md, prefix + "edge_glyph", widen=not prefix)
        return Verdict("unresolved", "needs_eyes", block.id, note=f"{prefix}letters differ")


def run(ch: Chapter) -> Counter:
    pp = Prepass(ch)
    review = ch.review
    ch.patches = [p for p in ch.patches if p.source != "prepass"]
    counts: Counter = Counter()
    made: dict[tuple, str] = {}
    for i in range(len(pp.hunks)):
        v = pp.classify(i)
        keys = [(v.block_id, *v.spec)] if v.spec is not None else []
        keys += [(bid, "drop_block", "", "") for bid in v.also]
        ids: list[str] = []
        added: list[tuple] = []
        for key in keys:
            if key not in made:
                patch = patchmod.Patch(
                    patchmod.next_id(ch.patches, "prepass"), *key, "prepass", v.rule, i
                )
                try:
                    patchmod.apply(ch.blocks, [*ch.patches, patch])
                except patchmod.PatchError as e:
                    for k in added:  # roll back this hunk's earlier patches
                        made.pop(k)
                        ch.patches.pop()
                    v = Verdict("unresolved", "needs_eyes", v.block_id, note=f"{v.rule}: {e}")
                    ids = []
                    break
                ch.patches.append(patch)
                made[key] = patch.id
                added.append(key)
            ids.append(made[key])
        rule = "needs_eyes" if v.verdict == "unresolved" else v.rule
        review["hunks"][i] = {"verdict": v.verdict, "rule": rule, "patches": ids, "note": v.note}
        counts[rule.removeprefix("move+")] += 1
    review["prepass"] = {"timestamp": now(), "counts": dict(counts)}
    ch.save()
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 5a: classify diff hunks, write pp- patches")
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    args = ap.parse_args(argv)
    try:
        ch = Chapter(args.book, args.chapter)
        counts = run(ch)
    except (ReviewError, ConfigError, patchmod.PatchError) as e:
        print(f"prepass: {e}", file=sys.stderr)
        return 1
    total = sum(counts.values())
    print(f"prepass: {args.book} ch{ch.number:02d} {total} hunks -> {ch.wd / 'patches.json'}")
    for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {rule:13} {n:4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
