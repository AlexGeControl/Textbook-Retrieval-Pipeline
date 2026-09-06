# Stages 1–4 design: splitter, extraction wrapper, guardrail, QA report

Written 2026-09-06 from a brainstorming session that confirmed
`docs/design/HANDOVER.md` and resolved its §9 open decisions for these stages.
For stages 1–4 this document supersedes HANDOVER §5–§7; HANDOVER §1 (principles),
§6 contracts not restated here, and §8 (fallbacks: do not pre-build) still hold.
Scope: HANDOVER §7 gates 2 and 3 on the benchmark chapters. Stage 5, `vault_commit`,
the benchmark pass and the batch loop are out of scope.

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
| Anchor JSON for stages 3–4 | `<stem>_content_list.json`. The `.md` is a reference rendering only. | Verified: mineru's `.md` drops every `page_footnote` block; content_list keeps them with `page_idx`, bbox and `text_level`. Anchoring on content_list verifies footnotes instead of losing them, and gives block ids for hunks, flags and later per-section slicing. |
| Section granularity vs. stages 1–4 | Extraction, guardrail and QA stay per **chapter**. `meta.json` records every level-3 outline entry (number, title, start page). Stage 5b later slices the reviewed content_list into per-section notes at heading anchors. | Sections start mid-page (5-2 begins on the page where 5-1 ends); a PDF-level per-section split duplicates text and doubles VLM calls on boundary pages. |
| Block-type vocabulary | qa_report `flagged_blocks.type ∈ {table, formula, chart}`; mineru `equation → formula`; `chart` blocks are flagged because at `--effort high` they carry a VLM-generated data table; `image` blocks are counted as figures, not flagged. | Generated numbers must be reviewable. Decorative images carry no transcribed content. |
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
  numbered sections (`1.1 …`). Stage 1 takes `chapter_level` + `chapter_pattern` per book,
  optional `normalize` steps, and a per-chapter `chapter_ranges` emergency override (a chapter
  resolved only by override has no outline entry, hence no sections).
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
    chapter_pattern: '^(\d+):'            # regex on the (normalized) title; group 1 = chapter number
    normalize: []                         # optional in-memory outline fixes (src/toc.py), e.g.
                                          # [number_from_sections] for STATS-style unnumbered titles
    page_offset: 31                       # printed = pdf_1based - page_offset; fallback only; null = unknown;
                                          # 0 for reflowed e-books without printed pagination (ops, acct)
  chapter_ranges: {}                      # ch05: [first_idx, last_idx] (0-based) overrides
  routing: {inline_formula: true}
```

`scripts/check_books.py` and `tests/test_config.py` follow the rename. All seven books are
configured (2026-09-06, evidence from `scripts/probe_toc.py <book>`, verified with
`--check`): chapter numbers come from the title for six books and, for stats, from the first
numbered section via the `number_from_sections` normalizer. Which outline entries are
chapters is decided in one place, `src/toc.chapter_entries`, shared by stage 1 and the
reading-list resolver. New outline layouts are handled by adding a normalizer, never by
extending the parser.

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
  `chapter_content_list_v2.json`, `chapter_middle.json`, `images/` present; content_list
  page count == chapter.pdf page count. Outputs are never reshaped.

## 6. Stage 3 — `src/guardrail.py` with `src/blocks.py`

### Block model (`src/blocks.py`, shared with stage 4)

`load_blocks(path) -> list[Block]`; `Block(id, index, type, page_idx, bbox, text,
list_items, table_body, img_path, text_level, sub_type)`; `id = f"p{page_idx:03d}-b{index:03d}"`
where `index` is the block's position in `_content_list.json`. Type classes:
`RUNNING_TEXT = {text, list, page_footnote}`, `VLM_GENERATED = {table, equation, chart}`,
`FIGURES = {image, chart}`, `DISCARDED = {header, page_number}`, `CAPTIONED = {table, chart,
image}`. `Block.running_text()` joins `list_items` with newlines for lists;
`Block.caption_text()` joins a captioned block's `*_caption` + `*_footnote` strings — text-layer
prose that sits around a non-text body and must be matched, not lost.

### Token streams, per page

- PDF side: `page.get_text("words")` on `chapter.pdf`; drop words whose centre lies in
  (a) a `header` or `page_number` bbox from `_middle.json.pdf_info[p].discarded_blocks`
  (point coordinates; assert `page_size` equals the PyMuPDF page rect within 1 pt, else
  fail) or (b) the bbox of any `table`, `equation`, `chart` or `image` block on that page
  (content_list 0–1000 coordinates scaled to points). Those regions' glyphs — table cells,
  display-formula symbols, chart labels — are in the text layer but are deliberately absent
  from the md side, so leaving them would hunk every table and formula. Footnote regions
  stay — they are matched by `page_footnote` blocks.
- MD side: the page's `RUNNING_TEXT` blocks (running text) and `CAPTIONED` blocks (caption
  text only — the body stays excluded) in content_list order; every token carries its
  `Block.id`.

### Normalization (`src/normalize.py`)

Ordered pure functions on strings, applied to both sides unless marked; each rule has its
own failing unit test on a string captured from the fixtures or the chapter before it is
implemented. Seed rules:

1. `flatten_inline_math` (md) — `$…$` → content with LaTeX commands, braces, `^`, `_`
   and all inner whitespace removed (mineru spaces digits: `\$ 5 0 0` → `$500`). Runs
   first because an unescaped `$` is the delimiter; unescaping `\$` earlier would create
   false delimiters.
2. `unescape_markdown` (md) — `\$ \% \_ \# \*` → literal; `<sup>x</sup>` → `x`;
   strip `**` / `*` emphasis markers.
