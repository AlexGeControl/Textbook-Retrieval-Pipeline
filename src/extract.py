"""Stage 2 — mineru hybrid-http-client wrapper (design §5).

Runs mineru on work/<book>/<chNN>/chapter.pdf and enforces the MinerU-native output contract
under <out>/chapter/hybrid_auto/. Never reshapes mineru's outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pymupdf

from src.config import ConfigError, book_cfg, chapter_number, work_dir

STEM = "chapter"
REQUIRED = (
    "{stem}.md",
    "{stem}_content_list.json",
    "{stem}_content_list_v2.json",
    "{stem}_middle.json",
    "images",
)
ROUTING_FLAGS = {
    "inline_formula": "-f",
    "table": "-t",
    "image_analysis": "--image-analysis",
    "lang": "-l",
}
# Client inference on the A6000 (CUDA index 1 in PCI order) and pinned local model snapshots.
CLIENT_ENV = {
    "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
    "MINERU_DEVICE_MODE": "cuda:1",
    "MINERU_MODEL_SOURCE": "local",
}


class ExtractError(Exception):
    pass


def hybrid_auto_dir(out_dir: Path, stem: str = STEM) -> Path:
    return Path(out_dir) / stem / "hybrid_auto"


def build_command(pdf: Path, out_dir: Path, url: str, routing: dict) -> list[str]:
    cmd = [
        "mineru",
        "-p",
        str(pdf),
        "-o",
        str(out_dir),
        "-b",
        "hybrid-http-client",
        "-u",
        url,
        "--effort",
        "high",
    ]
    for key, flag in ROUTING_FLAGS.items():
        if key in routing:
            value = routing[key]
            cmd += [flag, str(value).lower() if isinstance(value, bool) else str(value)]
    return cmd


def build_env(base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    env.update(CLIENT_ENV)
    return env


def mineru_config_path() -> Path:
    """Same resolution as mineru.utils.config_reader: absolute path, else ~/<name>."""
    name = os.environ.get("MINERU_TOOLS_CONFIG_JSON", "mineru.json")
    return Path(name) if os.path.isabs(name) else Path.home() / name


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return 200 <= resp.status < 300
    except (OSError, ValueError):  # URLError is an OSError; ValueError = malformed URL
        return False


def preflight(url: str | None, config_json: Path, probe: Callable[[str], bool] = _http_ok) -> None:
    if not url:
        raise ExtractError("MINERU_SERVER_URL is not set (e.g. http://127.0.0.1:30000)")
    health = f"{url.rstrip('/')}/health"
    if not probe(health):
        raise ExtractError(f"MinerU server not answering at {health} — is `make serve` running?")
    if not config_json.exists():
        raise ExtractError(
            f"{config_json} missing — MINERU_MODEL_SOURCE=local needs models-dir (CLAUDE.md)"
        )
    models = (json.loads(config_json.read_text()).get("models-dir") or {}).get("pipeline")
    if not models or not Path(models).is_dir():
        raise ExtractError(
            f"{config_json}: models-dir.pipeline {models!r} is not a directory — "
            "run `make client-models`"
        )


def check_outputs(hybrid_auto: Path, expected_pages: int, stem: str = STEM) -> None:
    hybrid_auto = Path(hybrid_auto)
    missing = [
        n.format(stem=stem) for n in REQUIRED if not (hybrid_auto / n.format(stem=stem)).exists()
    ]
    if missing:
        raise ExtractError(f"{hybrid_auto}: missing {', '.join(missing)}")
    # Page count comes from _middle.json: mineru writes one pdf_info entry per page, blank or not.
    # content_list has no block for a blank page (strat ch05 p33), so its max page_idx undercounts.
    middle = json.loads((hybrid_auto / f"{stem}_middle.json").read_text())
    pages = len(middle.get("pdf_info") or [])
    if pages != expected_pages:
        raise ExtractError(
            f"{hybrid_auto}: {stem}_middle.json has {pages} pages, chapter.pdf has {expected_pages}"
        )
    content_list = json.loads((hybrid_auto / f"{stem}_content_list.json").read_text())
    beyond = [b["page_idx"] for b in content_list if b["page_idx"] >= pages]
    if beyond:
        raise ExtractError(
            f"{hybrid_auto}: content_list references page {max(beyond)} beyond {pages} pages"
        )


def run(
    pdf: Path, out_dir: Path, url: str | None, routing: dict, force: bool = False, stem: str = STEM
) -> Path:
    target = hybrid_auto_dir(out_dir, stem)
    pages = pymupdf.open(pdf).page_count
    if not force and (target / f"{stem}_content_list.json").exists():
        check_outputs(target, pages, stem)
        print(f"extract: reusing {target} (--force to re-run)", file=sys.stderr)
        return target
    preflight(url, mineru_config_path())
    cmd = build_command(pdf, out_dir, url, routing)
    print("+ " + " ".join(cmd), file=sys.stderr)
    t0 = time.monotonic()
    proc = subprocess.run(cmd, env=build_env(), check=False)
    if proc.returncode != 0:
        raise ExtractError(f"mineru exited {proc.returncode} for {pdf}")
    check_outputs(target, pages, stem)
    print(f"extract: {pages} pages in {time.monotonic() - t0:.0f} s -> {target}", file=sys.stderr)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Stage 2: run mineru hybrid-http-client on a split chapter"
    )
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True, help="chapter number (5) or slug (ch05)")
    ap.add_argument("--force", action="store_true", help="re-run even if outputs exist")
    args = ap.parse_args(argv)
    try:
        cfg = book_cfg(args.book)
        wd = work_dir(args.book, chapter_number(args.chapter))
        pdf = wd / "chapter.pdf"
        if not pdf.exists():
            raise ExtractError(
                f"{pdf} missing — run `uv run python -m src.split --book {args.book} "
                f"--chapter {args.chapter}` first"
            )
        run(
            pdf, wd, os.environ.get("MINERU_SERVER_URL"), cfg.get("routing") or {}, force=args.force
        )
    except (ExtractError, ConfigError) as e:
        print(f"extract: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
