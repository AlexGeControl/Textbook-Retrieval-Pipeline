# `algorithm` Block Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (CLAUDE.md
> deviation: batches with operator checkpoints, never subagent-driven-development). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `make chapter BOOK=ops CH=16` runs stages 3–4 to completion on a chapter whose
content_list_v2 carries a mineru `algorithm` block, and the block flows through stage 5 as
VLM-transcribed running text: aligned, flagged, patchable, rendered.

**Architecture:** `src/blocks.py` learns the v2 `algorithm` shape (`algorithm_caption`,
`algorithm_content`, optional `algorithm_footnote`; no crop) and classifies it in a new set
`VLM_TRANSCRIBED`, a subset of `TEXT_BEARING` that is also VLM-generated but never masked. The
guardrail aligns caption then body against the text layer; stage 4 flags the block as
`text`/`vlm_generated` with a crop rendered from `chapter.pdf` and keeps it out of the spot-check
sample; patches and the pre-pass treat it as a paragraph; the renderer emits a caption-titled
callout. `MASKED`, `CAPTIONED` and the qa_report schema do not change.

**Tech Stack:** Python via `uv`, PyMuPDF, pytest, ruff. No GPU, no MinerU server: every new test
is synthetic (no fixture page carries an `algorithm` block).

**Spec:** the decision record below (§Spec). It amends `docs/plans/2026-09-06-stages-1-4-design.md`
§1 and §6 and `docs/plans/2026-09-07-stage5-design.md` §7, §9, §12; Task 7 writes the amendments.

## Global Constraints

- Branch `stage-5` in the main checkout. No worktrees. Commit per task; never `git push` (the
  operator pushes). `CLAUDE.md`, `Makefile` and the stage-5 plan carry the operator's uncommitted
  Task 13 edits: never `git add` them wholesale (Task 7 stages the CLAUDE.md hunk alone).
- `uv run …` for every command. `uv run pytest` and `uv run ruff check . && uv run ruff format
  --check .` pass before every commit; `ruff format --check` covers Python blocks in Markdown.
- Text layer wins. Review patches, never regenerates. Fail loudly. Do not pre-build fallbacks:
  `code` and `index` keep raising `BlockError` until a chapter produces one.
- Stage-2 outputs are read only. `qa_report.json` keeps the HANDOVER §6 schema
  (`flagged_blocks.type ∈ {table, formula, chart, figure, text}`, reasons unchanged).
- Book text never enters git: tests use invented notation lines, never the ops box's text;
  evidence is counts and block ids.

## Spec — decision record (2026-09-14)

**Symptom.** `make chapter BOOK=ops CH=16` → `BlockError: content_list_v2 p54 block 1:
unsupported type 'algorithm'` from stage 3, after a complete extraction.

**Root cause.** The layout model labelled the chapter's shaded "Summary of Key Notation and
Equations" box (`TABLE 16.6`) `algorithm`; mineru's hybrid backend maps that label to a code
block, switches the sub-type to `algorithm` because the body carries inline formulas, and keeps
the VLM transcription as the body instead of the text layer (every span shares the block bbox;
the text layer has a true minus where the VLM wrote a hyphen). v2 emits `{"type": "algorithm",
"content": {"algorithm_caption": [spans], "algorithm_content": [spans]}}` with no
`image_source`. `blocks.py` rejects it by the 2026-09-06 design decision, taken on a survey with
zero such blocks. Today: 1 block in ~11,000 across 16 extracted chapters and 4 fixtures; the ops
book prints this box at the end of most chapters.

**Decision.** `algorithm` is *VLM-transcribed running text*:

