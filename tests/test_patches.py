import json

import pytest

from src.blocks import Block, Span
from src.patches import Patch, PatchError, apply, load, next_id, save, target_text, validate


def _para(id_, *spans, type_="paragraph"):
    return Block(
        id=id_,
        index=int(id_[-3:]),
        type=type_,
        page_idx=int(id_[1:4]),
        bbox=(0, 0, 100, 100),
        spans=tuple(Span(t, c) for t, c in spans),
    )


def _eq(id_, math):
    return Block(
        id=id_, index=0, type="equation_interline", page_idx=0, bbox=(0, 0, 1, 1), math=math
    )


P1 = _para(
    "p000-b001", ("text", "the capi tal budget "), ("equation_inline", "C_0"), ("text", " here")
)
P2 = _para("p000-b002", ("text", "#"), type_="page_aside_text")
BLOCKS = [P1, P2, _eq("p000-b003", "\\frac{a}{b")]
BY_ID = {b.id: b for b in BLOCKS}


def _p(**kw):
    base = {
        "id": "pp-0001",
        "block": "p000-b001",
        "op": "replace",
        "old": "capi tal",
        "new": "capital",
    }
    base |= {"source": "prepass", "rule": "same_letters", "hunk": 0}
    base |= kw
    return Patch(**base)


def test_replace_applies_inside_one_span_and_leaves_input_untouched():
    out = apply(BLOCKS, [_p()])
    assert out[0].text() == "the capital budget  here"
    assert BLOCKS[0].text() == "the capi tal budget  here"
    assert out[0].inline_math() == ("C_0",)


def test_replace_rejects_old_absent_or_repeated():
    with pytest.raises(PatchError, match="occurs 0 times"):
        validate(_p(old="nowhere"), BY_ID)
    with pytest.raises(PatchError, match="occurs 2 times"):
        validate(_p(old="t"), {"p000-b001": _para("p000-b001", ("text", "t t"))})


def test_replace_rejects_old_crossing_a_span_boundary():
    with pytest.raises(PatchError, match="crosses a span"):
        validate(_p(old="budget  here"), BY_ID)


def test_drop_block_removes_the_block():
    out = apply(
        BLOCKS, [_p(id="pp-0002", block="p000-b002", op="drop_block", old="", new="", rule="junk")]
    )
    assert [b.id for b in out] == ["p000-b001", "p000-b003"]


def test_set_ops_are_reviewer_only_and_type_checked():
    with pytest.raises(PatchError, match="reviewer-only"):
        validate(_p(op="set_math", block="p000-b003", old="", new="x"), BY_ID)
    with pytest.raises(PatchError, match="set_math on a paragraph"):
        validate(_p(id="rv-0001", source="review", op="set_math", old="", new="x"), BY_ID)
    out = apply(
        BLOCKS,
        [_p(id="rv-0001", source="review", op="set_math", block="p000-b003", old="", new="x")],
    )
    assert out[2].math == "x"


def test_set_inline_math_rewrites_exactly_one_equation_inline_span():
    with pytest.raises(PatchError, match="reviewer-only"):
        validate(_p(op="set_inline_math", old="C_0", new="\\$ 1"), BY_ID)
    rv = _p(id="rv-0001", source="review", op="set_inline_math", old="C_0", new="\\$ 1")
    out = apply(BLOCKS, [rv])
    assert out[0].inline_math() == ("\\$ 1",)
    assert out[0].text() == BLOCKS[0].text()  # text spans untouched
    with pytest.raises(PatchError, match="inline-math span .* occurs 0 times"):
        validate(
            _p(id="rv-0002", source="review", op="set_inline_math", old="nope", new="x"), BY_ID
        )
    with pytest.raises(PatchError, match="set_inline_math on a equation_interline"):
        validate(
            _p(
                id="rv-0003",
                source="review",
                op="set_inline_math",
                block="p000-b003",
                old="",
                new="x",
            ),
            BY_ID,
        )
    with pytest.raises(PatchError, match="non-empty new"):
        validate(_p(id="rv-0004", source="review", op="set_inline_math", old="C_0", new=" "), BY_ID)


def test_id_prefix_must_match_source():
    with pytest.raises(PatchError, match="prefix"):
        validate(_p(id="rv-0001"), BY_ID)
    assert next_id([], "prepass") == "pp-0001"
    assert next_id([_p(), _p(id="pp-0007")], "prepass") == "pp-0008"
    assert next_id([_p()], "review") == "rv-0001"


def test_target_text_per_type():
    assert target_text(P1, "replace") == "the capi tal budget  here"
    assert target_text(BLOCKS[2], "replace") == "\\frac{a}{b"


def test_save_load_round_trip_and_sha_binding(tmp_path):
    content_list = tmp_path / "chapter_content_list_v2.json"
    content_list.write_text("[]")
    save(tmp_path, [_p()], content_list)
    assert load(tmp_path, content_list) == [_p()]
    data = json.loads((tmp_path / "patches.json").read_text())
    assert set(data) == {"content_list_sha256", "patches"}
    content_list.write_text("[[]]")
    with pytest.raises(PatchError, match="re-extracted"):
        load(tmp_path, content_list)


def test_load_without_file_is_empty(tmp_path):
    content_list = tmp_path / "c.json"
    content_list.write_text("[]")
    assert load(tmp_path, content_list) == []
