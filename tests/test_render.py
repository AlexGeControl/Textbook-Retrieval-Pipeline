import yaml

from src.blocks import Block, Span
from src.render import (
    Context,
    escape_start,
    footnote_defs,
    frontmatter,
    has_spans,
    inline,
    note_name,
    pipe_table,
    render_block,
    render_hub,
    render_section,
    slug,
)
from src.sections import Chain, Section

META = {
    "book": "bma",
    "chapter": "ch05",
    "title": "Net Present Value",
    "pdf_pages": [149, 150],
    "printed_pages": [119, 120],
}
CFG = {
    "course": "mitx",
    "title": "Principles of Corporate Finance",
    "edition": "14e (Brealey et al.)",
}


def _ctx(**kw):
    base = {
        "book": "bma",
        "chapter": 5,
        "meta": META,
        "cfg": CFG,
        "certified": True,
        "certified_at": "2026-09-08",
    }
    return Context(**(base | kw))


def _b(id_, type_, *spans, **kw):
    return Block(
        id=id_,
        index=int(id_[-3:]),
        type=type_,
        page_idx=int(id_[1:4]),
        bbox=kw.pop("bbox", (0, 0, 100, 100)),
        spans=tuple(Span(t, c) for t, c in spans),
        **kw,
    )


def test_slug_and_names():
    assert slug("Mini-Case: Vegetron’s CFO Calls Again") == "mini-case-vegetrons-cfo-calls-again"
    assert (
        slug("\x07Measuring  Returns over Different Holding Periods")
        == "measuring-returns-over-different-holding-periods"
    )
    assert len(slug("word " * 40)) <= 60 and not slug("word " * 40).endswith("-")
    assert (
        note_name(_ctx(), Section(3, "5-3", "The Internal Rate of Return Rule", 7))
        == "bma-ch05-03-the-internal-rate-of-return-rule"
    )


def test_escape_start_only_touches_markdown_starters():
    assert escape_start("1. Why NPV") == "1\\. Why NPV"
    assert escape_start("# not a heading") == "\\# not a heading"
    assert escape_start("- not a list") == "\\- not a list"
    assert escape_start("5.1 Self-Test") == "5.1 Self-Test"
    assert escape_start("plain") == "plain"


def test_inline_math_is_trimmed_and_footnote_refs_convert_only_real_markers():
    ctx = _ctx(footnote_ids={"1", "2"})
    spans = (
        Span("text", "flows "),
        Span("equation_inline", " C _ { 0 } "),
        Span("text", " then.<sup>1</sup> 1.1<sup>2</sup> x<sup>3</sup>"),
    )
    assert inline(spans, ctx) == "flows $C _ { 0 }$ then.[^1] 1.1<sup>2</sup> x<sup>3</sup>"


def test_paragraph_list_and_title_rules():
    ctx = _ctx(subheadings={"thepaybackrule"})
    assert (
        render_block(_b("p000-b001", "paragraph", ("text", "  Body text. ")), ctx) == "Body text."
    )
    assert render_block(_b("p000-b002", "paragraph", ("text", "")), ctx) == ""
    lst = _b(
        "p000-b003",
        "list",
        ("text", "∙ first"),
        ("text", "\n"),
        ("text", "2. second"),
        ("text", "\n"),
        ("text", "- third"),
    )
    assert render_block(lst, ctx) == "- first\n2. second\n- third"
    assert (
        render_block(_b("p000-b004", "title", ("text", "The Payback Rule"), level=2), ctx)
        == "## The Payback Rule"
    )
    assert (
        render_block(
            _b("p000-b005", "title", ("text", "EXAMPLE 5.1 ● The Payback Rule"), level=2), ctx
        )
        == "### EXAMPLE 5.1 ● The Payback Rule"
    )
    assert (
        render_block(
            _b("p000-b005", "title", ("text", "Section 5-1 A review"), level=2), ctx, in_hub=True
        )
        == "**Section 5-1 A review**"
    )


