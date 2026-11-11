"""Text-layer access for stage 5 (design §5–§6).

Words are rebuilt from PyMuPDF `rawdict` characters so a footnote marker set in its own span
stays attached to its word, and each character keeps the span's superscript flag. Ligatures are
expanded because TEXT_PRESERVE_LIGATURES is not passed. This module only reads.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import pymupdf

from src.normalize import PDF_RULES, normalize, tokenize

FLAGS = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP
SOFT_HYPHEN = "\u00ad"
SUPERSCRIPT = 1  # rawdict span flags, bit 0


@dataclass(frozen=True)
class Char:
    c: str
    sup: bool


@dataclass(frozen=True)
class Word:
    chars: tuple[Char, ...]
    rect: pymupdf.Rect
    line: tuple[int, int]  # (block_no, line_no) in PyMuPDF order

    @property
    def text(self) -> str:
        return "".join(ch.c for ch in self.chars)

    @property
    def soft_hyphen_end(self) -> bool:
        return self.text.endswith(SOFT_HYPHEN)

    def centre(self) -> pymupdf.Point:
        return pymupdf.Point((self.rect.x0 + self.rect.x1) / 2, (self.rect.y0 + self.rect.y1) / 2)


def _word(chars: list[Char], rects: list[pymupdf.Rect], line: tuple[int, int]) -> Word:
    rect = pymupdf.Rect(rects[0])
    for r in rects[1:]:
        rect |= r
    return Word(tuple(chars), rect, line)


def page_words(page: pymupdf.Page) -> list[Word]:
    """Words in PyMuPDF order, split at whitespace characters inside each line."""
    out: list[Word] = []
    raw = page.get_text("rawdict", flags=FLAGS)
    for b_no, block in enumerate(raw["blocks"]):
        if block.get("type", 0) != 0:
            continue
        for l_no, line in enumerate(block.get("lines", [])):
            chars: list[Char] = []
            rects: list[pymupdf.Rect] = []
            for span in line.get("spans", []):
                sup = bool(span.get("flags", 0) & SUPERSCRIPT)
                for ch in span.get("chars", []):
                    if ch["c"].isspace():
                        if chars:
                            out.append(_word(chars, rects, (b_no, l_no)))
                            chars, rects = [], []
                        continue
                    chars.append(Char(ch["c"], sup))
                    rects.append(pymupdf.Rect(ch["bbox"]))
            if chars:
                out.append(_word(chars, rects, (b_no, l_no)))
    return out


def words_in_bbox(
    words: list[Word], bbox: tuple[int, int, int, int], page_rect: pymupdf.Rect, pad: float = 2.0
) -> list[Word]:
    """Words whose centre lies in a 0–1000 block bbox (the guardrail's mask geometry)."""
    sx, sy = page_rect.width / 1000, page_rect.height / 1000
    x0, y0, x1, y1 = bbox
    area = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy) + (-pad, -pad, pad, pad)
    return [w for w in words if w.centre() in area]


def stream_text(words: list[Word]) -> str:
    """Words joined as the guardrail streams them: ' ' within a line, '\\n' between lines."""
    parts: list[str] = []
    prev = None
    for w in words:
        if parts:
            parts.append(" " if w.line == prev else "\n")
        parts.append(w.text)
        prev = w.line
    return "".join(parts)


def find_run(
    words: list[Word],
    tokens: list[str],
    rules: tuple[Callable[[str], str], ...] = PDF_RULES,
) -> list[Word] | None:
    """The unique run of raw words whose normalized tokens equal `tokens`, else None."""
    want = list(tokens)
    if not want:
        return None
    hits: list[tuple[int, int]] = []
    n = len(words)
    for i in range(n):
        for j in range(i + 1, min(n, i + 3 * len(want) + 3) + 1):
            got = tokenize(normalize(stream_text(words[i:j]), rules))
            if len(got) >= len(want):
                if got == want:
                    hits.append((i, j))
                break
    if len({j for _, j in hits}) != 1:
        return None
    start = max(i for i, _ in hits)  # shortest window when a leading word normalizes away
    return words[start : hits[0][1]]


def _wrap(s: str, sup: bool) -> str:
    return f"<sup>{s}</sup>" if sup else s


def _with_sup(w: Word) -> str:
    out: list[str] = []
    run: list[str] = []
    cur: bool | None = None
    for ch in w.chars:
        if cur is not None and ch.sup != cur:
            out.append(_wrap("".join(run), cur))
            run = []
        run.append(ch.c)
        cur = ch.sup
    if run:
        out.append(_wrap("".join(run), bool(cur)))
    return "".join(out)


_HYPHEN_END = re.compile(r"\w-$")  # a printed hyphen right after a letter or digit


def _breaks_word(w: Word, nxt: Word | None) -> bool:
    """`w` ends in a printed hyphen and the run continues with a word on another line. The text
    layer cannot say whether that hyphen is soft (licens-/ing) or a compound's (long-/term):
    render_words() joins it like a soft hyphen and line_end_hyphens() reports the word so the
    pre-pass can leave the decision to the reviewer (bma ch19, 2026-09-30)."""
    return (
        nxt is not None
        and w.line != nxt.line
        and _HYPHEN_END.search(w.text) is not None
        and nxt.text[:1].isalpha()
    )


def render_words(words: list[Word]) -> str:
    """Raw text of a run: single spaces, soft-hyphen and line-end hyphen breaks joined,
    superscripts wrapped."""
    out: list[str] = []
    join_next = False
    for i, w in enumerate(words):
        if out and not join_next:
            out.append(" ")
        text = _with_sup(w).replace(SOFT_HYPHEN, "")
        nxt = words[i + 1] if i + 1 < len(words) else None
        if _breaks_word(w, nxt) and text.endswith("-"):
            text, join_next = text[:-1], True
        else:
            join_next = w.soft_hyphen_end
        out.append(text)
    return "".join(out)


def line_end_hyphens(words: list[Word]) -> list[str]:
    """The words render_words() joined across a printed (not soft) line-end hyphen, as joined."""
    out: list[str] = []
    cur: str | None = None
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        text = w.text.replace(SOFT_HYPHEN, "")
        if cur is not None:
            cur += text[:-1] if _breaks_word(w, nxt) else text
            if not _breaks_word(w, nxt):
                out.append(cur)
                cur = None
        elif _breaks_word(w, nxt):
            cur = text[:-1]
    return out
