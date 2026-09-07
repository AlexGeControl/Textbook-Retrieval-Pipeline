from src.fold import clean_title, fold, letters


def test_fold_drops_punctuation_whitespace_case_and_markup_but_keeps_symbols():
    assert fold("Net Present Value’s Competitors") == fold("net present values competitors")
    assert fold("5-1: A Review") == fold("5-1 A Review") == "51areview"
    assert fold("Normality<sup>*</sup>") == "normality"
    assert fold("Connect®") != fold("Connect")
    assert fold("Treasury Bills, 1926-2021") == fold("Treasury Bills, 1926–2021")


def test_fold_drops_control_characters():
    assert fold("\x07Measuring Returns") == "measuringreturns"


def test_letters_keeps_alphanumerics_only():
    assert letters("C _ { 0 } = - $ 1") == "c01"
    assert letters("f (x) \\geq 0") == "fxgeq0"


def test_clean_title():
    assert clean_title("\x07Measuring  Returns\n") == "Measuring Returns"
