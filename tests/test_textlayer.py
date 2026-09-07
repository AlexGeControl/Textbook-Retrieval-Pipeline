import pymupdf
import pytest

from src.textlayer import Char, Word, find_run, page_words, render_words, stream_text, words_in_bbox
from tests.helpers import work_chapter


def _w(text, line=(0, 0), sup_from=None, x=0):
    chars = tuple(Char(c, sup_from is not None and i >= sup_from) for i, c in enumerate(text))
    return Word(chars, pymupdf.Rect(x, 0, x + 10 * len(text), 10), line)


def test_render_words_wraps_superscript_and_keeps_printed_quotes_and_dashes():
    words = [_w("Value’s"), _w("flows.5", sup_from=6), _w("—"), _w("next")]
    assert render_words(words) == "Value’s flows.<sup>5</sup> — next"


def test_render_words_joins_the_word_a_soft_hyphen_broke():
    words = [_w("invest\u00ad", line=(0, 0)), _w("ing", line=(0, 1)), _w("now", line=(0, 1))]
    assert render_words(words) == "investing now"


def test_stream_text_uses_newline_between_lines():
    words = [_w("a", line=(0, 0)), _w("b", line=(0, 0)), _w("c", line=(0, 1))]
    assert stream_text(words) == "a b\nc"


def test_find_run_is_unique_or_none():
    words = [_w("the", x=0), _w("capital", x=40), _w("of", x=120), _w("the", x=150)]
    run = find_run(words, ["capital", "of"])
    assert [w.text for w in run] == ["capital", "of"]
    assert find_run(words, ["the"]) is None
    assert find_run(words, ["missing"]) is None
    assert find_run(words, []) is None


def test_find_run_matches_across_dehyphenation():
    words = [_w("capi-", line=(0, 0)), _w("tal", line=(0, 1)), _w("budgeting", line=(0, 1))]
    run = find_run(words, ["capital", "budgeting"])
    assert [w.text for w in run] == ["capi-", "tal", "budgeting"]


def test_words_in_bbox_uses_centre_and_pad():
    words = [_w("in", x=100), _w("out", x=900)]
    inside = words_in_bbox(words, (90, 0, 200, 20), pymupdf.Rect(0, 0, 1000, 1000))
    assert [w.text for w in inside] == ["in"]


@pytest.mark.workdir
def test_bma_ch05_page_4_carries_a_superscript_footnote_marker():
    doc = pymupdf.open(work_chapter("bma", "ch05") / "chapter.pdf")
    marked = [w.text for w in page_words(doc[4]) if any(c.sup for c in w.chars)]
    assert any(t.endswith("1") for t in marked), marked[:10]


@pytest.mark.workdir
def test_ops_ligatures_are_expanded():
    doc = pymupdf.open(work_chapter("ops", "ch05") / "chapter.pdf")
    assert not any("ﬀ" in w.text or "ﬁ" in w.text for page in doc for w in page_words(page))
