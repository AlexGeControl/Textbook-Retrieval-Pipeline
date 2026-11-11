from pathlib import Path

import pytest

from tests.helpers import make_work_dir, work_chapter, work_chapter_sandbox


def test_work_chapter_skips_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("tests.helpers.WORK", tmp_path)
    with pytest.raises(pytest.skip.Exception):
        work_chapter("bma", "ch99")


def test_work_chapter_returns_dir_when_report_exists(monkeypatch, tmp_path):
    monkeypatch.setattr("tests.helpers.WORK", tmp_path)
    d = tmp_path / "bma" / "ch05"
    d.mkdir(parents=True)
    (d / "qa_report.json").write_text("{}")
    assert work_chapter("bma", "ch05") == Path(d)


def test_work_chapter_sandbox_never_touches_the_real_dir(monkeypatch, tmp_path):
    real_root = tmp_path / "real"
    real = make_work_dir(real_root, monkeypatch, pages=[[]], pdf_lines=[])
    before = (real / "qa_report.json").read_bytes()
    sandbox = work_chapter_sandbox("bma", "ch05", tmp_path / "box", monkeypatch)
    import src.config

    assert src.config.WORK == tmp_path / "box" and sandbox == tmp_path / "box" / "bma" / "ch05"
    assert (sandbox / "chapter.pdf").is_symlink() and (sandbox / "chapter").is_symlink()
    assert not (sandbox / "qa_report.json").is_symlink()  # a copy: writes stay in the sandbox
    (sandbox / "qa_report.json").write_text("{}")
    assert (real / "qa_report.json").read_bytes() == before