3. `nfkc` — NFKC (ligatures → letters, thin/en/em spaces → space, superscript digits → digits).
4. `punctuation_variants` — curly quotes → straight; en/em dash, U+2212 → `-`.
5. `drop_soft_hyphens` — remove U+00AD.
6. `dehyphenate` — PDF: `(\w)-\n(\w)` → `\1\2`; then both sides: remove intra-word hyphens.
7. `drop_bullets_and_list_markers` — `●`, `•`, leading `- ` / `N. ` markers.
8. `tokenize` — all whitespace → one space; split.

Rules are appended, never reordered silently; each addition during gate-3 tuning follows
the same RED-first step and is logged in the plan's verification output.

### Alignment, diff and hunks

Block first, words second. For each md-side block in content_list order, its normalized
tokens are searched as a contiguous run in the page's PDF tokens — first at or after the end
of the previous match (reading order), then anywhere on the page. A hit consumes those PDF
tokens and retires the block. This is what makes boxed examples, "Concept Check" boxes,
footnotes and captions cost nothing: PyMuPDF emits them in content-stream order, mineru in
visual order, and the text is identical. Verified on the control page: 40/40 blocks match,
zero hunks, with no reorder-specific logic.

The residue — unconsumed PDF tokens in order vs. tokens of unmatched blocks in order — goes
through `difflib.SequenceMatcher(None, pdf, md, autojunk=False)`. Every non-`equal` opcode
is a hunk; hunks separated by ≤ 2 equal tokens merge. Hunk shape is exactly HANDOVER §6:
`{"page": <printed page>, "anchor": <Block.id>, "pdf_text": …, "md_text": …}` with 3 equal
context tokens on each side. The anchor is the block owning the md tokens; for a pure
deletion it is the block whose matched PDF span ends just before the deleted words, else
the nearest preceding md block, else the page's first aligned block, else `pNNN-none`.

Known real-defect classes seen on the fixtures, deliberately **not** folded by
normalization because they are wrong in the output: words split at former hyphenation
points (`capi tal`, `inven tory`, `Earn ings`), dropped characters (`ou company`), a dash
rendered as `- `. They are stage-5 patch items; gate 3 counts them as real, not spurious.

### Output

`work/<book>/<ch>/guardrail.json`: `{"pages": N, "counts": {"pdf_tokens", "md_tokens",
"matched_blocks", "unmatched_blocks", "hunks", "hunks_inline_math"}, "hunks": [...]}` where
`matched_blocks` / `unmatched_blocks` count aligned blocks and `hunks_inline_math` counts
hunks whose owning block contains inline math (VLM/MFR output to review, not spurious).
CLI prints a per-page table and exits 0; nonzero only for structural faults (missing
inputs, page-count or page-size mismatch).

## 7. Stage 4 — `src/qa_report.py` with `src/qa_schema.py`

`uv run python -m src.qa_report --book bma --chapter 5` → `work/<book>/<ch>/qa_report.json`.

- `book`, `chapter` (slug), `pages` = `meta.printed_pages`.
- `extraction`: `backend: "hybrid-http-client"`, `effort` = `_middle.json._effort`,
  `mineru_version` = `_version_name`, `timestamp` = ISO-8601 mtime of
  `chapter_content_list.json`.
- `counts`: `blocks` (all), `tables`, `formulas` (= `equation`), `figures` (= `image` +
  `chart`), `diff_hunks`.
- `diff_hunks`: `guardrail.json.hunks` verbatim.
- `flagged_blocks`: every `VLM_GENERATED` block: `{id, type: table|formula|chart, crop,
  reason: "vlm_generated"}`. `crop` = `img_path` for tables/charts; equations have no
  mineru crop, so stage 4 renders `crops/<id>.png` from `chapter.pdf` (block bbox scaled
  from 0–1000 to points, 2× zoom, PyMuPDF).
- `spot_check`: seeded sample (`sha256(book + chapter)`) of 5 % (min 3) of unflagged
  `RUNNING_TEXT` blocks, each rendered to `crops/<id>.png` the same way.
- `status: "pending_review"`.
- `qa_schema.validate(report)`: required keys, value types, enums (`type`, `status`,
  `reason`), `pages` two ints, `counts` non-negative — raises with the path of the first
  violation. Stage 4 does not write a report that fails validation. No jsonschema dependency.

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
  one test per normalization rule; guardrail on the four cached fixtures with structural
  assertions — control page zero table/formula blocks and `hunks == 0` after tuning, table
  page `tables == 5`, formula page `formulas == 4` and every equation `text` balanced in
  `$$…$$` and braces; qa_report built from a cached fixture validates, and hand-broken
  reports fail with the right path.
- Integration tier: fixture regeneration; `make chapter` on Ch. 5 and Ch. 6.
- Forbidden: byte equality on any VLM-generated block.

## 10. Gates and evidence

- Gate 2: `make chapter BOOK=bma CH=5` and `CH=6` complete; `ls hybrid_auto/` and the
  block-type histogram for each chapter are pasted into the plan's verification step.
- Gate 3: for each chapter, `guardrail.json.counts` and a hand classification of every
  plain-text hunk (spurious vs. real); spurious < ~10 per chapter after tuning;
  `qa_report.json` passes `validate()`; `counts` pasted.

## 11. Out of scope

Stage 5 skill and `vault_commit.py`; per-section note slicing; footnote rendering policy;
the benchmark pass over seven books; the batch loop; the Mac client and Tailscale check;
`chapter_ranges` for stats/acct; the LLM heading-refinement hook (HANDOVER §8: only if
gate 4 shows bad hierarchy).
