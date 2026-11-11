"""scripts/benchmark_report.py — the gate-5 table from reviewed work dirs (plan Task 13)."""

import json

import pytest

from scripts.benchmark_report import COLUMNS, reviewed_dirs, row, table
from src.prepass import run as prepass
from src.review import Chapter
from src.review_checks import run as checks
from tests.helpers import make_work_dir, work_chapter
from tests.test_vault_commit import CHART, FLAGS, PARA, SECTIONS, TITLE, TITLE2


def _reviewed(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[TITLE, PARA, CHART], [TITLE2, PARA]],
        flagged=FLAGS,
        sections=SECTIONS,
        pdf_lines=["body one", "body one"],
    )
    prepass(Chapter("bma", 5))
    checks(Chapter("bma", 5))
    return wd


def test_row_and_table_from_a_reviewed_chapter(tmp_path, monkeypatch):
    wd = _reviewed(tmp_path, monkeypatch)
    r = row(wd)
    assert r["chapter"] == "bma/ch05" and r["hunks"] == 0 and r["flagged"] == 1
    assert r["status"] == "pending_review" and r["formula_error_rate"] == "n/a"
    assert r["table_cell_accuracy"] == "n/a" and r["edge_glyph_sup"] == 0 and r["minutes"] == ""
    assert set(r) == set(COLUMNS)
    md = table([r])
    assert md.splitlines()[0].startswith("| chapter |") and "bma/ch05" in md
    assert "body one" not in md


def test_reviewed_dirs_needs_the_review_key_and_honours_the_chapter_filter(tmp_path, monkeypatch):
    wd = _reviewed(tmp_path, monkeypatch)
    other = tmp_path / "bkm" / "ch15"  # extracted, never reviewed: no `review` key
    other.mkdir(parents=True)
    (other / "qa_report.json").write_text(json.dumps({"status": "pending_review"}))
    assert reviewed_dirs(tmp_path) == [wd]
    assert reviewed_dirs(tmp_path, ["bma/ch05", "bkm/ch15"]) == [wd]
    assert reviewed_dirs(tmp_path, ["bkm/ch15"]) == []


@pytest.mark.workdir
def test_row_on_certified_bma_ch05_matches_the_gate_4_record():
    r = row(work_chapter("bma", "ch05"))  # read-only: row() never writes
    assert r["status"] == "certified" and r["pages"] == 30 and r["hunks"] == 57
    assert r["flagged"] == 67 and r["tables"] == 38 and r["formulas"] == 20
    assert (r["tierA_match"], r["tierA_mismatch"]) == (65, 2)
    assert r["rv_patches"] == 16 and r["crops_opened"] == 87 and r["minutes"] == "70"
    assert r["unresolved"] == 0 and r["footnotes_unmatched"] == 0