| aspect | rule |
|---|---|
| type classes | `TEXT_BEARING += algorithm`; new `VLM_TRANSCRIBED = {algorithm}`; `SCHEMA_TYPE[algorithm] = text`; `MASKED`, `CAPTIONED`, `FIGURES`, `RUNNING_MATTER` unchanged |
| Block fields | `spans` = `algorithm_content`; `captions` = `algorithm_caption` NEWLINE `algorithm_footnote`; `crop` empty |
| `is_vlm_generated()` | true (body written by the VLM) |
| guardrail | md text = caption spans then body spans, inline math flattened; not masked |
| stage 4 | flagged `{type: text, reason: vlm_generated, crop: crops/<id>.png}` (rendered, mineru gives none); excluded from spot-check candidates so flagged and spot sets stay disjoint |
| patches / pre-pass | as a paragraph: `replace`, `set_inline_math` on the body; hunks anchored to it classify normally (no "masking gap") |
| sections | `BODY_TYPES += algorithm` so footnote references inside the box are scanned |
| render | `> [!abstract] <caption>` callout, one quoted line per printed row, inline math `$…$`, footnote line last; empty body and caption → nothing |
| review skill | tier A uses `rubric-text.md`; the block's guardrail hunks are the spotlights; never `set_*` on it |
| out of scope | `code`, `index`; a fixture page; a mechanical text-layer check for the block (the guardrail already diffs it) |

**Alternatives rejected.** Retyping to `paragraph` at load hides what mineru did and loses the
caption pairing. Treating it as a masked VLM body like a table violates "text layer wins" on a
box whose text layer is complete.

---

### Task 1: Block model — `algorithm` loads as VLM-transcribed text

**Files:**
- Modify: `src/blocks.py` (type-class sets, `Block.is_vlm_generated`, `_block`)
- Test: `tests/test_blocks.py`

**Interfaces:**
- Produces: `VLM_TRANSCRIBED: frozenset[str]`; `"algorithm" in TEXT_BEARING`;
  `SCHEMA_TYPE["algorithm"] == "text"`; `Block(type="algorithm", spans=…, captions=…)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_blocks.py` add `VLM_TRANSCRIBED` to the `from src.blocks import (…)` list, add
the constant and test below after `test_image_is_vlm_generated_only_when_it_carries_content`,
and replace `test_type_classes_partition_the_v2_vocabulary` with the version shown.

```python
ALGORITHM = {
    "type": "algorithm",
    "content": {
        "algorithm_caption": [{"type": "text", "content": "TABLE 9.9 Summary of Key Notation"}],
        "algorithm_content": [
            {"type": "equation_inline", "content": "q ="},
            {"type": "text", "content": " Order quantity  \n "},
            {"type": "equation_inline", "content": "h ="},
            {"type": "text", "content": " Holding cost per unit"},
        ],
    },
    "bbox": [117, 176, 854, 518],
}


def test_algorithm_is_vlm_transcribed_text_with_a_caption(tmp_path):
    (b,) = load_blocks(_v2(tmp_path, [[ALGORITHM]]))
    assert b.type == "algorithm" and b.type in TEXT_BEARING and b.type in VLM_TRANSCRIBED
    assert b.text() == " Order quantity  \n  Holding cost per unit"
    assert b.inline_math() == ("q =", "h =")
    assert b.caption_text() == "TABLE 9.9 Summary of Key Notation"
    assert b.is_vlm_generated() and SCHEMA_TYPE["algorithm"] == "text"
    assert b.crop == "" and b.type not in MASKED and b.type not in CAPTIONED


def test_type_classes_partition_the_v2_vocabulary():
    assert not TEXT_BEARING & (VLM_GENERATED | FIGURES)
    assert RUNNING_MATTER < TEXT_BEARING
    assert VLM_TRANSCRIBED < TEXT_BEARING and not VLM_TRANSCRIBED & MASKED
    assert MASKED == VLM_GENERATED | {"image"}
    assert frozenset(SCHEMA_TYPE) == MASKED | VLM_TRANSCRIBED
    assert CAPTIONED == FIGURES | {"table"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_blocks.py -q`
Expected: collection error `ImportError: cannot import name 'VLM_TRANSCRIBED'`.

- [ ] **Step 3: Implement**

In `src/blocks.py`:

```python
# Text-layer blocks. Every one is aligned against the PDF text layer; nothing is dropped by type,
# because on reflowed e-books (acct, ops) mineru labels body text page_header / page_footer.
TEXT_BEARING = frozenset(
    {
        "paragraph",
        "title",
        "list",
        "page_footnote",
        "page_aside_text",
        "page_header",
        "page_footer",
        "page_number",
        "algorithm",
    }
)
# Running heads, feet and folios: aligned like any text; stage 4 flags the ones whose text is
# not running matter (a heading or sentence the layout model mislabeled) so stage 5 keeps them.
RUNNING_MATTER = frozenset({"page_header", "page_footer", "page_number"})
# Text-bearing bodies the VLM wrote: mineru's hybrid backend keeps the VLM transcription of a
# `code`/`algorithm` body instead of the text layer (ops ch16 p054-b001: a boxed notation summary
# the layout model read as pseudo-code). Aligned by the guardrail like any text, flagged for
# review as `text`, never masked. `code` and `index` still fail loudly until a chapter has one.
VLM_TRANSCRIBED = frozenset({"algorithm"})
```

Add `"algorithm": "text",` to `SCHEMA_TYPE`. Change the `captions` field comment to
`# *_caption NEWLINE *_footnote spans of a CAPTIONED or algorithm block`. Replace
`is_vlm_generated`:

```python
    def is_vlm_generated(self) -> bool:
        if self.type in VLM_GENERATED or self.type in VLM_TRANSCRIBED:
            return True
        return self.type == "image" and bool(self.content.strip())
```

In `_block`, after the `RUNNING_MATTER`/footnote/aside branch and before `crop = …`:

