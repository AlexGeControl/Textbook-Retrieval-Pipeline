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


# --- stage 5: the `review` key (design §11) -----------------------------------------------
HUNK_VERDICTS = (
    "accepted_pdf",
    "accepted_md",
    "move",
    "dropped",
    "verified",
    "patched",
    "unresolved",
)
BLOCK_VERDICTS = ("verified", "patched", "dropped", "unresolved")
SPOT_VERDICTS = ("ok", "patched", "unresolved")
HEADING_VERDICTS = ("found_as", "not_a_heading")
FOOTNOTE_VERDICTS = ("accepted", "patched")
CHECK_KEYS = (
    "latex_parses",
    "rectangular",
    "rows",
    "cols",
    "textlayer_match",
    "textlayer_diff",
    "visual",
)
VISUAL_KEYS = ("model", "match", "rows", "cols", "discrepancies")
REVIEW_KEYS = (
    "prepass",
    "hunks",
    "blocks",
    "spot_check",
    "headings",
    "footnotes",
    "effort",
    "unresolved",
)


def _list(value, path: str) -> None:
    if not isinstance(value, list):
        raise SchemaError(path, f"expected list, got {type(value).__name__}")


def _pair(value, path: str) -> None:
    _list(value, path)
    if len(value) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in value):
        raise SchemaError(path, "expected [found, expected]")


def _ids(entries, path: str) -> list:
    _list(entries, path)
    return [e.get("id") if isinstance(e, dict) else None for e in entries]


def validate_review(report: dict) -> None:
    """The stage-5 `review` key. Call after validate(); raises with the path of the violation."""
    r = report.get("review")
    _obj(r, "review", REVIEW_KEYS)
    _obj(r["prepass"], "review.prepass", ("timestamp", "counts"))
    _str(r["prepass"]["timestamp"], "review.prepass.timestamp")
    _list(r["hunks"], "review.hunks")
    if len(r["hunks"]) != len(report["diff_hunks"]):
        raise SchemaError(
            "review.hunks", f"{len(r['hunks'])} entries for {len(report['diff_hunks'])} hunks"
        )
    for i, h in enumerate(r["hunks"]):
        p = f"review.hunks[{i}]"
        _obj(h, p, ("verdict", "rule", "patches", "note"))
        _enum(h["verdict"], f"{p}.verdict", HUNK_VERDICTS)
        _list(h["patches"], f"{p}.patches")
    if _ids(r["blocks"], "review.blocks") != [f["id"] for f in report["flagged_blocks"]]:
        raise SchemaError("review.blocks", "ids must equal flagged_blocks ids, same order")
    for i, b in enumerate(r["blocks"]):
        p = f"review.blocks[{i}]"
        _obj(b, p, ("id", "verdict", "checks", "patches", "note"))
        _enum(b["verdict"], f"{p}.verdict", BLOCK_VERDICTS)
        _obj(b["checks"], f"{p}.checks", CHECK_KEYS)
        v = b["checks"]["visual"]
        if v is not None:
            _obj(v, f"{p}.checks.visual", VISUAL_KEYS)
            if not isinstance(v["match"], bool):
                raise SchemaError(f"{p}.checks.visual.match", "expected bool")
            _list(v["discrepancies"], f"{p}.checks.visual.discrepancies")
        _list(b["patches"], f"{p}.patches")
    if _ids(r["spot_check"], "review.spot_check") != [s["id"] for s in report["spot_check"]]:
        raise SchemaError("review.spot_check", "ids must equal spot_check ids, same order")
    for i, s in enumerate(r["spot_check"]):
        _obj(s, f"review.spot_check[{i}]", ("id", "verdict", "note"))
        _enum(s["verdict"], f"review.spot_check[{i}].verdict", SPOT_VERDICTS)
    hd = r["headings"]
    _obj(hd, "review.headings", ("sections", "subheadings", "missing"))
    _pair(hd["sections"], "review.headings.sections")
    _pair(hd["subheadings"], "review.headings.subheadings")
    _list(hd["missing"], "review.headings.missing")
    for i, m in enumerate(hd["missing"]):
        p = f"review.headings.missing[{i}]"
        _obj(m, p, ("title", "page", "kind", "verdict", "block", "note"))
        _enum(m["kind"], f"{p}.kind", ("section", "subheading"))
        if m["verdict"] is not None:
            _enum(m["verdict"], f"{p}.verdict", HEADING_VERDICTS)
    fn = r["footnotes"]
    _obj(fn, "review.footnotes", ("definitions", "references", "unmatched", "dangling"))
    _list(fn["unmatched"], "review.footnotes.unmatched")
    for i, u in enumerate(fn["unmatched"]):
        p = f"review.footnotes.unmatched[{i}]"
        _obj(u, p, ("id", "verdict", "note"))
        if u["verdict"] is not None:
            _enum(u["verdict"], f"{p}.verdict", FOOTNOTE_VERDICTS)
    _list(fn["dangling"], "review.footnotes.dangling")
    ef = r["effort"]
    _obj(ef, "review.effort", ("started", "finished", "crops_opened", "patches", "notes"))
    _int(ef["crops_opened"], "review.effort.crops_opened")
    _int(ef["patches"], "review.effort.patches")
    _list(r["unresolved"], "review.unresolved")
    for i, u in enumerate(r["unresolved"]):
        _obj(u, f"review.unresolved[{i}]", ("kind", "ref", "reason"))
