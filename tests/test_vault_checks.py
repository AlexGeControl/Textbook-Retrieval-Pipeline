import pytest

from src.review import Chapter
from src.vault_checks import check_note, check_tree
from src.vault_commit import render_chapter
from tests.helpers import make_work_dir
from tests.test_vault_commit import CHART, FLAGS, PARA, SECTIONS, TITLE, TITLE2


@pytest.fixture
def tree(tmp_path, monkeypatch):
    import src.vault_commit

    monkeypatch.setattr(src.vault_commit, "VAULT", tmp_path / "vault")
    make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[TITLE, PARA, CHART], [TITLE2, PARA]],
        flagged=FLAGS,
        sections=SECTIONS,
        pdf_lines=["body one", "body one"],
    )
    return render_chapter(Chapter("bma", 5), certified=False)


def test_clean_tree_has_no_problems(tree):
    assert check_tree(tree, Chapter("bma", 5)) == []


def _note(body, certified="false"):
    return f"---\nbook: bma\nchapter: 5\ncourse: mitx\nsource_pages: [119, 119]\ncertified: {certified}\ntitle: T\nsection: '5-1'\nbook_title: B\nedition: E\ncertified_at: null\n---\n\n# T\n\n{body}\n"


@pytest.mark.parametrize(
    "body, needle",
    [
        ("$$\nx\n", "$$"),
        ("a $ x$ b", "space inside"),
        ("$\\frac{a}{b$", "expecting"),
        ("| a | b |\n| --- |\n| 1 | 2 |", "pipe"),
        ("![[missing.jpg]]", "unresolved embed"),
        ("[[bma-ch05-77-nope]]", "unresolved link"),
        ("text[^1]", "footnote"),
        ("> [!info] head\nnot quoted", "callout"),
        ("# Second H1", "one H1"),
        ("%% p. 1 %% and %%", "%%"),
    ],
)
def test_check_note_finds_each_fault(tree, body, needle):
    problems = check_note(_note(body), "bma-ch05-01-first.md", tree, certified=False)
    assert any(needle in p.msg for p in problems), [p.msg for p in problems]


@pytest.mark.parametrize(
    "body",
    [
        "costs \\$4,000 and yields \\$5,000 next year, or \\$ 6,000.",
        "<table><tr><td>Cash ($)</td><td>$4,000</td><td>$ 5,000</td></tr></table>",
        "| Cash (\\$) | $C_0$ |\n| --- | --- |\n| \\$4,000 | \\$ 5,000 |",
    ],
)
def test_check_note_ignores_currency_dollars(tree, body):
    problems = check_note(_note(body), "bma-ch05-01-first.md", tree, certified=False)
    assert not any("$" in p.msg for p in problems), [p.msg for p in problems]


def test_check_note_pairs_inline_math_in_order(tree):
    body = "Of course, $C _ { 1 }$ is the payoff and $- C _ { 0 }$ is the investment.\n\n"
    body += "| $C_0$ | $C_1$ | $C_2$ |\n| --- | --- | --- |\n| -\\$200 | +\\$100 | +\\$100 |"
    problems = check_note(_note(body), "bma-ch05-01-first.md", tree, certified=False)
    assert not any("$" in p.msg for p in problems), [p.msg for p in problems]


def test_check_note_frontmatter_and_status(tree):
    bad = "---\nbook: bma\n---\n\n# T\n"
    assert any(
        "frontmatter" in p.msg
        for p in check_note(bad, "bma-ch05-01-first.md", tree, certified=False)
    )
    assert any(
        "certified" in p.msg
        for p in check_note(_note("x"), "bma-ch05-01-first.md", tree, certified=True)
    )


def test_check_tree_catches_manifest_drift(tree):
    (tree / "bma-ch05-01-first.md").write_text(
        (tree / "bma-ch05-01-first.md").read_text() + "\nextra\n"
    )
    assert any("sha256" in p.msg for p in check_tree(tree, Chapter("bma", 5)))
    (tree / "orphan.md").write_text("x")
    assert any("unlisted" in p.msg for p in check_tree(tree, Chapter("bma", 5)))
