import json
import subprocess
import sys

import pytest

from src.qa_schema import SchemaError, validate_review
from src.review import Chapter, ReviewError, new_review
from tests.helpers import make_work_dir

PARA = {
    "type": "paragraph",
    "bbox": [80, 80, 600, 120],
    "content": {"paragraph_content": [{"type": "text", "content": "the capi tal budget"}]},
}
EQ = {
    "type": "equation_interline",
    "bbox": [80, 200, 600, 260],
    "content": {"math_content": "x^{2}", "image_source": {"path": "images/eq.jpg"}},
}
HUNK = {
    "page": 119,
    "anchor": "p000-b000",
    "pdf_text": "the capital budget",
    "md_text": "the capi tal budget",
}
FLAG = {"id": "p000-b001", "type": "formula", "crop": "images/eq.jpg", "reason": "vlm_generated"}
SPOT = {"id": "p000-b000", "crop": "crops/p000-b000.png"}


@pytest.fixture
def wd(tmp_path, monkeypatch):
    return make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[[PARA, EQ]],
        hunks=[HUNK],
        flagged=[FLAG],
        spot=[SPOT],
        pdf_lines=["the capital budget"],
    )


def test_new_review_validates_and_mirrors_the_report(wd):
    report = json.loads((wd / "qa_report.json").read_text())
    report["review"] = new_review(report)
    validate_review(report)
    assert [h["verdict"] for h in report["review"]["hunks"]] == ["unresolved"]
    assert report["review"]["blocks"][0]["id"] == "p000-b001"
    assert set(report["review"]["blocks"][0]["checks"]) == {
        "latex_parses",
        "rectangular",
        "rows",
        "cols",
        "textlayer_match",
        "textlayer_diff",
        "visual",
    }


@pytest.mark.parametrize(
    "path, mutate",
    [
        ("review.hunks", lambda r: r["hunks"].append(r["hunks"][0])),
        ("review.hunks[0].verdict", lambda r: r["hunks"][0].__setitem__("verdict", "yes")),
        ("review.blocks", lambda r: r["blocks"][0].__setitem__("id", "p999-b999")),
        (
            "review.blocks[0].checks.visual.match",
            lambda r: r["blocks"][0]["checks"].__setitem__(
                "visual",
                {"model": "sonnet", "match": "yes", "rows": 1, "cols": 1, "discrepancies": []},
            ),
        ),
        (
            "review.headings.missing[0].kind",
            lambda r: r["headings"]["missing"].append(
                {
                    "title": "x",
                    "page": 1,
                    "kind": "para",
                    "verdict": None,
                    "block": None,
                    "note": "",
                }
            ),
        ),
        ("review.footnotes", lambda r: r["footnotes"].pop("dangling")),
    ],
)
def test_validate_review_names_the_first_violation(wd, path, mutate):
    report = json.loads((wd / "qa_report.json").read_text())
    report["review"] = new_review(report)
    mutate(report["review"])
    with pytest.raises(SchemaError) as e:
        validate_review(report)
    assert e.value.path == path


def test_chapter_loads_and_save_validates(wd):
    ch = Chapter("bma", 5)
    assert ch.by_id["p000-b000"].text() == "the capi tal budget"
    ch.review["effort"]["started"] = "2026-09-08T00:00:00+00:00"
    ch.save()
    assert json.loads((wd / "qa_report.json").read_text())["review"]["effort"]["started"]
    ch.review["hunks"][0]["verdict"] = "bogus"
    with pytest.raises(SchemaError):
        ch.save()


def test_crop_path_resolves_images_and_crops(wd):
    ch = Chapter("bma", 5)
    assert ch.crop_path("p000-b001") == ch.hybrid_auto / "images/eq.jpg"
    assert ch.crop_path("p000-b000") == wd / "crops/p000-b000.png"
    with pytest.raises(ReviewError):
        ch.crop_path("p000-b099")


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.review", *args, "--book", "bma", "--chapter", "5"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_hunk_block_patch_round_trip(wd):
    assert _cli("start").returncode == 0
    r = _cli(
        "patch",
        "--block",
        "p000-b000",
        "--op",
        "replace",
        "--old",
        "capi tal",
        "--new",
        "capital",
        "--rule",
        "manual",
    )
    assert r.returncode == 0, r.stderr
    pid = r.stdout.strip()
    assert pid == "rv-0001"
    assert (
        _cli(
            "hunk", "--index", "0", "--verdict", "patched", "--rule", "manual", "--patch", pid
        ).returncode
        == 0
    )
    r = _cli(
        "block",
        "--id",
        "p000-b001",
        "--verdict",
        "verified",
        "--visual",
        json.dumps(
            {"model": "sonnet", "match": True, "rows": None, "cols": None, "discrepancies": []}
        ),
    )
    assert r.returncode == 0, r.stderr
    assert _cli("spot", "--id", "p000-b000", "--verdict", "ok").returncode == 0
    report = json.loads((wd / "qa_report.json").read_text())
    assert report["review"]["hunks"][0] == {
        "verdict": "patched",
        "rule": "manual",
        "patches": ["rv-0001"],
        "note": "",
    }
    assert report["review"]["blocks"][0]["checks"]["visual"]["match"] is True
    assert report["review"]["effort"]["patches"] == 1
    assert report["status"] == "pending_review"  # only finalize sets status


def test_cli_rejects_bad_patch_and_unknown_patch_id(wd):
    r = _cli("patch", "--block", "p000-b000", "--op", "replace", "--old", "zzz", "--new", "y")
    assert r.returncode == 1 and "occurs 0 times" in r.stderr
    assert (
        not (wd / "patches.json").exists()
        or json.loads((wd / "patches.json").read_text())["patches"] == []
    )
    r = _cli("hunk", "--index", "0", "--verdict", "patched", "--patch", "rv-0009")
    assert r.returncode == 1 and "rv-0009" in r.stderr


def test_cli_crop_prints_path_and_counts(wd):
    r = _cli("crop", "--id", "p000-b001")
    assert r.returncode == 0 and r.stdout.strip().endswith("images/eq.jpg")
    assert json.loads((wd / "qa_report.json").read_text())["review"]["effort"]["crops_opened"] == 1
