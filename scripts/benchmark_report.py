"""Gate-5 benchmark table from the reviewed work dirs (design §15). Counts and ids only.

  uv run python scripts/benchmark_report.py [--out metrics/gate5-benchmark-<date>.md]
                                            [--chapters bma/ch05 bma/ch06 ...]

Reads every work/<book>/ch*/qa_report.json that carries a `review` key (or only the chapters
listed), plus patches.json; never book text. The operator appends tokens (where the harness
exposed them) and the calibration rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run by path

from src.config import WORK

COLUMNS = (
    "chapter",
    "pages",
    "blocks",
    "hunks",
    "same_letters",
    "move",
    "junk",
    "duplicate",
    "folio",
    "inline_math",
    "edge_glyph",
    "edge_glyph_sup",
    "needs_eyes",
    "unresolved",
    "flagged",
    "formulas",
    "formulas_textlayer",
    "tables",
    "tables_textlayer",
    "tables_empty",
    "tierA_match",
    "tierA_mismatch",
    "rv_patches",
    "formula_error_rate",
    "table_cell_accuracy",
    "footnotes_unmatched",
    "subheadings_missing",
    "crops_opened",
    "minutes",
    "status",
)
CLASSES = (
    "same_letters",
    "move",
    "junk",
    "duplicate",
    "folio",
    "inline_math",
    "edge_glyph",
    "needs_eyes",
)


def _rate(num: int, den: int) -> str:
    return "n/a" if not den else f"{num / den:.1%}"


def _minutes(effort: dict) -> str:
    if not (effort["started"] and effort["finished"]):
        return ""
    span = datetime.fromisoformat(effort["finished"]) - datetime.fromisoformat(effort["started"])
    return f"{span.total_seconds() / 60:.0f}"


def load_patches(wd: Path) -> list[dict]:
    path = wd / "patches.json"
    return json.loads(path.read_text())["patches"] if path.exists() else []


def row(wd: Path) -> dict:
    report = json.loads((wd / "qa_report.json").read_text())
    r = report["review"]
    patches = load_patches(wd)
    counts = Counter(r["prepass"]["counts"])
    flagged = {f["id"]: f["type"] for f in report["flagged_blocks"]}
    blocks = r["blocks"]
    visual = [b for b in blocks if b["checks"]["visual"] is not None]
    formulas = [b for b in blocks if flagged[b["id"]] == "formula"]
    tables = [b for b in blocks if flagged[b["id"]] == "table"]
    rv = [p for p in patches if p["source"] == "review"]
    cells = sum((b["checks"]["rows"] or 0) * (b["checks"]["cols"] or 0) for b in tables)
    table_patches = {p["block"] for p in rv if flagged.get(p["block"]) == "table"}
    bad_cells = sum(
        len(b["checks"]["visual"]["discrepancies"]) if b["checks"]["visual"] else 1
        for b in tables
        if b["id"] in table_patches
    )
    edge_sup = sum(
        p["rule"] == "edge_glyph" and "<sup>" in p["new"]
        for p in patches
        if p["source"] == "prepass"
    )
    ef = r["effort"]
    return {
        "chapter": f"{wd.parent.name}/{wd.name}",
        "pages": report["pages"][1] - report["pages"][0] + 1,
        "blocks": report["counts"]["blocks"],
        "hunks": report["counts"]["diff_hunks"],
        **{k: counts.get(k, 0) for k in CLASSES},
        "edge_glyph_sup": edge_sup,
        "unresolved": len(r["unresolved"]),
        "flagged": len(blocks),
        "formulas": len(formulas),
        "formulas_textlayer": sum(b["checks"]["textlayer_match"] is True for b in formulas),
        "tables": len(tables),
        "tables_textlayer": sum(b["checks"]["textlayer_match"] is True for b in tables),
        "tables_empty": sum(b["checks"]["rows"] == 0 for b in tables),
        "tierA_match": sum(bool(b["checks"]["visual"]["match"]) for b in visual),
        "tierA_mismatch": sum(not b["checks"]["visual"]["match"] for b in visual),
        "rv_patches": len(rv),
        "formula_error_rate": _rate(
            sum(b["verdict"] in ("patched", "unresolved") for b in formulas), len(formulas)
        ),
        "table_cell_accuracy": _rate(cells - bad_cells, cells),
        "footnotes_unmatched": len(r["footnotes"]["unmatched"]),
        "subheadings_missing": len(r["headings"]["missing"]),
        "crops_opened": ef["crops_opened"],
        "minutes": _minutes(ef),
        "status": report["status"],
    }


def table(rows: list[dict]) -> str:
    head = "| " + " | ".join(COLUMNS) + " |"
    sep = "|" + "---|" * len(COLUMNS)
    body = ["| " + " | ".join(str(r[c]) for c in COLUMNS) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def review_ops(wd: Path) -> str:
    """`replace 5 · set_math 2` — the tier-B patches by op, for the per-book notes."""
    ops = Counter(p["op"] for p in load_patches(wd) if p["source"] == "review")
    return " · ".join(f"{op} {n}" for op, n in sorted(ops.items())) or "none"


def reviewed_dirs(work: Path, only: list[str] | None = None) -> list[Path]:
    """work/<book>/ch*/ dirs whose qa_report.json has a `review` key, restricted to `only`
    (`book/chNN` names) when given, sorted."""
    dirs = []
    for p in sorted(work.glob("*/ch*/qa_report.json")):
        name = f"{p.parent.parent.name}/{p.parent.name}"
        if only is not None and name not in only:
            continue
        if "review" in json.loads(p.read_text()):
            dirs.append(p.parent)
    return dirs


def render(rows: list[dict], dirs: list[Path], today: str) -> str:
    notes = "\n".join(
        f"- **{r['chapter']}**: review patches {review_ops(d)}. " for r, d in zip(rows, dirs)
    )
    calib = "\n".join(f"| {r['chapter']} | | | | | | |" for r in rows)
    return (
        f"# Gate 5 — benchmark pass ({today})\n\n"
        "Automatic columns from qa_report.review and patches.json; counts and block ids only. The\n"
        "operator appends tokens (where the harness exposed them) and the calibration rows.\n\n"
        f"{table(rows)}\n\n## Per-book notes\n\n{notes}\n\n## Calibration (operator)\n\n"
        "| chapter | tables checked | table misses | formulas checked | formula misses "
        "| tokens tier A | tokens tier B |\n|---|---|---|---|---|---|---|\n"
        f"{calib}\n"
    )


def main(argv: list[str] | None = None) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=Path("metrics") / f"gate5-benchmark-{today}.md")
    ap.add_argument("--chapters", nargs="+", metavar="BOOK/chNN", help="restrict to these dirs")
    args = ap.parse_args(argv)
    dirs = reviewed_dirs(WORK, args.chapters)
    if not dirs:
        print(f"benchmark_report: no reviewed chapters under {WORK}", file=sys.stderr)
        return 1
    rows = [row(d) for d in dirs]
    args.out.write_text(render(rows, dirs, today))
    print(f"benchmark_report: {len(rows)} chapters -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
