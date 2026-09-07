from pathlib import Path

import pytest

from tests.helpers import work_chapter


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
