"""Guardrail normalization rules (design §6). Pure str -> str functions; order matters.

Rules are appended, never reordered silently. Every rule was introduced by a failing test on a
string captured from the fixtures or the benchmark chapters. The md side is content_list_v2:
unescaped text spans plus inline-math spans, so no rule here parses markdown — inline math is
flattened span by span with flatten_latex before the string rules run.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

_LATEX_CMD = re.compile(r"\\[A-Za-z]+")
_MARKUP_TAG = re.compile(r"</?su[bp]>")
_PUNCT = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "−": "-"})
_LINE_END_HYPHEN = re.compile(r"(\w)-\n\s*(\w)")
_INTRA_WORD_HYPHEN = re.compile(r"(?<=\w)-(?=\w)")
_BULLETS = re.compile(r"[●•▪■◦∙]")
_LIST_MARKER = re.compile(r"(?m)^[ \t]*[-*][ \t]+")
_SOFT_HYPHEN_BREAK = re.compile("\u00ad\n\\s*")
_SPACED_CAPS = re.compile(r"(?<!\S)(?:[A-Z]{1,2}[ \t]+){2,}[A-Z]{1,2}(?!\S)")
_ZERO_WIDTH_SPACE = "\u200b"


def flatten_latex(latex: str) -> str:
    """Inline-math LaTeX -> the bare glyphs the text layer holds.

    `\\$` -> `$`; LaTeX commands, braces, `^`, `_` and all whitespace removed (the MFR spaces
    digits: `\\$ 5 0 0` -> `$500`, `r_f` -> `rf`, `\\frac{C}{1+r}` -> `C1+r`).
    """
    s = latex.replace("\\$", "$")
    s = _LATEX_CMD.sub("", s)
    return re.sub(r"[{}^_\s]", "", s)


def strip_markup(s: str) -> str:
    """<sup>/<sub> tags mineru wraps around footnote markers and exponents -> bare text."""
    return _MARKUP_TAG.sub("", s)


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def punctuation_variants(s: str) -> str:
    return s.translate(_PUNCT)


def drop_soft_hyphens(s: str) -> str:
    """Remove U+00AD; a soft hyphen at a line end joins the word it broke.

    stats ch05 sets 143 line ends as `invest\\u00ad\\ning` in the text layer while mineru holds
    `investing`; dropping the hyphen alone left the line break as a word split (gate 3, 2026-09-06).
    """
    return _SOFT_HYPHEN_BREAK.sub("", s).replace("\u00ad", "")


def dehyphenate(s: str) -> str:
    s = _LINE_END_HYPHEN.sub(r"\1\2", s)
    return _INTRA_WORD_HYPHEN.sub("", s)


def drop_bullets_and_list_markers(s: str) -> str:
    """Bullet glyphs and leading `- `/`* ` markers go; numbered markers stay on both sides.

    Digit stripping was asymmetric (gate 3, 2026-09-06): PyMuPDF sets a bold question ordinal on
    its own line, so `1.\\nWhy` kept it while mineru's `1. Why` lost it (corpfin 11, strat 21
    hunks), and a sentence-final `0.` at a PDF line start was eaten. Neither side drops a real
    list number, so nothing is normalized away.
    """
    return _LIST_MARKER.sub("", _BULLETS.sub(" ", s))


def join_letter_spaced_caps(s: str) -> str:
    """Letter-spaced small-caps heads: `P A R T I I I` and `PA R T I I I` -> `PARTIII`.

    PyMuPDF and mineru group the glyphs of a tracked heading differently. Only runs of three or
    more tokens of at most two capitals are joined, so split words (`capi tal`) stay visible.
    """
    return _SPACED_CAPS.sub(lambda m: re.sub(r"[ \t]+", "", m.group(0)), s)


def drop_zero_width_spaces(s: str) -> str:
    """U+200B: PyMuPDF emits it as a word of its own or glued to glyphs in formula-set text.

    Seen on bma ch06 (printed pages 163, 169, 171) where display formulas are set as running
    text; NFKC does not touch it and `str.split` does not treat it as whitespace.
    """
    return s.replace(_ZERO_WIDTH_SPACE, "")


def tokenize(s: str) -> list[str]:
    return s.split()


MD_RULES: tuple[Callable[[str], str], ...] = (
    strip_markup,
    nfkc,
    punctuation_variants,
    drop_soft_hyphens,
    dehyphenate,
    drop_bullets_and_list_markers,
    join_letter_spaced_caps,
    drop_zero_width_spaces,
)
PDF_RULES: tuple[Callable[[str], str], ...] = (
    nfkc,
    punctuation_variants,
    drop_soft_hyphens,
    dehyphenate,
    drop_bullets_and_list_markers,
    join_letter_spaced_caps,
    drop_zero_width_spaces,
)


def normalize(s: str, rules: tuple[Callable[[str], str], ...]) -> str:
    for rule in rules:
        s = rule(s)
    return s