```python
    if t == "algorithm":
        return Block(
            **common,
            spans=_spans(c.get("algorithm_content", [])),
            captions=_joined([c.get("algorithm_caption", []), c.get("algorithm_footnote", [])]),
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_blocks.py -q`
Expected: all pass, including `test_unsupported_type_fails_loudly` (still `code`).

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/blocks.py tests/test_blocks.py
git commit -m "blocks: load mineru's algorithm block as VLM-transcribed text with a caption"
```

---

### Task 2: Guardrail — caption then body aligned, never masked

**Files:**
- Modify: `src/guardrail.py:83-96` (`block_text`)
- Test: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: `Block` with both `captions` and `spans` (Task 1).
- Produces: `block_text(algorithm) == "<caption> <flattened body>"`; `block_masks` unchanged.

- [ ] **Step 1: Write the failing test**

Ensure `block_masks` is in the `from src.guardrail import (…)` list, then add:

```python
def test_algorithm_block_aligns_its_caption_and_vlm_body_and_is_not_masked():
    alg = Block(
        id="p000-b004",
        index=4,
        type="algorithm",
        page_idx=0,
        bbox=(100, 100, 900, 500),
        spans=(
            Span("equation_inline", "q ="),
            Span("text", " Order quantity  \n "),
            Span("equation_inline", "h ="),
            Span("text", " Holding cost"),
        ),
        captions=(Span("text", "TABLE 9.9 Key notation"),),
    )
    assert block_text(alg) == "TABLE 9.9 Key notation q=  Order quantity  \n  h=  Holding cost"
    toks = [t.text for t in block_tokens(alg)]
    assert toks == "TABLE 9.9 Key notation q= Order quantity h= Holding cost".split()
    assert block_masks([alg], pymupdf.Rect(0, 0, 1000, 1000)) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_guardrail.py -q -k algorithm`
Expected: FAIL — `block_text` returns the body only (`"q=  Order quantity …"`).

- [ ] **Step 3: Implement**

```python
def block_text(block: Block) -> str:
    """md-side text: body spans of a text-bearing block, caption spans of a captioned one.

    An `algorithm` block carries both: its text-layer caption precedes its VLM-written body, in
    reading order. Inline-math spans are flattened to their glyphs. Spans are joined with a
    space because mineru puts none between a formula and the text that follows it.
    """
    if block.type in TEXT_BEARING:
        spans = (*block.captions, *block.spans)
    elif block.type in CAPTIONED:
        spans = block.captions
    else:
        return ""
    return " ".join(
        flatten_latex(s.content) if s.type == "equation_inline" else s.content for s in spans
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_guardrail.py -q`
Expected: PASS (other text-bearing blocks have empty `captions`, so nothing else changes).

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/guardrail.py tests/test_guardrail.py
git commit -m "guardrail: align an algorithm block's caption and body; never mask it"
```

---

### Task 3: Stage 4 — flagged as `text`/`vlm_generated`, out of the spot sample

**Files:**
- Modify: `src/qa_report.py:17-34` (import, `BODY_TEXT`)
- Test: `tests/test_qa_report.py`

**Interfaces:**
- Consumes: `VLM_TRANSCRIBED`, `SCHEMA_TYPE["algorithm"]`, `Block.is_vlm_generated()` (Task 1).
- Produces: a flagged entry `{id, type: "text", crop: "crops/<id>.png", reason: "vlm_generated"}`.

- [ ] **Step 1: Write the failing test**

```python
def test_algorithm_is_flagged_as_vlm_text_with_a_rendered_crop_and_never_spot_checked():
    alg = Block(
        id="p000-b000",
        index=0,
        type="algorithm",
        page_idx=0,
        bbox=(100, 100, 900, 500),
        spans=(Span("equation_inline", "q ="), Span("text", " Order quantity")),
        captions=(Span("text", "TABLE 9.9 Key notation"),),
    )
    paras = [_matter(i, "paragraph", f"body text {i}") for i in range(1, 5)]
    r = build(META, GUARD, [alg, *paras], MIDDLE, 1_788_000_000.0, lambda b: f"crops/{b.id}.png")
    assert r["flagged_blocks"] == [
        {
            "id": "p000-b000",
            "type": "text",
            "crop": "crops/p000-b000.png",
            "reason": "vlm_generated",
        },
    ]
    spot = {s["id"] for s in r["spot_check"]}
    assert len(spot) == 3 and "p000-b000" not in spot
    assert r["counts"] == {"blocks": 5, "tables": 0, "formulas": 0, "figures": 0, "diff_hunks": 1}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_qa_report.py -q -k algorithm`
Expected: FAIL on the spot-check assertion — the algorithm block is a `BODY_TEXT` candidate and
the seeded sample of 3 from 5 may include it (the flagged assertion already passes via Task 1).
If the seed happens to skip it, the test still documents the invariant; proceed.

- [ ] **Step 3: Implement**

Add `VLM_TRANSCRIBED` to the `from src.blocks import (…)` list and change:

```python
# Spot-check candidates: running text nobody else looks at. Running matter has its own flag and
# VLM-transcribed bodies are flagged already, so the flagged and sampled sets stay disjoint.
BODY_TEXT = TEXT_BEARING - RUNNING_MATTER - VLM_TRANSCRIBED
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_qa_report.py -q`
Expected: PASS; `validate(report)` inside `build` accepts `type: text` + `reason: vlm_generated`.

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/qa_report.py tests/test_qa_report.py
git commit -m "qa_report: flag algorithm blocks as text/vlm_generated, outside the spot sample"
```

---

### Task 4: Render rule and `BODY_TYPES`

**Files:**
- Modify: `src/render.py` (new `algorithm_callout`, dispatch in `render_block`)
- Modify: `src/sections.py:20-22` (`BODY_TYPES`)
- Test: `tests/test_render.py`, `tests/test_sections.py`

**Interfaces:**
- Consumes: `inline`, `md_text`, `strip_ornament`, `_caption_parts` (existing in `render.py`).
- Produces: `algorithm_callout(block: Block, ctx: Context) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:

```python
def test_algorithm_renders_as_a_callout_titled_by_its_caption():
    from src.render import algorithm_callout

    b = _b(
        "p054-b001",
        "algorithm",
        ("equation_inline", "q ="),
        ("text", " Order quantity  \n "),
        ("equation_inline", "h ="),
        ("text", " Holding cost per unit, $ per year"),
        captions=(Span("text", "▶ TABLE 9.9 Summary of Key Notation"),),
    )
    expected = (
        "> [!abstract] TABLE 9.9 Summary of Key Notation\n"
        "> $q =$ Order quantity\n"
        "> $h =$ Holding cost per unit, \\$ per year"
    )
    assert render_block(b, _ctx()) == expected
    assert algorithm_callout(b, _ctx()) == expected
    assert render_block(_b("p054-b002", "algorithm"), _ctx()) == ""
```

`tests/test_sections.py`: add `TEXT_BEARING` to the `src.blocks` import and `BODY_TYPES` to the
`src.sections` import, then:

```python
def test_body_types_are_the_text_bearing_types_less_footnotes_and_folios():
    assert BODY_TYPES == TEXT_BEARING - {"page_footnote", "page_number"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_render.py tests/test_sections.py -q -k "algorithm or body_types"`
Expected: `ImportError` for `algorithm_callout`; `BODY_TYPES` assertion fails (`algorithm` missing).

- [ ] **Step 3: Implement**

`src/render.py`, after `aside_callout`:

```python
def algorithm_callout(block: Block, ctx: Context) -> str:
    """A boxed notation/equation summary mineru typed `algorithm` (ops ch16, TABLE 16.6).

    A callout titled by the caption, one quoted line per printed row, inline math as `$…$`,
    the footnote last. The body is the VLM's transcription, aligned by the guardrail and
    patched like any text-bearing block.
    """
    cap, foot = _caption_parts(block)
    lines = [t for t in (ln.strip() for ln in inline(block.spans, ctx).splitlines()) if t]
    if foot:
        lines.append(md_text(foot, ctx))
    if not lines and not cap:
        return ""
    head = strip_ornament(md_text(cap, ctx)) if cap else "Summary"
    return "\n".join([f"> [!abstract] {head}", *(f"> {t}" for t in lines)])
```

In `render_block`, before `raise RenderError(…)`:

```python
    if block.type == "algorithm":
        return algorithm_callout(block, ctx)
```

`src/sections.py`:

```python
BODY_TYPES = frozenset(
    {"paragraph", "list", "title", "page_aside_text", "page_header", "page_footer", "algorithm"}
)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_render.py tests/test_sections.py tests/test_review_checks.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/render.py src/sections.py tests/test_render.py tests/test_sections.py
git commit -m "Render an algorithm block as a caption-titled callout; BODY_TYPES includes it"
```

---

### Task 5: Stage 5a confirmation tests and review-skill note

No source change is expected: `patches.py` and `prepass.py` dispatch on `TEXT_BEARING`. The
tests pin that down; the skill tells the reviewer what a `text`-typed `vlm_generated` block is.

**Files:**
- Test: `tests/test_patches.py`, `tests/test_prepass.py`
- Modify: `.claude/skills/chapter-review/SKILL.md` (step 3 rubric list; rules section),
  `.claude/skills/chapter-review/rubric-text.md` (title, `note` vocabulary)

- [ ] **Step 1: Write the tests (expected to pass already)**

`tests/test_patches.py`:

```python
def test_algorithm_body_is_patchable_like_running_text():
    alg = Block(
        id="p054-b001",
        index=1,
        type="algorithm",
        page_idx=54,
        bbox=(0, 0, 1, 1),
        spans=(Span("equation_inline", "q ="), Span("text", " Order quantity - Back order")),
        captions=(Span("text", "TABLE 9.9"),),
    )
    assert target_text(alg, "replace") == " Order quantity - Back order"
    (out,) = apply([alg], [_p(block=alg.id, old=" - ", new=" − ")])
    assert out.text() == " Order quantity − Back order"
    assert out.caption_text() == "TABLE 9.9" and out.inline_math() == ("q =",)
```

`tests/test_prepass.py`, next to `_aside`:

```python
def _algorithm(text, bbox=(70, 80, 600, 110)):
    return {
        "type": "algorithm",
        "bbox": list(bbox),
        "content": {
            "algorithm_caption": [{"type": "text", "content": "TABLE 9.9 Key notation"}],
            "algorithm_content": [{"type": "text", "content": text}],
        },
    }


def test_algorithm_anchor_is_classified_like_running_text(tmp_path, monkeypatch):
    wd = make_work_dir(
        tmp_path,
        monkeypatch,
        pages=[_page(_algorithm("Order quan tity minus back orders"))],
        hunks=[_hunk("p000-b000", "Order quantity minus", "Order quan tity minus")],
        pdf_lines=["Order quantity minus back orders"],
    )
    assert run(Chapter("bma", 5)) == Counter({"same_letters": 1})
    report = json.loads((wd / "qa_report.json").read_text())
    assert "masking gap" not in report["review"]["hunks"][0]["note"]
    (patch,) = _patches(wd)
    assert (patch["op"], patch["block"], patch["old"], patch["new"]) == (
        "replace",
        "p000-b000",
        "quan tity",
        "quantity",
    )
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/test_patches.py tests/test_prepass.py -q -k algorithm`
Expected: PASS. If the pre-pass test yields a different rule, read `Prepass._classify` before
changing the assertion: the invariant that matters is no `masking gap` note and a `replace` on
the algorithm block.

- [ ] **Step 3: Amend the skill**

`SKILL.md` step 3: replace `` `rubric-text.md` for `running_matter_suspect` and spot checks) ``
with `` `rubric-text.md` for `running_matter_suspect`, spot checks and `text`-typed
`vlm_generated` blocks — mineru `algorithm` bodies, a boxed notation summary the VLM
transcribed, whose guardrail hunks are its spotlights) ``. In "Rules you must not break", after
the "Text layer wins on running text" bullet add:

