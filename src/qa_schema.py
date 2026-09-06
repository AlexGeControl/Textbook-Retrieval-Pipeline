"""qa_report.json schema — HANDOVER §6 v1 with the enums the design amends.

flagged_blocks.type ∈ {table, formula, chart, figure, text}; reason ∈ {vlm_generated,
running_matter_suspect}. Hand-written: required keys, value types, enums, cross-field counts.
Extra keys are allowed so stage 5 can add verdicts without changing this validator.
"""

from __future__ import annotations

BLOCK_TYPES = ("table", "formula", "chart", "figure", "text")
REASONS = ("vlm_generated", "running_matter_suspect")
STATUSES = ("pending_review", "certified", "needs_attention")


class SchemaError(Exception):
    def __init__(self, path: str, msg: str):
        super().__init__(f"{path}: {msg}")
        self.path = path


def _obj(value, path: str, keys: tuple[str, ...]) -> None:
    if not isinstance(value, dict):
        raise SchemaError(path, f"expected object, got {type(value).__name__}")
    missing = [k for k in keys if k not in value]
    if missing:
        raise SchemaError(path, f"missing {', '.join(missing)}")


def _str(value, path: str) -> None:
    if not isinstance(value, str):
        raise SchemaError(path, f"expected string, got {type(value).__name__}")


def _int(value, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaError(path, f"expected non-negative int, got {value!r}")


def _enum(value, path: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise SchemaError(path, f"{value!r} not in {allowed}")


def validate(report: dict) -> None:
    _obj(
        report,
        "$",
        (
            "book",
            "chapter",
            "pages",
            "extraction",
            "counts",
            "diff_hunks",
            "flagged_blocks",
            "spot_check",
            "status",
        ),
    )
    _str(report["book"], "book")
    _str(report["chapter"], "chapter")
    pages = report["pages"]
    if not (isinstance(pages, list) and len(pages) == 2):
        raise SchemaError("pages", "expected [first_printed, last_printed]")
    for i, p in enumerate(pages):
        _int(p, f"pages[{i}]")
    if pages[0] > pages[1]:
        raise SchemaError("pages", "first > last")
    ex = report["extraction"]
    _obj(ex, "extraction", ("backend", "effort", "mineru_version", "timestamp"))
    for k in ("backend", "effort", "mineru_version", "timestamp"):
        _str(ex[k], f"extraction.{k}")
    counts = report["counts"]
    _obj(counts, "counts", ("blocks", "tables", "formulas", "figures", "diff_hunks"))
    for k in ("blocks", "tables", "formulas", "figures", "diff_hunks"):
        _int(counts[k], f"counts.{k}")
    for i, h in enumerate(report["diff_hunks"]):
        _obj(h, f"diff_hunks[{i}]", ("page", "anchor", "pdf_text", "md_text"))
        _int(h["page"], f"diff_hunks[{i}].page")
        for k in ("anchor", "pdf_text", "md_text"):
            _str(h[k], f"diff_hunks[{i}].{k}")
    for i, f in enumerate(report["flagged_blocks"]):
        _obj(f, f"flagged_blocks[{i}]", ("id", "type", "crop", "reason"))
        _str(f["id"], f"flagged_blocks[{i}].id")
        _str(f["crop"], f"flagged_blocks[{i}].crop")
        _enum(f["type"], f"flagged_blocks[{i}].type", BLOCK_TYPES)
        _enum(f["reason"], f"flagged_blocks[{i}].reason", REASONS)
    for i, s in enumerate(report["spot_check"]):
        _obj(s, f"spot_check[{i}]", ("id", "crop"))
        _str(s["id"], f"spot_check[{i}].id")
        _str(s["crop"], f"spot_check[{i}].crop")
    _enum(report["status"], "status", STATUSES)
    if counts["diff_hunks"] != len(report["diff_hunks"]):
        raise SchemaError(
            "counts.diff_hunks",
            f"{counts['diff_hunks']} != len(diff_hunks) {len(report['diff_hunks'])}",
        )
