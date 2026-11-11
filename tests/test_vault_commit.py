import json

import pytest

from src.review import Chapter
from src.vault_commit import render_chapter, select, staging_dir
from tests.helpers import make_work_dir

TITLE = {
    "type": "title",
    "bbox": [80, 40, 600, 70],
    "content": {"title_content": [{"type": "text", "content": "5-1 First"}], "level": 2},
}
PARA = {
    "type": "paragraph",
    "bbox": [80, 80, 600, 120],
    "content": {"paragraph_content": [{"type": "text", "content": "body one"}]},
}
CHART = {
    "type": "chart",
    "bbox": [80, 200, 600, 500],
    "sub_type": "bar",
    "content": {
        "content": "| A | B |\n| --- | --- |\n| 1 | 2 |",
        "image_source": {"path": "images/c.jpg"},
        "chart_caption": [{"type": "text", "content": "FIGURE 5.2"}],
        "chart_footnote": [],
    },
}
TITLE2 = {
    "type": "title",
    "bbox": [80, 40, 600, 70],
    "content": {"title_content": [{"type": "text", "content": "Second"}], "level": 2},
}
SECTIONS = [
    {"number": "5-1", "title": "First", "pdf_page": 149, "printed_page": 119, "level": 3},
    {"number": None, "title": "Second", "pdf_page": 150, "printed_page": 120, "level": 3},
]
FLAGS = [{"id": "p000-b002", "type": "chart", "crop": "images/c.jpg", "reason": "vlm_generated"}]


@pytest.fixture
def wd(tmp_path, monkeypatch):
    import src.vault_commit

    monkeypatch.setattr(src.vault_commit, "VAULT", tmp_path / "vault")
    return make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[TITLE, PARA, CHART], [TITLE2, PARA]],
        flagged=FLAGS,
        sections=SECTIONS,
        pdf_lines=["body one", "body one"],
    )


def test_render_chapter_writes_notes_assets_and_manifest(wd):
    ch = Chapter("bma", 5)
    ch.review["blocks"][0]["verdict"] = "verified"
    ch.save()
    tree = render_chapter(Chapter("bma", 5), certified=False)
    assert tree == staging_dir(ch)
    names = sorted(p.name for p in tree.glob("*.md"))
    assert names == [
        "bma-ch05-00-net-present-value-and-other-investment-criteria.md",
        "bma-ch05-01-first.md",
        "bma-ch05-02-second.md",
    ]
    assert (tree / "assets" / "bma-ch05-p000-b002.jpg").exists()
    m = json.loads((tree / "manifest.json").read_text())
    assert m["status"] == "pending_review" and m["chapter"] == 5
    assert m["files"]["assets/bma-ch05-p000-b002.jpg"]["section"] == 1
    assert set(m["files"]) == {*names, "assets/bma-ch05-p000-b002.jpg"}
    assert "certified: false" in (tree / "bma-ch05-01-first.md").read_text()
    assert "[!note]- Chart data" in (tree / "bma-ch05-01-first.md").read_text()


def test_section_render_merges_and_full_render_removes_stale_files(wd):
    ch = Chapter("bma", 5)
    tree = render_chapter(ch, certified=False)
    (tree / "bma-ch05-09-stale.md").write_text("x")
    render_chapter(ch, certified=False, section="2")
    assert (tree / "bma-ch05-09-stale.md").exists()  # a section render touches only its files
    m = json.loads((tree / "manifest.json").read_text())
    assert "bma-ch05-01-first.md" in m["files"]
    render_chapter(ch, certified=False)
    assert not (tree / "bma-ch05-09-stale.md").exists()


def test_select_by_ordinal_name_or_slug(wd):
    from src.sections import resolve
    from src.vault_commit import pages_of

    ch = Chapter("bma", 5)
    secs = resolve(ch.meta, pages_of(ch.patched_blocks(), 2))
    assert [s.ordinal for s in select(secs, "2")] == [2]
    assert [s.ordinal for s in select(secs, "bma-ch05-01-first")] == [1]
    assert [s.ordinal for s in select(secs, "first")] == [1]
    with pytest.raises(ValueError, match="no section"):
        select(secs, "nope")