def test_currency_dollars_are_escaped_and_inline_math_gets_its_space_back():
    ctx = _ctx()
    para = _b("p000-b006", "paragraph", ("text", "a proposed $1 million investment ($ millions)"))
    assert render_block(para, ctx) == "a proposed \\$1 million investment (\\$ millions)"
    glued = _b(
        "p000-b007",
        "paragraph",
        ("text", "where "),
        ("equation_inline", "C_0 = 1"),
        ("text", "million, so "),
        ("equation_inline", "r"),
        ("text", "."),
    )
    assert render_block(glued, ctx) == "where $C_0 = 1$ million, so $r$."
    t = Block(
        id="p001-b009",
        index=9,
        type="table",
        page_idx=1,
        bbox=(0, 0, 1, 1),
        html="<table><tr><td>Cash Flows ($)</td><td>$C_0$</td><td>$1,949^a$</td></tr>"
        "<tr><td>$4,000</td><td>$ 5,000-$6,000</td><td>$(1 + r)^{2}$</td></tr></table>",
        sub_type="simple_table",
        captions=(Span("text", "Market Value ($ millions)"),),
    )
    out = render_block(t, ctx)
    assert out.startswith("Market Value (\\$ millions)\n\n")
    assert "| Cash Flows (\\$) | $C_0$ | $1,949^a$ |" in out
    assert "| \\$4,000 | \\$ 5,000-\\$6,000 | $(1 + r)^{2}$ |" in out


def test_aside_callout_quotes_every_line_of_a_multiline_block():
    from src.render import aside_callout

    ctx = _ctx()
    run = [_b("p009-b020", "page_aside_text", ("text", "Try It!\nCalculate\nthe MIRR"))]
    assert aside_callout(run, ctx) == "> [!info] Try It!\n> Calculate\n> the MIRR"


def test_running_matter_and_suspects():
    ctx = _ctx(suspects={"p001-b003"}, dropped={"p001-b004"})
    assert render_block(_b("p001-b002", "page_header", ("text", "CHAPTER 5")), ctx) == ""
    assert (
        render_block(
            _b("p001-b003", "page_header", ("text", "Analyzing the Financial Statements")), ctx
        )
        == "Analyzing the Financial Statements"
    )
    assert render_block(_b("p001-b004", "page_header", ("text", "junk")), ctx) == ""


def test_equation_and_tables():
    ctx = _ctx()
    eq = Block(
        id="p001-b001",
        index=1,
        type="equation_interline",
        page_idx=1,
        bbox=(0, 0, 1, 1),
        math=" \\mathrm{NPV} = C_0 \\tag{5.1} ",
    )
    assert render_block(eq, ctx) == "$$\n\\mathrm{NPV} = C_0 \\tag{5.1}\n$$"
    simple = (
        "<table><tr><td>Asset</td><td>a | b</td></tr><tr><td>Cash</td><td>1<br>2</td></tr></table>"
    )
    assert pipe_table(simple) == "| Asset | a \\| b |\n| --- | --- |\n| Cash | 1 2 |"
    assert not has_spans(simple) and has_spans('<table><tr><td colspan="2">x</td></tr></table>')
    t = Block(
        id="p001-b006",
        index=6,
        type="table",
        page_idx=1,
        bbox=(0, 0, 1, 1),
        html=simple,
        sub_type="simple_table",
        captions=(
            Span("text", "◗ TABLE 5.1 Values"),
            Span("text", "\n"),
            Span("text", "Source: BMA"),
        ),
    )
    out = render_block(t, ctx)
    assert out.startswith("TABLE 5.1 Values\n\n| Asset") and out.endswith("Source: BMA")
    complex_html = '<table><tr><td colspan="2">x</td></tr><tr><td>1</td><td>2</td></tr></table>'
    tc = Block(
        id="p001-b007",
        index=7,
        type="table",
        page_idx=1,
        bbox=(0, 0, 1, 1),
        html=complex_html,
        sub_type="complex_table",
    )
    assert render_block(tc, ctx) == complex_html
    empty = Block(
        id="p001-b008",
        index=8,
        type="table",
        page_idx=1,
        bbox=(0, 0, 1, 1),
        html="",
        sub_type="simple_table",
        crop="images/t.jpg",
    )
    out = render_block(empty, ctx)
    assert "![[bma-ch05-p001-b008.jpg]]" in out and "[!warning]" in out and ctx.log


