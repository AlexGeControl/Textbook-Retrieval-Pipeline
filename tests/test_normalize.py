from src.normalize import (
    MD_RULES,
    PDF_RULES,
    dehyphenate,
    drop_bullets_and_list_markers,
    drop_soft_hyphens,
    flatten_latex,
    join_letter_spaced_caps,
    nfkc,
    normalize,
    punctuation_variants,
    strip_markup,
    tokenize,
)


def test_flatten_latex_strips_commands_braces_and_inner_spaces():
    assert flatten_latex("r_f") == "rf"
    assert flatten_latex("\\frac{C}{1+r}") == "C1+r"
    assert flatten_latex("\\$ 5 0 0") == "$500"
    assert flatten_latex("x^{2}") == "x2"
    assert flatten_latex("C _ { 0 } = - \\mathbb { S } 1") == "C0=-S1"


def test_strip_markup_removes_sup_and_sub_tags_only():
    assert strip_markup("year.<sup>9</sup> and CO<sub>2</sub>") == "year.9 and CO2"
    assert strip_markup("costs $250,000 and 5% a_b") == "costs $250,000 and 5% a_b"


def test_nfkc_folds_ligatures_and_spaces():
    assert nfkc("ﬁnance ﬂow x²") == "finance flow x2"


def test_punctuation_variants_fold_quotes_and_dashes():
    assert punctuation_variants("“q” ‘a’ 5–6 — x − 1") == "\"q\" 'a' 5-6 - x - 1"


def test_drop_soft_hyphens():
    assert drop_soft_hyphens("in­vest­ment") == "investment"


def test_dehyphenate_joins_line_breaks_and_drops_intra_word_hyphens():
    assert dehyphenate("exam-\nple of supply-and-demand") == "example of supplyanddemand"
    assert dehyphenate("- 1,000 and -5") == "- 1,000 and -5"


def test_drop_bullets_and_list_markers():
    s = "● ● ● Intro\n- item one\n1. item two\n• x\n∙ y"
    assert tokenize(drop_bullets_and_list_markers(s)) == [
        "Intro",
        "item",
        "one",
        "item",
        "two",
        "x",
        "y",
    ]
    assert drop_bullets_and_list_markers("rose 1.5 percent") == "rose 1.5 percent"


def test_tokenize_collapses_all_whitespace():
    assert tokenize("a\tb  c\nd ") == ["a", "b", "c", "d"]


def test_pdf_pipeline_on_a_real_text_layer_string():
    s = "Investors  in these funds, and­the exam-\nple of “relative strength”"
    assert tokenize(normalize(s, PDF_RULES)) == [
        "Investors",
        "in",
        "these",
        "funds,",
        "andthe",
        "example",
        "of",
        '"relative',
        'strength"',
    ]


def test_md_pipeline_on_a_real_v2_span_string():
    # a paragraph's spans joined by the guardrail: text, flattened inline math, text
    s = "price of $72 and rate " + flatten_latex("r _ { f }") + " per year.<sup>9</sup>"
    assert tokenize(normalize(s, MD_RULES)) == [
        "price",
        "of",
        "$72",
        "and",
        "rate",
        "rf",
        "per",
        "year.9",
    ]


def test_no_rule_parses_markdown():
    assert flatten_latex not in MD_RULES and flatten_latex not in PDF_RULES
    assert MD_RULES[1:] == PDF_RULES  # the md side only adds markup stripping


def test_join_letter_spaced_caps_folds_small_caps_running_heads():
    # bkm control page running head: PyMuPDF groups the glyphs as `PA R T`, mineru as `P A R T`
    assert join_letter_spaced_caps("PA R T I I I Equilibrium in") == "PARTIII Equilibrium in"
    assert join_letter_spaced_caps("P A R T I I I Equilibrium in") == "PARTIII Equilibrium in"
    assert join_letter_spaced_caps("plan A or B") == "plan A or B"
    assert join_letter_spaced_caps("the US GDP rose") == "the US GDP rose"
    assert join_letter_spaced_caps("NPV IRR") == "NPV IRR"
    assert join_letter_spaced_caps("capi tal") == "capi tal"
    assert join_letter_spaced_caps in MD_RULES and join_letter_spaced_caps in PDF_RULES