```
- An `algorithm` body is running text the VLM wrote: judge it against the text layer first (its
  hunks), the crop second; fix it with `replace` / `set_inline_math`, never a `set_*` body op.
```

`rubric-text.md`: title → `# Tier A — text block (spot check, running-matter suspect or
`algorithm` body)`; add `boxed summary` to the `note` vocabulary.

- [ ] **Step 4: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add tests/test_patches.py tests/test_prepass.py .claude/skills/chapter-review/SKILL.md \
  .claude/skills/chapter-review/rubric-text.md
git commit -m "Stage 5a: algorithm bodies patch and classify as running text; review-skill note"
```

---

### Task 6: ops ch16 through stages 3–4 and 5a (gate evidence)

**Files:** none in git except the addendum appended to this plan.

- [ ] **Step 1: Run stages 3 and 4 (extraction output already exists; no `FORCE`)**

```bash
make guardrail BOOK=ops CH=16 && make qa_report BOOK=ops CH=16
```

Expected: both exit 0; `work/ops/ch16/guardrail.json`, `qa_report.json` and
`crops/p054-b001.png` exist.

- [ ] **Step 2: Collect the evidence (counts and ids only)**

```bash
uv run python - <<'EOF'
import json
from collections import Counter

wd = "work/ops/ch16/"
g = json.load(open(wd + "guardrail.json"))
q = json.load(open(wd + "qa_report.json"))
print("guardrail:", g["counts"])
print("qa counts:", q["counts"], q["status"])
print("flagged by type:", dict(Counter(f["type"] for f in q["flagged_blocks"])))
print("p054-b001:", [f for f in q["flagged_blocks"] if f["id"] == "p054-b001"])
print("hunks on p054-b001:", sum(h["anchor"] == "p054-b001" for h in g["hunks"]))
print("spot-checked:", any(s["id"] == "p054-b001" for s in q["spot_check"]))
EOF
```

Expected: one flagged entry `{id: p054-b001, type: text, crop: crops/p054-b001.png, reason:
vlm_generated}`; at least one hunk anchored to `p054-b001` (the VLM's hyphen for the printed
minus); `spot-checked: False`.

- [ ] **Step 3: Stage 5a and a render smoke test**

```bash
make review BOOK=ops CH=16
uv run python - <<'EOF'
import json

