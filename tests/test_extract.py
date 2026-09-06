import json
from pathlib import Path

import pytest

from src.extract import (
    ExtractError,
    build_command,
    build_env,
    check_outputs,
    hybrid_auto_dir,
    mineru_config_path,
    preflight,
)


def test_build_command_maps_routing_flags(tmp_path):
    cmd = build_command(
        tmp_path / "chapter.pdf", tmp_path, "http://h:30000", {"inline_formula": False}
    )
    assert cmd == [
        "mineru",
        "-p",
        str(tmp_path / "chapter.pdf"),
        "-o",
        str(tmp_path),
        "-b",
        "hybrid-http-client",
        "-u",
        "http://h:30000",
        "--effort",
        "high",
        "-f",
        "false",
    ]


def test_build_command_without_routing_adds_no_flags(tmp_path):
    cmd = build_command(tmp_path / "chapter.pdf", tmp_path, "http://h:30000", {})
    assert cmd[-2:] == ["--effort", "high"]
    cmd = build_command(
        tmp_path / "c.pdf", tmp_path, "u", {"table": True, "lang": "ch", "image_analysis": False}
    )
    assert cmd[-6:] == ["-t", "true", "--image-analysis", "false", "-l", "ch"]


def test_build_env_pins_gpu1_and_local_models():
    env = build_env({"PATH": "/bin", "MINERU_DEVICE_MODE": "cuda"})
    assert env["PATH"] == "/bin"
    assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert env["MINERU_DEVICE_MODE"] == "cuda:1"
    assert env["MINERU_MODEL_SOURCE"] == "local"


def test_hybrid_auto_dir_follows_mineru_layout(tmp_path):
    assert hybrid_auto_dir(tmp_path) == tmp_path / "chapter" / "hybrid_auto"
    assert hybrid_auto_dir(tmp_path, "table") == tmp_path / "table" / "hybrid_auto"


def test_check_outputs_accepts_cached_fixture(table_cache):
    check_outputs(table_cache, 2, stem="table")


def test_check_outputs_reports_missing_files(tmp_path):
    with pytest.raises(ExtractError, match="chapter_middle.json"):
        check_outputs(tmp_path, 1)


def test_check_outputs_rejects_page_mismatch(table_cache):
    with pytest.raises(ExtractError, match="2 pages, chapter.pdf has 3"):
        check_outputs(table_cache, 3, stem="table")


def test_preflight_requires_url(tmp_path):
    with pytest.raises(ExtractError, match="MINERU_SERVER_URL"):
        preflight(None, tmp_path / "mineru.json", probe=lambda url: True)


def test_preflight_requires_a_live_server(tmp_path):
    with pytest.raises(ExtractError, match="health"):
        preflight("http://h:1", tmp_path / "mineru.json", probe=lambda url: False)


def test_preflight_requires_pinned_models_dir(tmp_path):
    cfg = tmp_path / "mineru.json"
    cfg.write_text(json.dumps({"models-dir": {"pipeline": str(tmp_path / "nope")}}))
    with pytest.raises(ExtractError, match="models-dir.pipeline"):
        preflight("http://h:1", cfg, probe=lambda url: True)
    with pytest.raises(ExtractError, match="missing"):
        preflight("http://h:1", tmp_path / "absent.json", probe=lambda url: True)


def test_preflight_passes_when_everything_is_there(tmp_path):
    (tmp_path / "models").mkdir()
    cfg = tmp_path / "mineru.json"
    cfg.write_text(json.dumps({"models-dir": {"pipeline": str(tmp_path / "models")}}))
    seen = []
    preflight("http://h:30000/", cfg, probe=lambda url: seen.append(url) or True)
    assert seen == ["http://h:30000/health"]


def test_mineru_config_path(monkeypatch):
    monkeypatch.delenv("MINERU_TOOLS_CONFIG_JSON", raising=False)
    assert mineru_config_path() == Path.home() / "mineru.json"
    monkeypatch.setenv("MINERU_TOOLS_CONFIG_JSON", "/abs/x.json")
    assert mineru_config_path() == Path("/abs/x.json")


def _write_hybrid_auto(root, middle_pages, content_pages, stem="chapter"):
    """Minimal MinerU-shaped output: _middle.json with `middle_pages` pdf_info entries and a
    content_list whose blocks span `content_pages` pages (a trailing blank page has no block)."""
    d = root / stem / "hybrid_auto"
    (d / "images").mkdir(parents=True)
    (d / f"{stem}.md").write_text("")
    cl = [
        {"type": "text", "text": "x", "bbox": [0, 0, 1, 1], "page_idx": i}
        for i in range(content_pages)
    ]
    (d / f"{stem}_content_list.json").write_text(json.dumps(cl))
    (d / f"{stem}_content_list_v2.json").write_text(json.dumps([[b] for b in cl]))
    (d / f"{stem}_middle.json").write_text(
        json.dumps({"pdf_info": [{"page_idx": i} for i in range(middle_pages)]})
    )
    return d


def test_check_outputs_accepts_a_blank_trailing_page(tmp_path):
    # strat ch05 p33 (2026-09-06): mineru saw 34 pages, the last one empty -> no content_list block
    d = _write_hybrid_auto(tmp_path, middle_pages=34, content_pages=33)
    check_outputs(d, 34)


def test_check_outputs_page_count_comes_from_middle_json(tmp_path):
    d = _write_hybrid_auto(tmp_path, middle_pages=33, content_pages=33)
    with pytest.raises(ExtractError, match="33 pages.*chapter.pdf has 34"):
        check_outputs(d, 34)
