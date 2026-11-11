"""The equality stage 5 uses for headings, hunk cores and table bags (design §6, §9).

`fold` keeps symbols (category S) so `Connect®` never equals `Connect`; it drops punctuation,
whitespace, control characters (the bkm outline carries a U+0007) and `<sup>/<sub>` tags.
"""

from __future__ import annotations

import unicodedata

from src.normalize import strip_markup


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", strip_markup(s))
    return "".join(
        ch for ch in s if not ch.isspace() and unicodedata.category(ch)[0] not in "PC"
    ).casefold()


def letters(s: str) -> str:
    """Alphanumerics only, casefolded: the comparison for LaTeX against text-layer glyphs."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", s) if ch.isalnum()).casefold()


def clean_title(s: str) -> str:
    """An outline or block title as printed: control characters out, whitespace collapsed."""
    return " ".join("".join(ch for ch in s if unicodedata.category(ch) != "Cc").split())