from src.blocks import load_blocks
from src.render import Context, render_block

blocks = load_blocks("work/ops/ch16/chapter/hybrid_auto/chapter_content_list_v2.json")
b = next(x for x in blocks if x.id == "p054-b001")
ctx = Context("ops", 16, json.load(open("work/ops/ch16/meta.json")), {}, False, None)
out = render_block(b, ctx)
print(len(out.splitlines()), "callout lines; head:", out.splitlines()[0][:14])
EOF
```

Expected: `make review` exits 0 (a failure naming a section anchor is an ops outline issue for
the operator, not this plan — report it); the render prints about 14 lines starting
`> [!abstract]`.

- [ ] **Step 4: Record**

Append a "Measured 2026-09-14" addendum to this plan with the printed counts (no text).

---

### Task 7: Design amendments, metrics note, CLAUDE.md pointer and hard rule

**Files:**
- Modify: `docs/plans/2026-09-06-stages-1-4-design.md` (append `## Amendments (2026-09-14)`)
- Modify: `docs/plans/2026-09-07-stage5-design.md` (Amendments item 10)
- Modify: `metrics/block-types-2026-09-06.md:41`
- Modify: `CLAUDE.md` (pointer paragraph after the stage-5 paragraph; the "Text layer wins" rule)

- [ ] **Step 1: Stages 1–4 design**