def test_figures_charts_and_decorative_images():
    ctx = _ctx(verdicts={"p003-b000": "verified", "p002-b000": "unresolved"})
    ctx.current = 2
    chart = Block(
        id="p003-b000",
        index=0,
        type="chart",
        page_idx=3,
        bbox=(0, 0, 500, 500),
        sub_type="bar",
        crop="images/c.jpg",
        content="| Category | Value |\n| --- | --- |\n| NPV | 75 |",
        captions=(Span("text", "◗ FIGURE 5.2 Survey"),),
    )
    out = render_block(chart, ctx)
    assert out.split("\n\n")[:2] == ["![[bma-ch05-p003-b000.jpg]]", "FIGURE 5.2 Survey"]
    assert "> [!note]- Chart data (VLM transcription)\n> | Category | Value |" in out
    assert ctx.assets["bma-ch05-p003-b000.jpg"] == ("images/c.jpg", 2)
    flow = Block(
        id="p002-b000",
        index=0,
        type="image",
        page_idx=2,
        bbox=(0, 0, 500, 500),
        sub_type="flowchart",
        crop="images/f.jpg",
        content="```mermaid\ngraph TD\n```",
        captions=(Span("text", "FIGURE 5.1 Cash"),),
    )
    out = render_block(flow, ctx)
    assert "[!note]-" not in out and out.startswith("![[bma-ch05-p002-b000.jpg]]")
    icon = Block(
        id="p000-b013",
        index=13,
        type="image",
        page_idx=0,
        bbox=(10, 10, 40, 40),
        crop="images/i.jpg",
    )
    assert render_block(icon, ctx) == ""
    big = Block(
        id="p000-b014",
        index=14,
        type="image",
        page_idx=0,
        bbox=(0, 0, 900, 900),
        crop="images/b.jpg",
    )
    assert render_block(big, ctx) == "![[bma-ch05-p000-b014.jpg]]" and any(
        "uncaptioned" in line for line in ctx.log
    )


def test_aside_run_becomes_one_callout():
    ctx = _ctx()
    run = [
        _b("p009-b014", "page_aside_text", ("text", "BEYOND THE PAGE")),
        _b("p009-b016", "page_aside_text", ("text", "Calculating the IRR")),
        _b("p009-b017", "page_aside_text", ("text", "mhhe.com/brealey14e")),
    ]
    from src.render import aside_callout

    assert (
        aside_callout(run, ctx)
        == "> [!info] BEYOND THE PAGE\n> Calculating the IRR\n> mhhe.com/brealey14e"
    )


def test_footnote_defs_continuations_and_star_notes():
    ctx = _ctx(footnote_ids={"1"})
    chains = [
        Chain(
            "1",
            [
                _b("p004-b017", "page_footnote", ("text", "<sup>1</sup>Occasionally firms")),
                _b("p004-b018", "page_footnote", ("text", "PV = 10/1.1<sup>2</sup>")),
            ],
        ),
        Chain(None, [_b("p031-b010", "page_footnote", ("text", "*The material in this section"))]),
    ]
    out = footnote_defs(chains, ctx)
    assert (
        out
        == "---\n\n*The material in this section\n\n[^1]: Occasionally firms\n    PV = 10/1.1<sup>2</sup>"
    )


def test_frontmatter_round_trips_with_quoted_section():
    ctx = _ctx()
    sec = Section(1, "5.10", "Ten", 0, printed_pages=(126, 134))
    data = yaml.safe_load(frontmatter(sec, ctx).strip("-\n"))
    assert data == {
        "book": "bma",
        "chapter": 5,
        "course": "mitx",
        "source_pages": [126, 134],
        "certified": True,
        "title": "Ten",
        "section": "5.10",
        "book_title": "Principles of Corporate Finance",
        "edition": "14e (Brealey et al.)",
        "certified_at": "2026-09-08",
    }
    hub = Section(0, None, "Net Present Value", 0, printed_pages=(119, 120))
    assert (
        yaml.safe_load(frontmatter(hub, _ctx(certified=False, certified_at=None)).strip("-\n"))[
            "certified_at"
        ]
        is None
    )


def test_section_note_and_hub():
    ctx = _ctx()
    hub = Section(
        0,
        None,
        "Net Present Value",
        0,
        blocks=[_b("p000-b001", "paragraph", ("text", "opener"))],
        printed_pages=(119, 120),
    )
    s1 = Section(
        1,
        "5-1",
        "First",
        0,
        anchor="p000-b002",
        blocks=[
            _b("p000-b003", "paragraph", ("text", "body one")),
            _b("p001-b000", "paragraph", ("text", "body two")),
        ],
        printed_pages=(119, 120),
    )
    s2 = Section(2, None, "Second", 1, anchor="p001-b001", blocks=[], printed_pages=(120, 120))
    secs = [hub, s1, s2]
    note = render_section(s1, secs, ctx)
    assert "\n# 5-1 First\n" in note
    assert note.count("%% p. 119 %%") == 1 and note.count("%% p. 120 %%") == 1
    assert note.rstrip().endswith(
        "[[bma-ch05-00-net-present-value|↑ Net Present Value]] · [[bma-ch05-02-second|Second →]]"
    )
    hub_note = render_hub(secs, ctx)
    assert (
        "# Net Present Value" in hub_note and "**opener**" not in hub_note and "opener" in hub_note
    )
    assert "- [[bma-ch05-01-first|5-1 First]]\n- [[bma-ch05-02-second|Second]]" in hub_note
