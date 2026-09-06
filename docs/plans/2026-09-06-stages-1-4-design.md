# Stages 1–4 design: splitter, extraction wrapper, guardrail, QA report

Written 2026-09-06 from a brainstorming session that confirmed
`docs/design/HANDOVER.md` and resolved its §9 open decisions for these stages.
For stages 1–4 this document supersedes HANDOVER §5–§7; HANDOVER §1 (principles),
§6 contracts not restated here, and §8 (fallbacks: do not pre-build) still hold.
Scope: HANDOVER §7 gates 2 and 3 on the benchmark chapters. Stage 5, `vault_commit`,
the benchmark pass and the batch loop are out of scope.

**Amended 2026-09-06 after gate 2** (operator decision; evidence in
`metrics/block-types-2026-09-06.md`): the anchor for stages 3–5 is `<stem>_content_list_v2.json`;
the block-type vocabulary, the PDF-side masking rule and the `flagged_blocks` enums are revised
accordingly in §1, §2, §5, §6, §7, §9 and §10. The plan's Task 7b and its revised Tasks 8–10
implement it.

## 1. Decisions

Corrections to HANDOVER made by the operator (2026-09-06):

| Topic | Decision |
|---|---|
| Client location | The extraction client runs on the server box for all upcoming work. The Mac-over-Tailscale client is deferred; nothing in stages 1–4 assumes it. |
| Benchmark chapters | `bma` chapters 5 and 6 (`Net Present Value and Other Investment Criteria`, `Making Investment Decisions with the NPV Rule`), not `corpfin`. Both must pass gates 2–3. |
| Note granularity | One vault note per chapter *section* (BMA outline level 3: `5-1`, `5-2`, …, plus the unnumbered end-matter entries). |
| Reading lists | Optional. When a course has no reading list, or a book is absent from it, every chapter of the book is in scope. |

§9 decisions resolved in the session:

| Open item | Resolution | Why |
|---|---|---|
| Anchor JSON for stages 3–5 | `<stem>_content_list_v2.json` (amended 2026-09-06; was v1). The `.md` is a reference rendering only. | Both files come from the same `_middle.json` and are 1:1 in identical order (verified on 8 chapters, 4,466 blocks), but v2 keeps inline math as `equation_inline` spans beside unescaped `text` spans — v1 flattens it into `$…$` inside markdown-escaped text, the source of the two most fragile normalization rules — and carries `title.level`, `table_type`, `list_type`, unambiguous `page_*` types, a mineru crop for every display equation, and a blank page as `[]`. Nothing v1 has is missing; footnotes stay verifiable. |
| Section granularity vs. stages 1–4 | Extraction, guardrail and QA stay per **chapter**. `meta.json` records every level-3 outline entry (number, title, start page). Stage 5b later slices the reviewed content_list into per-section notes at heading anchors. | Sections start mid-page (5-2 begins on the page where 5-1 ends); a PDF-level per-section split duplicates text and doubles VLM calls on boundary pages. |
| Block-type vocabulary | v2 types. Text-bearing: `paragraph title list page_footnote page_aside_text page_header page_footer page_number` — all aligned against the text layer, none dropped by type. VLM-generated: `table equation_interline chart`, plus any `image` whose `content` is non-empty (`flowchart` → mermaid, `text_image` → transcription). qa_report `flagged_blocks.type ∈ {table, formula, chart, figure, text}`. Unsupported v2 types (`code`, `algorithm`, `index`) fail loudly. | Generated numbers must be reviewable — flowchart mermaid and spreadsheet transcriptions carry them too (acct, ops, bma p16). Decorative images have no `content` and are not flagged. |
| Running matter (heads, feet, folios) | Aligned like any text. Stage 4 flags a `page_header`/`page_footer`/`page_number` block as `running_matter_suspect` when its text is neither a folio, a `Chapter N`/`Part N` head, a head repeated on ≥2 pages, nor the chapter title. | On the reflowed e-books mineru labels body text as heads/feet (acct 17/17 and ops 4/5 header blocks are section titles, sentences or table rows; acct's 8 footers are labels and table cells). The `.md` drops all of it; masking it on the PDF side would hide the loss. Suspects reach the reviewer instead. |
| Client GPU / model resolution | `extract.py` sets `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `MINERU_DEVICE_MODE=cuda:1` (RTX A6000) and `MINERU_MODEL_SOURCE=local`, reading the pinned snapshot paths already in `~/mineru.json`. | No contention with vLLM's KV cache on GPU 0; offline, deterministic model set. |
| Routing flags → CLI | `routing.inline_formula → -f`, `routing.table → -t`, `routing.image_analysis → --image-analysis`, `routing.lang → -l`. Only `inline_formula` is set today. | Direct 1:1 mapping; mineru 3.4.5 `--help` verified. |
| Entrypoint | `make chapter BOOK=<id> CH=<n>` runs stages 1→4; `FORCE=1` re-runs extraction. | HANDOVER's recommended single entrypoint. |
| Diff strategy | Page-scoped: verbatim block alignment first (order-insensitive), word-token diff (difflib) on the residue, block-anchored hunks. | Cheap, local; reordered boxes/footnotes/captions match for free; a block mineru moved across a page break shows as a visible unmatched block. |

Deferred to stage 5 (recorded so they are not lost): which level-3 entries become notes
(numbered sections only vs. all, end-matter grouping); how notes render footnotes from
content_list; whether a chart's generated data table is kept, dropped or collapsed.

## 2. Facts the design rests on (measured 2026-09-06)

- BMA outline: 850 entries; chapters are level 2 under `Part` level-1 entries, titled
  `N: Title`; numbered sections `N-M: Title` and unnumbered end matter (Key Takeaways,
  Further Reading, Problem Sets, Solutions to Self-Test Questions, Mini-Case) at level 3;
  subsections at level 4. Ch. 5 = pdf indices 149–178 (printed 119–148); Ch. 6 = 179–213
  (printed 149–183). PyMuPDF page labels are present and correct; printed = index − 30
  (0-based), i.e. `page_offset` 31 in the 1-based convention `books.yaml` documents.
- Chapter depth differs per book: bkm/bma/strat/acct chapters at level 2 with numbered
  titles; ops/corpfin at level 1 (`Chapter N`); stats has unnumbered chapter titles but
  numbered sections (`1.1 …`), corpfin splits section numbers from their titles. Stage 1 takes
  `chapter_level` + `chapter_pattern` per book; such quirks are patched into the PDF outline
  once (`toc.patches`, `scripts/patch_toc.py`). `chapter_ranges` remains an emergency override
  (a chapter resolved only by override has no outline entry, hence no sections).
- ops and acct are reflowed e-books without printed page numbers per PDF page; their
  `page_offset` is 0 by explicit decision (printed = PDF 1-based page).
- `books.yaml` currently uses `manual_ranges: {begin, end}` for the intake *body sampling
  range* in `scripts/check_books.py`, while its own comment reserves `manual_ranges` for
  per-chapter overrides. Renamed below.
- Stage-2 output (`hybrid_auto/`): `<stem>.md`, `<stem>_content_list.json` (flat blocks:
  `type`, `page_idx`, `bbox` normalized to 0–1000, `text` + `text_level` for headings,
  `list_items`, `table_body` HTML, `img_path`, equation `text` with `text_format: latex`,
  chart `content` markdown table), `<stem>_content_list_v2.json`, `<stem>_middle.json`
  (`pdf_info[].page_size` in points, `para_blocks`, `discarded_blocks` = header /
  page_number / page_footnote with point bboxes, plus `_backend`, `_effort`,
  `_version_name`), `<stem>_model.json`, `<stem>_layout.pdf`, `<stem>_origin.pdf`,
  `images/`. mineru writes to `<out>/<stem>/hybrid_auto/`.
- Block types seen on the fixtures: `text`, `list` (with `sub_type`, e.g. `ref_text`),
  `table`, `equation`, `chart` (with `sub_type`), `image`, `header`, `page_number`,
  `page_footnote`. `header`, `page_number` and `page_footnote` are absent from the `.md`.
- BMA Ch. 5 text layer (30 pages): 69 soft hyphens, 464 thin/en/em spaces, 266 tabs, 139
  curly quotes, 776 other non-ASCII glyphs, 4 hard line-end hyphens, 63 `●` bullets.
  Running header alternates: bare printed page number on even pages, `Chapter 5 ⁠⁠Title`
  on odd pages. Footnotes are 8 pt vs 10 pt body.
- mineru 3.4.5 honours `MINERU_DEVICE_MODE`, `MINERU_MODEL_SOURCE`,
  `MINERU_TOOLS_CONFIG_JSON` (default `~/mineru.json`, which already has `models-dir`
  pointing at the pinned PDF-Extract-Kit and VLM snapshots).
- `content_list_v2` (`ContentTypeV2`, built by `make_blocks_to_content_list_v2` from the same
  `para_blocks`/`discarded_blocks` as v1): a list per page; block `{type, content, bbox, sub_type?}`;
  text-bearing content is a span list `{type: text|equation_inline|phonetic, content}` with text
  spans unescaped (bma ch05: 0 `\$` vs 59 in v1; 346/346 plain-text blocks identical to v1 once
  v1 is unescaped); `title.level`; `equation_interline.{math_content, math_type, image_source}`
  (crop files exist, 20/20 on bma ch05); `table.{html, table_type, table_nest_level}`;
  `list.{list_type, list_items[].item_content}` (`ref_text` becomes `reference_list`);
  captions/footnotes as span lists; `page_header page_footer page_number page_aside_text
  page_footnote`. 1:1 with v1 in identical order on all 8 extracted chapters. strat ch05 p33 (a
  blank page) is `[]` in v2 and invisible in v1.
- Block types on ch05 of all seven books (`metrics/block-types-2026-09-06.md`): v1 adds
  `aside_text` (bma margin callouts, a bkm part label), `footer` (strat running feet; acct
  mislabeled body) and `ref_text` (strat bibliography) to the fixture vocabulary;
  `_middle.json.discarded_blocks` holds header, page_number, page_footnote, aside_text, footer and
  the `.md` drops all five; `image` blocks carry VLM `content` when `sub_type` is `flowchart`
  (16/16) or `text_image` (1/1), never otherwise (0/62).

## 3. Configuration

### `config/books.yaml` (per book)

```yaml
bma:
  title: …
  course: mitx
  pdf: books/bma/bma.pdf
  body_range: {begin: 4, end: 1052}      # renamed from manual_ranges; intake sampling only
  toc:
    source: outline                       # outline | manual
    chapter_level: 2                      # outline level holding chapters
    chapter_pattern: '^(\d+):'            # regex on the outline title; group 1 = chapter number
    patches: []                           # outline fixes written into the PDF once by scripts/patch_toc.py
    page_offset: 31                       # printed = pdf_1based - page_offset; fallback only; null = unknown;
                                          # 0 for reflowed e-books without printed pagination (ops, acct)
  chapter_ranges: {}                      # ch05: [first_idx, last_idx] (0-based) overrides
  routing: {inline_formula: true}
```

`scripts/check_books.py` and `tests/test_config.py` follow the rename. All seven books are
configured (2026-09-06, evidence from `scripts/probe_toc.py <book>`, verified with `--check`).
Which outline entries are chapters is decided in one place, `src/toc.chapter_entries`, by one
rule: an entry at `chapter_level` whose title matches `chapter_pattern`. Outline quirks are not
handled at run time: `scripts/patch_toc.py <book> --apply` fixes them **once in the PDF** using
the `toc.patches` rules (`number_from_children` for stats' unnumbered chapter titles,
`rebuild_numbered_sections` + `insert` for corpfin's detached section numbers, `rename` for one-offs). The
patched `books/<id>/<id>.pdf` is the source of truth; `books/<id>/<id>.orig.pdf` preserves the
original bytes (gitignored) so the change is reversible and diffable via `get_toc()`; only the
outline objects change (incremental save), the text layer is byte-identical.

### `config/readings/<course>.yaml` (optional)

```yaml
# chapter numbers per book id; a book absent here = all chapters
bma: [5, 6]
```

`readings.list_chapters(book_id) -> list[int]`: if `config/readings/<course>.yaml` exists
and has the book, its list; otherwise every chapter matched by `chapter_pattern` at
`chapter_level` in the outline (plus `chapter_ranges` keys). Ships with `mitx.yaml`
holding only the benchmark chapters; no `fmba.yaml`.

## 4. Stage 1 — `src/split.py`

`uv run python -m src.split --book bma --chapter 5` → `work/bma/ch05/`.

- Slug `ch{NN}` (two-digit zero-padded; `ch{NNN}` never needed for this corpus).
- Range resolution, in order: (1) `chapter_ranges[slug]` if present; (2) the unique outline
  entry at `chapter_level` whose title matches `chapter_pattern` with group 1 == N; the
  chapter ends on the page before the next outline entry with level ≤ `chapter_level`
  (or the last page). No outline, no match, or more than one match →
  `SplitError("bma ch05: <reason>")`, exit 1. No guessing.
- Writes `chapter.pdf` via PyMuPDF `insert_pdf(from_page, to_page)` — text layer and
  labels preserved — and `meta.json`:

```json
{
  "book": "bma", "chapter": "ch05", "number": 5,
  "title": "Net Present Value and Other Investment Criteria",
  "pdf_pages": [149, 178],            // 0-based indices into the book PDF, inclusive
  "printed_pages": [119, 148],
  "sections": [
    {"number": "5-1", "title": "A Review of the Net Present Value Rule",
     "pdf_page": 149, "printed_page": 119, "level": 3},
    {"number": null, "title": "Key Takeaways", "pdf_page": 169, "printed_page": 139, "level": 3}
  ],
  "toc_subtree": [[3, "5-1: A Review …", 149], [4, "Net Present Value’s Competitors", 151], …]
}
```

  `sections` = every entry at `chapter_level + 1` under the chapter; `number` is the
  leading `N-M` token when present. `toc_subtree` = all deeper entries `[level, title,
  pdf_page]` for stage-5 heading verification. Printed pages come from PyMuPDF labels;
  if a label is empty, from `page_offset`; if neither yields an integer → `SplitError`
  (qa_report needs `pages`).

## 5. Stage 2 — `src/extract.py`

`uv run python -m src.extract --book bma --chapter 5 [--force]` (all four stage CLIs take the
chapter number; `ch05` is also accepted).

- Preflight (each a loud failure): `MINERU_SERVER_URL` set; `GET <url>/health` answers;
  `~/mineru.json` (or `MINERU_TOOLS_CONFIG_JSON`) has `models-dir.pipeline` pointing at an
  existing directory; `work/<book>/<ch>/chapter.pdf` exists.
- Skips when `work/<book>/<ch>/chapter/hybrid_auto/chapter_content_list.json` exists
  unless `--force`.
- Runs, with `CUDA_DEVICE_ORDER=PCI_BUS_ID MINERU_DEVICE_MODE=cuda:1
  MINERU_MODEL_SOURCE=local` in the environment:
  `mineru -p work/<book>/<ch>/chapter.pdf -o work/<book>/<ch> -b hybrid-http-client
  -u $MINERU_SERVER_URL --effort high [-f false] [-t false] [--image-analysis false] [-l …]`
  from `routing`. Streams mineru's stderr through; records wall time.
- Postcondition (gate-2 criterion, enforced): `chapter.md`, `chapter_content_list.json`,
  `chapter_content_list_v2.json`, `chapter_middle.json`, `images/` present;
  `len(_middle.json.pdf_info)` == chapter.pdf page count (mineru writes one entry per page,
  blank or not — content_list has no block for strat ch05's blank p33), and content_list
  references no page beyond it. Outputs are never reshaped.

## 6. Stage 3 — `src/guardrail.py` with `src/blocks.py` (amended 2026-09-06)

### Block model (`src/blocks.py`, shared with stage 4)

Anchor: `<stem>_content_list_v2.json`. `load_pages(path) -> list[list[Block]]` (one list per
page, a blank page is `[]`), `load_blocks(path)` flattens, `on_page(blocks, i)`,
`v2_path(hybrid_auto, stem)`. `Block(id, index, type, page_idx, bbox, spans, captions, level,
math, html, content, crop, sub_type)`; `id = f"p{page_idx:03d}-b{index:03d}"` where `index` is
the block's position within its page. `Span(type, content)`, type `text | equation_inline |
phonetic`; list items, and a caption from its footnote, are separated by a `"\n"` text span.
`Block.text()` joins text spans, `caption_text()`, `inline_math()` lists the `equation_inline`
contents, `is_vlm_generated()` is true for `VLM_GENERATED` types and for an `image` whose
`content` is non-empty. `crop` is `content.image_source.path` (relative to `hybrid_auto/`) for
tables, display equations, charts and images. Unsupported v2 types raise `BlockError` naming
page and block — extend the model on first sight, never guess.

Type classes: `TEXT_BEARING = {paragraph, title, list, page_footnote, page_aside_text,
page_header, page_footer, page_number}` (all aligned; nothing dropped by type),
`RUNNING_MATTER = {page_header, page_footer, page_number}`, `VLM_GENERATED = {table,
equation_interline, chart}`, `FIGURES = {image, chart}`, `CAPTIONED = {table, chart, image}`
(caption/footnote spans are text-layer prose around a non-text body), `MASKED = {table,
equation_interline, chart, image}`, `SCHEMA_TYPE = {table: table, equation_interline: formula,
chart: chart, image: figure}`.

### Token streams, per page

- PDF side: `page.get_text("words")` on `chapter.pdf`; drop words whose centre lies in the bbox
  of a `MASKED` block on that page (0–1000 coordinates scaled to points, 2 pt pad). Those
  regions' glyphs — table cells, display-formula symbols, chart labels, figure text — are in the
  text layer but deliberately absent from the md side. **Nothing else is masked.** The five
  `_middle.json.discarded_blocks` types all have content_list_v2 counterparts and are matched,
  not hidden; `_middle.json` is read only for the `page_size` sanity check (must equal the
  PyMuPDF page rect within 1 pt, else fail).
- MD side: the body spans of every `TEXT_BEARING` block and the caption spans of every
  `CAPTIONED` block, in page order. `equation_inline` spans are flattened with `flatten_latex`;
  spans are joined with a space (mineru puts none between a formula and the text after it).
  Every token carries its `Block.id`.

### Normalization (`src/normalize.py`)

`flatten_latex(latex)` runs span by span before the string rules: `\$` → `$`, then LaTeX
commands, braces, `^`, `_` and all whitespace removed (`\$ 5 0 0` → `$500`, `r _ { f }` →
`rf`). It is not a string rule — with v2 there is no `$…$` to parse and no `\$ \% \_` to
unescape.

Ordered pure string rules, applied to both sides unless marked; each has its own failing test on
a string captured from the fixtures or the chapters before it is implemented:

1. `strip_markup` (md) — `<sup>x</sup>`, `<sub>x</sub>` → `x`.
2. `nfkc` — NFKC (ligatures → letters, thin/en/em spaces → space, superscript digits → digits).
3. `punctuation_variants` — curly quotes → straight; en/em dash, U+2212 → `-`.
4. `drop_soft_hyphens` — remove U+00AD; a soft hyphen at a line end joins the word it broke
   (stats sets 143 line ends as `invest\u00ad\ning` while mineru holds `investing`; gate 3).
5. `dehyphenate` — PDF: `(\w)-\n(\w)` → `\1\2`; then both sides: remove intra-word hyphens.
6. `drop_bullets_and_list_markers` — `●`, `•`, `∙` (mineru's list glyph), leading `- ` / `* `.
   Numbered markers stay on both sides: stripping them was asymmetric (PyMuPDF sets a bold
   ordinal on its own line, so the PDF kept `1.` while mineru's `1. Why` lost it — corpfin 11,
   strat 21 hunks) and ate a sentence-final `0.` at a PDF line start; no side drops a real
   list number (gate 3, `metrics/hunk-stats-2026-09-06.md`).
7. `join_letter_spaced_caps` — runs of ≥3 tokens of ≤2 capitals lose their spaces
   (`P A R T I I I`, `PA R T I I I` → `PARTIII`): PyMuPDF and mineru group the glyphs of a
   tracked small-caps running head differently (bkm control page). Split words such as
   `capi tal` are untouched.
8. `drop_zero_width_spaces` — U+200B, which PyMuPDF emits as words of its own or glued to
   glyphs where display formulas are set as running text (bma ch06; gate 3).
9. `tokenize` — all whitespace → one space; split.

Rules are appended, never reordered silently; each addition during gate-3 tuning follows the
same RED-first step and is logged in the plan's verification output.

### Alignment, diff and hunks

Block first, words second. For each md-side block in page order, its normalized tokens are
searched as a contiguous run in the page's PDF tokens — first at or after the end of the
previous match (reading order), then anywhere on the page. A hit consumes those PDF tokens and
retires the block. This is what makes boxed examples, "Concept Check" boxes, footnotes,
running heads and captions cost nothing: PyMuPDF emits them in content-stream order, mineru in
visual order, and the text is identical. Verified on the control page with the v2 model and
rules 1–7: 48/48 blocks match (running heads and folios included), zero hunks, 2495 = 2495
tokens.

The residue — unconsumed PDF tokens in order vs. tokens of unmatched blocks in order — goes
through `difflib.SequenceMatcher(None, pdf, md, autojunk=False)`. Every non-`equal` opcode
is a hunk; hunks separated by ≤ 2 equal tokens merge. Hunk shape is exactly HANDOVER §6:
`{"page": <printed page>, "anchor": <Block.id>, "pdf_text": …, "md_text": …}` with 3 residual
tokens of context on each side. The anchor is the block owning the md tokens; for a pure
deletion it is the block whose matched PDF span ends just before the deleted words, else the
nearest preceding md block, else the page's first aligned block, else `pNNN-none`.

Known real-defect classes seen on the fixtures, deliberately **not** folded by
normalization because they are wrong in the output: words split at former hyphenation
points (`capi tal`, `inven tory`, `Earn ings`), dropped characters (`ou company`), a dash
rendered as `- `. They are stage-5 patch items; gate 3 counts them as real, not spurious.

### Output

`work/<book>/<ch>/guardrail.json`: `{"pages": N, "counts": {"pdf_tokens", "md_tokens",
"matched_blocks", "unmatched_blocks", "hunks", "hunks_inline_math"}, "hunks": [...]}` where
`matched_blocks` / `unmatched_blocks` count aligned blocks and `hunks_inline_math` counts
hunks whose owning block has an `equation_inline` span (MFR output to review, not spurious).
CLI prints a per-page table and exits 0; nonzero only for structural faults (missing inputs,
content_list_v2 page count ≠ chapter.pdf, page-size mismatch).

## 7. Stage 4 — `src/qa_report.py` with `src/qa_schema.py` (amended 2026-09-06)

`uv run python -m src.qa_report --book bma --chapter 5` → `work/<book>/<ch>/qa_report.json`.

- `book`, `chapter` (slug), `pages` = `meta.printed_pages`.
- `extraction`: `backend: "hybrid-http-client"`, `effort` = `_middle.json._effort`,
  `mineru_version` = `_version_name`, `timestamp` = ISO-8601 mtime of
  `chapter_content_list_v2.json`.
- `counts`: `blocks` (all), `tables`, `formulas` (= `equation_interline`), `figures` (= `image` +
  `chart`, decorative images included), `diff_hunks`.
- `diff_hunks`: `guardrail.json.hunks` verbatim.
- `flagged_blocks`, sorted by id — the stage-5 work order (HANDOVER §6: "all tables and formulas
  plus anything low-confidence"):
  - every block with `is_vlm_generated()`: `{id, type: table|formula|chart|figure, crop,
    reason: "vlm_generated"}`; `crop` is the block's `image_source.path` under
    `hybrid_auto/images/` — mineru crops display equations too, so stage 4 renders nothing for
    them (rendered from `chapter.pdf` only if the path is empty);
  - every `RUNNING_MATTER` block whose text is not running matter: `{id, type: "text", crop:
    "crops/<id>.png", reason: "running_matter_suspect"}`. Running matter = a folio (digits,
    roman numerals, or `Page N` as the reflowed ops e-book prints them), a `Chapter N`/`Part N`
    head (letter-spaced caps such as `C H A P T E R` are joined first), a head repeated verbatim
    on ≥2 pages, or the chapter title; empty text is not a suspect. Everything else is a heading
    or sentence the layout model mislabeled, which the `.md` drops and stage 5 must keep.
    Audited on ch05 of all seven books (`metrics/block-types-2026-09-06.md`): 37 suspects out of
    570 running-matter blocks — 27 real (acct 23, bma 1, ops 3), 10 harmless (stats' single-page
    section heads, strat's margin tab numbers). Position- or outline-based suppression of the
    harmless ones was rejected: it would also hide acct's mislabeled section headings.
- `spot_check`: seeded sample (`sha256(book + chapter)`) of 5 % (min 3) of
  `TEXT_BEARING − RUNNING_MATTER` blocks, each rendered to `crops/<id>.png` from `chapter.pdf`
  (block bbox scaled from 0–1000 to points, 2× zoom, PyMuPDF).
- `status: "pending_review"`.
- `qa_schema.validate(report)`: required keys, value types, enums (`type ∈ {table, formula,
  chart, figure, text}`, `reason ∈ {vlm_generated, running_matter_suspect}`, `status`), `pages`
  two ints, `counts` non-negative, `counts.diff_hunks == len(diff_hunks)` — raises with the path
  of the first violation. Stage 4 does not write a report that fails validation. No jsonschema
  dependency.

## 8. Entrypoint and layout

```
make chapter BOOK=bma CH=5 [FORCE=1]   # split → extract → guardrail → qa_report
src/__init__.py  config.py  blocks.py  normalize.py  readings.py  split.py  extract.py  guardrail.py  qa_report.py  qa_schema.py
work/<book>/<ch>/chapter.pdf  meta.json  chapter/hybrid_auto/…  guardrail.json  qa_report.json  crops/
```

`pyproject.toml` gains `pythonpath = ["."]` under `[tool.pytest.ini_options]` so `src.*`
imports work identically under `python -m` and pytest. CLAUDE.md's Commands and Layout
sections are updated in the same change that adds `make chapter`.

## 9. Testing

- Fixture cache `tests/fixtures/cache/<book>/<set>/hybrid_auto/` (gitignored), seeded by
  copying the 2026-09-06 sanity outputs from `work/sanity/`; `pytest -m integration`
  regenerates it against the live server.
- Unit tier (no network, no book PDFs): reading-list resolution; splitter on a synthetic
  PDF built in-test with PyMuPDF (outline with Part/Chapter/Section levels, labels) covering
  happy path, missing outline, ambiguous match, `chapter_ranges` override, label fallback;
  one test per normalization rule; block model on the cached fixtures' `_content_list_v2.json`
  — control page zero table/formula blocks (50 blocks), table page 5 tables / 1 display
  equation / 1 chart, formula page 4 `equation_interline` with balanced braces and existing
  crops, per-page positional ids, a blank page loads as `[]`, an unsupported type raises, v2
  text spans carry no markdown escapes while v1 does; guardrail — control page 48/48 blocks
  aligned and `hunks == 0`, masks remove exactly the words inside VLM-body boxes,
  order-insensitive block alignment, hunk shape/anchor/context including pure deletions,
  page-count mismatch fails; qa_report — built from the table fixture it validates with 5/1/1
  flags all carrying `images/` crops, the running-matter heuristic on captured
  acct/strat/bma strings, suspects flagged as `text`, an image with `content` flagged as
  `figure`, and hand-broken reports fail with the right path.
- Integration tier: fixture regeneration; `make chapter` on Ch. 5 and Ch. 6.
- Forbidden: byte equality on any VLM-generated block.

## 10. Gates and evidence

- Gate 2: `make chapter BOOK=bma CH=5` and `CH=6` complete; `ls hybrid_auto/` and the
  block-type histogram for each chapter are pasted into the plan's verification step.
- Gate 3: for each chapter, `guardrail.json.counts` and a hand classification of every
  plain-text hunk (spurious vs. real); spurious < ~10 per chapter after tuning;
  `qa_report.json` passes `validate()`; `counts` and the number of `running_matter_suspect`
  flags pasted.

## 11. Out of scope

Stage 5 skill and `vault_commit.py`; per-section note slicing; footnote rendering policy;
the benchmark pass over seven books; the batch loop; the Mac client and Tailscale check;
`chapter_ranges` for stats/acct; the LLM heading-refinement hook (HANDOVER §8: only if
gate 4 shows bad hierarchy).