Append:

```
## Amendments (2026-09-14)

1. **§1 vocabulary, §6 block model — `algorithm`.** First sighting: ops ch16 `p054-b001`, the
   chapter's boxed "Summary of Key Notation and Equations", labelled `algorithm` by the layout
   model (1 block in ~11,000 across 16 chapters and the fixtures). mineru's hybrid backend keeps
   the VLM transcription of a `code`/`algorithm` body instead of the text layer, so the body is
   running text the VLM wrote. The model loads it: `TEXT_BEARING` gains `algorithm` (aligned,
   pre-pass-classified, patchable like a paragraph; its caption spans precede the body in the
   guardrail's md text); a new class `VLM_TRANSCRIBED = {algorithm}` makes it VLM-generated for
   stage 4 (`flagged_blocks.type` `text`, reason `vlm_generated`, crop rendered from
   `chapter.pdf`) and keeps it out of the spot-check sample. `MASKED`, `CAPTIONED` and the
   qa_report schema are unchanged; `code` and `index` still raise `BlockError`. Plan and
   decision record: `docs/plans/2026-09-14-algorithm-block-plan.md`.
```

- [ ] **Step 2: Stage-5 design Amendments, item 10**

```
10. **§7, §9, §12 — `algorithm` blocks (2026-09-14).** A `text`-typed `vlm_generated` block gets
    no mechanical block check; the guardrail hunks anchored to it are its tier-A spotlights and
    `rubric-text.md` applies. It renders as a `> [!abstract] <caption>` callout with one quoted
    line per printed row and inline math as `$…$`; `BODY_TYPES` includes it so footnote
    references inside the box are scanned. `blocks.py` no longer raises on it; §12 still holds
    for `code` and `index`. See the stages 1–4 design Amendments and
    `docs/plans/2026-09-14-algorithm-block-plan.md`.
```

- [ ] **Step 3: Metrics note**

Replace the line `No `code`, `algorithm`, `index` or `phonetic` in this corpus (they would raise
`BlockError`).` with the same sentence followed by: `Update 2026-09-14: the first `algorithm`
appeared in ops ch16 (`p054-b001`, a boxed notation summary; 1 of ~11,000 blocks across 16
chapters) and is supported since `docs/plans/2026-09-14-algorithm-block-plan.md`; `code`, `index`
and `phonetic` still raise.`

- [ ] **Step 4: CLAUDE.md**

After the stage-5 pointer paragraph add:

```
The `algorithm` block type (first seen 2026-09-14 in ops ch16) is added by
`docs/plans/2026-09-14-algorithm-block-plan.md`, whose decision record amends both designs.
```

Extend the first hard rule:

```
- Text layer wins. VLM output is used only for blocks typed table, formula
  or figure. Never let a VLM transcribe running text. The one exception MinerU
  forces: an `algorithm` body (a boxed notation summary) arrives as VLM text;
  the guardrail aligns it against the text layer and stage 4 flags it
  `text`/`vlm_generated`.
```

Stage only this hunk (the operator's Task 13 edits to CLAUDE.md stay unstaged): build the edited
text from `git show HEAD:CLAUDE.md`, `diff -u` it against HEAD's copy, `git apply --cached` the
patch, and make the same edit in the working copy. Verify with `git diff --cached CLAUDE.md`
(only the two hunks above) and `git diff CLAUDE.md` (only the operator's hunks).

- [ ] **Step 5: Commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add docs/plans/2026-09-06-stages-1-4-design.md docs/plans/2026-09-07-stage5-design.md \
  metrics/block-types-2026-09-06.md docs/plans/2026-09-14-algorithm-block-plan.md
git commit -m "Docs: record the algorithm block in both designs, the metrics note and CLAUDE.md"
```

Then `git status --short` must still show the operator's `M CLAUDE.md`, `M Makefile`,
`M docs/plans/2026-09-07-stage5-plan.md` and the untracked gate-5 files, untouched.
