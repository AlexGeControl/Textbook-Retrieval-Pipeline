import json
import subprocess
import sys

import pytest

from src.prepass import run as prepass
from src.review import Chapter, ReviewError, finalize
from src.review_checks import run as checks
from tests.helpers import make_work_dir
from tests.test_vault_commit import CHART, FLAGS, PARA, SECTIONS, TITLE, TITLE2


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


def test_finalize_refuses_before_prepass_and_start(wd):
    with pytest.raises(ReviewError, match="prepass"):
        finalize(Chapter("bma", 5))
    prepass(Chapter("bma", 5))
    with pytest.raises(ReviewError, match="start"):
        finalize(Chapter("bma", 5))


def test_finalize_needs_attention_then_certified(wd, tmp_path):
    prepass(Chapter("bma", 5))
    checks(Chapter("bma", 5))
    ch = Chapter("bma", 5)
    ch.review["effort"]["started"] = "2026-09-08T00:00:00+00:00"
    ch.save()
    assert finalize(Chapter("bma", 5)) == "needs_attention"
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["status"] == "needs_attention"
    assert report["review"]["unresolved"] == [
        {"kind": "block", "ref": "p000-b002", "reason": "no verdict"}
    ]
    tree = tmp_path / "vault" / "bma" / "ch05"
    assert json.loads((tree / "manifest.json").read_text())["status"] == "needs_attention"
    assert "certified: false" in (tree / "bma-ch05-01-first.md").read_text()
    ch = Chapter("bma", 5)
    ch.review["blocks"][0]["verdict"] = "verified"
    ch.save()
    assert finalize(Chapter("bma", 5)) == "certified"
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["status"] == "certified" and report["review"]["unresolved"] == []
    manifest = json.loads((tree / "manifest.json").read_text())
    assert manifest["status"] == "certified"
    text = (tree / "bma-ch05-01-first.md").read_text()
    assert "certified: true" in text and "certified_at: '2" in text or "certified_at: 2" in text


def test_finalize_cli_exit_codes(wd):
    prepass(Chapter("bma", 5))
    checks(Chapter("bma", 5))
    r = subprocess.run(
        [sys.executable, "-m", "src.review", "start", "--book", "bma", "--chapter", "5"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "src.review", "finalize", "--book", "bma", "--chapter", "5"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 3 and "needs_attention" in r.stdout
