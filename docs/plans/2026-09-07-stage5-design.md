# Stage 5 design: pre-pass, review skill, rendering and vault commit

Written 2026-09-07 from a brainstorming session that started from
`docs/plans/2026-09-07-stage5-bootstrap.md`, confirmed its §3 as fixed and settled its §5
questions one at a time. For stage 5 this document supersedes HANDOVER §6 "Stage 5" and the
gate 4–5 details of §7; HANDOVER §1 (principles) and §8 (fallbacks: do not pre-build) still
hold, and the stages 1–4 design (`docs/plans/2026-09-06-stages-1-4-design.md`) is unchanged.
Scope: HANDOVER §7 gates 4 and 5 on the eight extracted chapters under `work/`. The batch loop
(gate 6), the Mac client and any change to mineru are out of scope.

Everything here is measured on the eight work dirs (ch05 of all seven books plus bma ch06) as
they stood on 2026-09-07 after PR #1 (`2f3a7d8`). No GPU or server is needed to build or test
stage 5. The vault host may be unreachable; certification never depends on it.

## 1. Decisions

Bootstrap §3 (HANDOVER §6 rules, hard rules, one note per section, skill location, gates 4–5)
is confirmed without change. One reading note: "outline level 3" means the outline level
directly below the chapter, which is what `meta.json.sections` records (level 3 in bkm, bma,
strat and acct; level 2 in corpfin, stats and ops, whose chapters sit at outline level 1).

| Open item (bootstrap §5) | Resolution | Why |
|---|---|---|
| 1 Vault transport | Certify into a local staging tree `vault/<book>/<chNN>/` (gitignored, self-contained); push is a separate, retryable step over the Obsidian Local REST API at section or chapter granularity; host, port and key from `OBSIDIAN_HOST`, `OBSIDIAN_PORT`, `OBSIDIAN_API_KEY`. Default push root `raw/textbooks/`. CLI with argparse subparsers, not `fire`. | The only shape where certification does not depend on the network and no second source of truth exists. The REST interface was probed live (§3). `fire` parses argument values as Python literals, so section numbers such as `5.1` would arrive as floats. |
| 2 Note layout | Every `meta.json` section becomes one note, no grouping; a hub note per chapter; filenames `<book>-<chNN>-<NN>-<slug>.md` (hub `00`), assets `<book>-<chNN>-<block id>.<ext>`; frontmatter = the five fixed keys plus `title`, `section`, `book_title`, `edition`, `certified_at`; no links into lecture notes. | strat and acct have no numbered sections, so "numbered only" yields nothing there; grouping is editorial and the mission is as-is. Key Takeaways, Problem Sets and Summary recur in every chapter, and Obsidian resolves `[[…]]` by shortest path, so bare titles collide in a shared vault. Kebab-case matches the vault's existing `notes/01-introduction-to-finance/` convention. |
| 3 Pre-pass | Deterministic `src/prepass.py`; seven mechanical classes; patches in `work/<book>/<chNN>/patches.json`, applied at render time, never to `content_list_v2.json`; PDF-wins text rebuilt from raw PyMuPDF spans, not from the normalized hunk text. | Over half the hunks are mechanical; review tokens must scale with defects, not corpus size. Folding the resolution into stage 3 would hide defects from the gate-3 numbers. |
| 4 Review mechanics | Two tiers: tier A (Sonnet, 100 % of crops, fixed rubric, fixed JSON answer, no write path) and tier B (the reviewer, disagreements and `needs_eyes` hunks only). Text-layer checks verify formulas and tables before any crop is opened. All writes through `src/review.py`; `finalize` computes the status. | HANDOVER §6 requires every table and formula to be compared to its crop; a cheap perception tier makes that affordable, and two independent signals agreeing is stronger than either alone. Hand-editing a 27 KB JSON is where an agent introduces silent errors. |
| 5 Rendering policy | One fixed rule per block type (§9): Obsidian footnotes, callouts for aside runs, collapsed callouts for chart data and mermaid, pipe tables for `simple_table`, HTML for `complex_table`, `%% p. N %%` page comments, `##` for TOC subheadings and `###` for other titles. | Faithful and readable for a human; cosmetic refinements wait until a human has read a section and formed an opinion (operator's stop rule). |
| 6 Gate 4 without a phone | A mechanical battery over the staging tree is part of certification; when the host answers, Obsidian's own renderer is asked over REST and its output counted; one human mobile pass per gate from a seven-item checklist recorded in `metrics/`. | Obsidian's REST HTML rendering is the same core the mobile app uses; the phone confirms once what the battery cannot see. |
| 7 mineru line-final glyph loss | Kept as a stage-5 patch class (the pre-pass `edge_glyph` rule), with superscript-flagged glyphs restored as `<sup>n</sup>`; measured at gate 5; an upstream report drafted from a synthetic reproduction for the operator to file. No local mineru patch. | Every lost glyph surfaces as a guardrail hunk and the class is fully mechanical. mineru runs as a subprocess, so a fix means a forked pin plus re-extraction for about 40 patches across eight chapters. |
| 8 Benchmark pass | The seven extracted ch05 chapters plus bma ch06; `scripts/benchmark_report.py` computes every number it can from the stage-5 artifacts; a seeded human calibration sample (2–3 tables, 3 formulas per chapter) measures what the tiers missed; tokens collected where the harness exposes them, no threshold; counts only in `metrics/`. | Comparable to the gate-3 evidence on the same chapters; the calibration sample is the number that says whether the review process can be trusted on a whole book. |

Items deferred from the stages 1–4 design and its plan Addendum 3 are resolved here: which
entries become notes (all), footnote rendering (§9), chart data tables (collapsed callout),
`page_aside_text` (callout per run), running-matter suspects (body text), ops folios (pre-pass),
the glyph loss (decision 7). `chapter_ranges` for stats/acct and the Mac client stay deferred.

## 2. Terms

- **Operator**: the human running the pipeline and pushing to git and to the vault.
- **Reviewer**: the Claude Code agent running `.claude/skills/chapter-review/SKILL.md` on one
  chapter, in the operator's interactive session or as one subagent of the benchmark fleet.
  The reviewer is tier B.
- **Tier A**: the Sonnet perception agents the reviewer dispatches over crops. They answer a
  fixed rubric with a fixed JSON schema and have no write path.
- **Pre-pass**: deterministic Python with no agent involved (`src/prepass.py`).
- **Certification**: the `status` that `review finalize` computes. **Commit**: writing the
  staging tree. **Push**: copying the staging tree into the vault.

## 3. Facts the design rests on (measured 2026-09-07)

Corpus (`metrics/block-types-2026-09-06.md`, re-read with `src.blocks`): 4,466 blocks on 366
pages; 259 tables (166 simple, 93 complex), 230 display equations, 41 charts (all with a data
table in `content`), 79 images (17 with `content`: 16 flowchart mermaid, 1 text transcription),
584 flagged blocks in the eight `qa_report.json` files, every one with its crop file on disk.
mineru's `title.level` is only ever 1 or 2; the heading tree must come from `meta.json`.

Hunks: 622 across the eight chapters (acct 38, bkm 111, bma ch05 57, bma ch06 82, corpfin 40,
ops 81, stats 140, strat 73). A crude fold (NFKC, whitespace and Unicode punctuation removed,
symbols kept, casefolded) makes 324 pairs equal; 100 more anchor a block with `equation_inline`
spans; 14 are PDF-only and 8 md-only after context; 176 differ. Hunk `pdf_text`/`md_text` carry
up to three residual context tokens on each side, so a classifier must strip the common prefix
and suffix first. The mechanisms behind the residue are in `metrics/hunk-stats-2026-09-06.md`
§4; the dominant genuine defect is mineru dropping the last glyph of a right-justified line or
a trailing footnote superscript.

Footnotes: 61 `page_footnote` blocks; 46 open with `<sup>n</sup>`. The other 15 are
continuation paragraphs of a multi-block footnote (bma p012: eight blocks with numbered steps
and formulas), page-top continuations (bma p026, bkm p033) and three star footnotes (bkm, stats).
bkm ch05 has 35 paragraphs carrying `<sup>` for 18 footnote blocks.

Asides: 41 `page_aside_text` blocks in 11 runs of consecutive blocks (bma ch05 17, bma ch06 23,
bkm 1). A bma run is `BEYOND THE PAGE` / `#` / topic / `mhhe.com/brealey14e`; the `#` is a
margin icon with no text-layer words.

Decorative images (no `content`): 62; 4 carry a caption; 58 are uncaptioned and cover less than
1.5 % of the page (bkm's check-mark icons, logos); none is uncaptioned and larger.

Sections: bma ch05 has 9 (four numbered, five end-matter), 120–3,730 words each; two of them
(Further Reading, Problem Sets) start on the same page. acct's section title "Analyzing the
Financial Statements" arrives typed `page_header` (`p006-b008`) on exactly the section's page,
so section anchors must accept running-matter suspects. Inline math spans keep the surrounding
text spans' spaces (`"…cash flows "`, `C _ { 0 } , C _ { 1 }`, `", and so on"`). ops injects
`Page N Page N` into 7 paragraphs. `toc_subtree` holds levels 3–4 (bkm, bma, strat, acct) or 2–3
(corpfin, stats, ops).

Environment: pylatexenc 2.11, lxml, requests, bs4 and PIL are in the venv as mineru
dependencies; latex2mathml and matplotlib are not. `LatexWalker(..., tolerant_parsing=False)`
raises on `\frac{a}{b` and does not catch `\left( x \right`. Obsidian renders math with
MathJax, not KaTeX.

Vault (live probe 2026-09-07, Obsidian 1.13.7, Local REST API plugin 4.1.3 at
`192.168.3.26:27123`): only the `obsidian-01-foundations-of-modern-finance` key from
`~/.claude.json` authenticates; the generic `obsidian` key is rejected. `PUT /vault/{path}`
into a non-existent nested folder returns 204 and creates the parents; a PNG PUT with
`image/png` round-trips byte for byte; `GET` with `Accept: application/vnd.olrapi.note+json`
returns parsed frontmatter; a directory `GET` returns `{"files": [...]}`; `DELETE ?permanent=true`
returns 204 and empty parent folders disappear. The vault holds `raw/transcripts/`,
`notes/<NN-module>/` and `references/`, all kebab-case.

## 4. Architecture and data flow

For one chapter, after `make chapter` has produced `work/<book>/<chNN>/`:

1. `make prepass` — `src/prepass.py` reads `qa_report.json`, `chapter.pdf` and the content
   list, writes its patch records to `patches.json` and a verdict for every hunk into the new
   `review` key of `qa_report.json`.
2. `make review-checks` — `src/review_checks.py` runs the text-layer, LaTeX, HTML, heading and
   footnote checks and writes `review.blocks[*].checks`, `review.headings`,
   `review.footnotes`.
3. The reviewer dispatches tier A over every flagged, spot-check and suspect crop with the
   fixed rubric; each answer is relayed into `review.blocks[*].checks.visual` (or the
   spot-check verdict) through `src/review.py`.
4. The reviewer adjudicates the residue — `needs_eyes` hunks, blocks where the text-layer check
   and tier A disagree or either reported a discrepancy, unresolved checks — opening those
   crops itself, and writes verdicts and `rv-` patches through the CLI.
5. `review finalize` derives the status from the verdicts, renders the staging tree, runs the
   check battery, and sets `certified` only if all three pass; otherwise `needs_attention`
   with `review.unresolved` filled.
6. `vault_commit push` copies the manifest's files into the vault over REST, reads each back,
   records the result in the manifest, and refuses anything not certified.

`make review` runs steps 1 and 2; it is the skill's first action. Steps 3–4 are the skill.
Rendering (`vault_commit render`) and the battery (`vault_commit check`) also run alone at any
time for local inspection, with `certified: false` in the frontmatter.

## 5. Modules

| module | job | reads | writes |
|---|---|---|---|
| `src/textlayer.py` | PyMuPDF words and raw spans with superscript flags for a page; words whose centre lies in a bbox (guardrail's 2 pt pad); locate the raw run whose normalized form equals a token sequence | `chapter.pdf` | nothing |
| `src/patches.py` | `Patch` records, `load`/`save`, validation (block exists, `old` occurs once, op allowed for the block type, sha256 binding), `apply(blocks, patches) -> list[Block]` | `patches.json` | `patches.json` |
| `src/prepass.py` | context stripping, the seven classes, PDF-wins text, `pp-` patches, `review.hunks` | report, PDF, blocks | patches, report |
| `src/review_checks.py` | formula and table text-layer verification, LaTeX parse and delimiter pairing, HTML rectangularity, heading tree, footnote references | blocks, PDF, meta | report (`checks`, `headings`, `footnotes`) |
| `src/review.py` | the `review` key model; CLI `start hunk block spot patch finalize` | report, patches | report, patches |
| `src/qa_schema.py` | unchanged `validate`; new `validate_review` | | |
| `src/sections.py` | anchors, preamble, per-section block lists, footnote assignment, page boundaries | meta, patched blocks | nothing |
| `src/render.py` | block-to-Markdown rules, slugs, frontmatter, section and hub notes, navigation | sections | Markdown strings |
| `src/vault_commit.py` | CLI `render check push`; staging tree, assets, manifest; REST client | notes, crops | `vault/<book>/<chNN>/` |
| `src/vault_checks.py` | the mechanical battery over a staging tree; `--rendered` variant over REST | staging tree, REST | nothing |
| `scripts/benchmark_report.py` | the gate-5 table from the eight work dirs | reports, patches, manifests | `metrics/gate5-benchmark-<date>.md` |
| `.claude/skills/chapter-review/` | `SKILL.md`, tier-A rubrics and answer schemas as reference files | | |

`blocks.py`, `guardrail.py`, `qa_report.py`, `normalize.py`, `split.py`, `extract.py` are not
modified. Stage-2 outputs are read only. `Block` is a frozen dataclass; `apply` returns new
blocks via `dataclasses.replace`.

## 6. Stage 5a — pre-pass (`src/prepass.py`, `src/patches.py`, `src/textlayer.py`)

### Patch model

`patches.json` (format in §11) holds one record per patch: `id`, `block`, `op`, `old`, `new`,
`source`, `rule`, `hunk`, `note`. Ops:

- `replace` — `old` → `new` in the block's body text, caption text or LaTeX; `old` must occur
  exactly once in the raw joined text of that field, checked at creation and again at apply.
- `drop_block` — the block renders as nothing.
- `set_math`, `set_html`, `set_content` — replace one VLM body whole; review-sourced only.

Ids are `pp-NNNN` (pre-pass) and `rv-NNNN` (reviewer). The pre-pass rewrites only `pp-`
records; reviewer records survive a rerun. `content_list_sha256` binds the file to one
extraction; a mismatch fails at apply time with "re-extracted, rerun prepass and review".
Patches are applied by `render`, never to the content list.

### Classification

Each hunk's `pdf_text` and `md_text` are tokenized; the common prefix and suffix tokens (the
guardrail's context) are stripped to leave the core pair. `fold(s)` = NFKC, remove whitespace,
remove Unicode category P (punctuation), keep category S (symbols), casefold. Classes are
tested in this order; the first match wins.

| class | test | action | verdict |
|---|---|---|---|
| `junk` | md-only core whose anchor block bbox holds no text-layer words | `drop_block` | `dropped` |
| `move` | chapter-wide: an md-only core whose fold equals the fold of one or several PDF-only cores elsewhere in the chapter, or the reverse; one insertion may pair with several deletions | none (the cross-page merge is desirable output; the empty next-page paragraph renders as nothing) | `move` |
| `duplicate` | md core is the PDF core repeated n ≥ 2 times | `replace` collapsing to one copy | `patched` |
| `folio` | md-only tokens matching `Page N` (or the page's folio) inside a body block | `replace` dropping them | `patched` |
| `same_letters` | `fold(pdf) == fold(md)` | PDF wins: `replace` with the rebuilt PDF text; no patch when the rebuilt text equals the md raw text | `accepted_pdf` |
| `inline_math` | anchor block has `equation_inline` spans and `flatten_latex` of them, letters and digits only, equals the PDF core's letters and digits | none; LaTeX kept | `verified` |
| `edge_glyph` | `fold(md)` equals `fold(pdf)` with one glyph, or one superscript-flagged run, removed at the start or end of one md token | PDF wins: `replace`; a single-letter PDF word at the start (drop cap) is glued to the following word; superscript-flagged glyphs are wrapped as `<sup>n</sup>` | `accepted_pdf` |
| — | anything else, or any class whose raw run cannot be anchored uniquely, or a hunk anchored to a VLM body (a masking gap) | none | `unresolved` (`needs_eyes`) |

### PDF-wins text

The pre-pass never pastes the hunk's `pdf_text`: it is normalized and has lost curly quotes, em
dashes and superscript information. `textlayer.raw_run(page, tokens)` locates on the hunk's
page the run of raw words whose normalized form (the guardrail's `PDF_RULES`) equals the core
tokens, uniquely, and returns their raw text from PyMuPDF's `rawdict` spans with ligatures
expanded, soft hyphens removed and the word each one broke rejoined, quotes and dashes as
printed, and superscript-flagged glyphs wrapped in `<sup>…</sup>`. `old` on the md side is the
smallest word window of the anchor block's raw text whose normalized form (`MD_RULES`) equals
the md core, also unique. Either lookup failing drops the hunk to `needs_eyes`.

## 7. Review checks (`src/review_checks.py`)

Run after the pre-pass, before the reviewer reads anything. Results go into
`review.blocks[*].checks` (keys not applicable to a type are `null`, never absent),
`review.headings` and `review.footnotes`.

- **Formula text-layer check** (`textlayer_match`): letters and digits of `flatten_latex(math)`
  equal the letters and digits of the words the guardrail masked under the block's bbox.
  `null` when the mask holds no words (symbol fonts, image-set formulas).
- **Table text-layer check** (`textlayer_match`, `rows`, `cols`, `rectangular`): the HTML parses
  with lxml; every row spans the same number of columns after colspan and rowspan; the bag of
  normalized cell tokens equals the bag of normalized masked words. The differing tokens are
  listed for tier B.
- **LaTeX** (`latex_parses`): every display and inline LaTeX span parses with
  `LatexWalker(tolerant_parsing=False)` and passes a pairing check for `\left`/`\right`,
  `\begin`/`\end` and unescaped `$`. A one-off task builds a macro histogram over all eight
  chapters and checks it against MathJax's TeX macro set.
- **Heading tree** (`headings`): every `meta.json` section anchor found on its page (§9), and
  every subheading of `toc_subtree` (the level below the sections) found as a `title` block
  inside its section slice, matched by fold. Missing titles are listed.
- **Footnote references** (`footnotes`): every `<sup>n</sup>` footnote definition has a body
  reference in the chapter and vice versa; unmatched ids are listed. Because the dominant
  mineru defect drops trailing superscripts, this is a defect detector, not bookkeeping.

## 8. Review skill (`.claude/skills/chapter-review/SKILL.md`)

Invoked as `/chapter-review <book> <chapter>` in a Claude Code session. Steps, in order:

1. `make review BOOK=… CH=…` (pre-pass and checks), then `review start` to stamp
   `effort.started`.
2. Read `qa_report.json` only: the `review.prepass.counts`, the `needs_eyes` hunks with their
   contexts, the flagged blocks with their checks, the heading and footnote reports.
3. **Tier A.** Dispatch one perception agent per batch of about ten crops with `model: sonnet`
   and the rubric for each block type, from the skill's reference files:
   - table: rows, columns, header cells, every cell whose value in the crop differs from the
     HTML;
   - formula: does the crop match the LaTeX; each differing symbol;
   - chart or flowchart: does the data table or mermaid match the crop; each discrepancy;
   - spot-check or running-matter crop: does the crop text equal the block text; is the block
     body text or running matter.
   Each answer is a fixed JSON object (`match`, `rows`, `cols`, `discrepancies`, `note`). The
   mechanism is the Workflow tool with a `schema` per agent, batches kept under the harness's
   15-agent guideline, which requires the operator's opt-in per session; Agent fan-out with
   `model: sonnet` is the fallback, same rubric, same schema. Tier A has no write path: the
   reviewer relays every answer through `review block --visual …`, where it is validated.
4. **Tier B.** For each `needs_eyes` hunk, each block where `textlayer_match` and `visual.match`
   disagree or either lists a discrepancy, each spot-check or suspect the rubric did not clear,
   and each missing heading or unmatched footnote: open that crop (and only that), decide, and
   write the verdict and any `rv-` patch through the CLI. The text layer wins unless the crop
   shows the layer itself is wrong. Patches are surgical `replace`s wherever possible; a
   `set_*` op rewrites one VLM body against its crop and never running text.
5. `review finalize`. If `certified`, report the counts. If `needs_attention`, list
   `review.unresolved` and stop; never push.

The skill also states what the reviewer may open — crops referenced by `flagged_blocks` and
`spot_check`, hunk contexts in the report — and forbids `chapter.md`, `chapter.pdf` pages,
files outside the chapter's work dir, and editing `qa_report.json` or `patches.json` with a
text tool. Effort: `crops_opened` and `patches` are counted by the CLI; tokens are not visible
to the agent and are recorded by the operator from `/cost` per session and from the workflow
report where it exposes them.

**Certification semantics.** `certified` requires: a verdict other than `unresolved` on every
hunk, every flagged block and every spot-check entry; zero missing headings; zero unmatched
footnotes; a successful render; a green check battery. Anything else is `needs_attention` with
every reason under `review.unresolved`. `finalize` refuses to run while any verdict is missing,
and never sets `status` from a hand-typed value.

**Benchmark fleet.** One parent session runs tier A as one Workflow per chapter, then
dispatches one tier-B subagent per chapter with the same skill. Each subagent writes only inside
its own `work/<book>/<chNN>/`; the parent only aggregates and runs the report script.

## 9. Sections and rendering (`src/sections.py`, `src/render.py`)

### Slicing

- The section anchor is any `TEXT_BEARING` block on the section's page (index
  `pdf_page − pdf_pages[0]`) whose fold equals the fold of the section title or of
  `<number> <title>`; `title` blocks are preferred, running-matter suspects are accepted. Zero
  candidates, or two of the preferred type, fail naming book, chapter, section and page.
- A section runs from its anchor to the block before the next anchor in page and index order,
  the last to the chapter's end. A block belongs to the section that holds it, by its own page
  and index, so a cross-page merged paragraph stays where mineru placed it.
- Blocks before the first anchor are the chapter preamble and render in the hub; the level-1
  chapter `title` block is dropped there because the hub's H1 comes from `meta.json`.
- Footnote definitions are assigned to the section whose body references them; an unreferenced
  definition stays with the section holding the block and is reported (§7).

### Rules by block type, patches applied first

| block | rendering |
|---|---|
| section anchor | H1 `<number> <title>` as printed in `meta.json` |
| `title` matching a `toc_subtree` subheading | `## <text>` |
| any other `title` | `### <text>`; in the hub preamble, a bold line |
| `paragraph` | text spans verbatim; `equation_inline` → `$<latex.strip()>$` (Obsidian does not render inline math that starts or ends with a space); one backslash escape when the first characters would start a Markdown list, heading or quote (`#`, `>`, `-`/`*`/`+` + space, `N.`/`N)` + space); empty blocks skipped |
| `list` | `- ` per item, mineru's bullet glyph stripped; items that start with a printed number keep it (ordered lists, strat's reference lists) |
| `page_footnote` with `<sup>n</sup>` | `[^n]: text` at the end of the owning section note; a following footnote block without a marker continues the most recent footnote as an indented paragraph; a block with no open footnote (star footnotes) renders as a plain paragraph under a `---` rule at the section end |
| `<sup>n</sup>` in body text | `[^n]` when footnote n exists in the chapter, else left as HTML |
| `page_aside_text` run | one `> [!info] <first block>` callout with the remaining blocks as its lines (`#` icons are already dropped by the pre-pass) |
| `page_header`/`page_footer`/`page_number` | dropped; a `running_matter_suspect` renders as a paragraph unless its verdict is `dropped` |
| `equation_interline` | `$$` on its own lines around the LaTeX, `\tag` kept; no crop |
| `table`, `simple_table` | pipe table, first row as header, `\|` escaped in cells, `<br>` → space; caption as a plain paragraph above with a leading ornament glyph (category So) stripped; table footnote as a paragraph below; a `simple_table` whose HTML carries colspan or rowspan renders as HTML and is listed in the render log |
| `table`, `complex_table` | the HTML `<table>` verbatim, caption and footnote as above |
| `chart`, `image` with `content` | `![[<book>-<chNN>-<id>.<ext>]]`, caption paragraph, then the data table or mermaid inside `> [!note]- Chart data (VLM transcription)` (or `Flowchart (VLM transcription)`), only when the block's verdict is `verified` or `patched` |
| `image` without `content` | embedded with its caption when captioned; dropped when uncaptioned and under 1.5 % of the page; embedded and named in the render log otherwise |
| page boundary | `%% p. <printed> %%` before the first block of each page in a note, invisible in reading view, so the synthesis stage can cite a page |

Notes are one block per paragraph separated by blank lines, no hard wrapping, no reordering,
no sentence-level edits, no text from `chapter.md`, no VLM text outside the four body types.
Each section note ends with a navigation line of aliased wikilinks: previous section, hub,
next section. The hub holds frontmatter, the H1 chapter title, a line with book title, edition
and printed page range, the preamble, and one aliased wikilink per section in order.

**Slug**: NFKC, casefold, every run of characters outside `[a-z0-9]` → `-`, edges trimmed,
cut at the last `-` before 60 characters. bma ch05 →
`bma-ch05-00-net-present-value-and-other-investment-criteria.md` (hub) …
`bma-ch05-09-mini-case-vegetrons-cfo-calls-again.md`. The original title stays in the H1 and in
frontmatter.

**Stop rule** (operator, 2026-09-07): the renderer aims at faithful, readable notes. Rendering
refinements beyond that wait until a human has read a section and formed an opinion; no task
polishes a rule nobody has read against.

## 10. Vault commit (`src/vault_commit.py`, `src/vault_checks.py`)

- `render --book B --chapter N [--section S]` writes `vault/<book>/<chNN>/`: the hub, one note
  per section, `assets/` with the crops the notes embed (copied from `hybrid_auto/images/`,
  extension preserved), and `manifest.json` (§11). `--section` accepts the ordinal or the slug
  and rewrites that note and its assets only; the manifest entry for every file carries its
  section ordinal. No `.obsidian/` folder is written.
- `check [--section S] [--rendered]` runs the battery (below); `--rendered` adds the REST pass.
- `push [--section S] [--root raw/textbooks/]` PUTs every manifest file (or the section's note
  and assets) to `<root>/<book>/<chNN>/…` with `text/markdown` for notes and the guessed MIME
  type for assets, GETs each back, compares bytes, and records `status` and `verified` per file
  plus `pushed_at`, `host` and `root` in the manifest. Refuses a manifest not marked
  `certified`, and a section whose note fails the battery.

**Battery** (`vault_checks`, always available):

- Frontmatter parses as YAML and carries the five fixed keys with the right types, `certified`
  true when the manifest says certified, `source_pages` two ascending integers.
- Math: even `$$` count per note; inline `$` balanced per paragraph with no space just inside a
  delimiter; every LaTeX span passes the §7 parse and pairing check.
- Tables: every pipe-table row has the same unescaped pipe count and a separator row follows the
  header; every HTML table parses and is rectangular.
- Links: every `![[…]]` resolves to a file in the chapter's `assets/`; every asset is referenced
  at least once; every `[[…]]` resolves to a note in the chapter tree; every `[^n]` has exactly
  one definition in the same note and vice versa.
- Callouts: every line of a callout carries `> `; the fold marker is well formed.
- Structure: one H1 per note; one note per `meta.json` section plus the hub; filenames match the
  slug pattern, are unique and under the cap.
- Manifest: every file listed with a matching sha256; no unlisted files; `qa_report_sha256`
  matches the current report.

**Rendered check** (`--rendered`, host-dependent): `GET /vault/<path>` with `Accept: text/html`
returns Obsidian's own rendering. The check asserts that the number of rendered math
containers, `<table>` elements and resolved embeds equals the source note's counts and that no
embed is marked unresolved. The exact class names Obsidian emits are recorded by the first
host-dependent plan task, not assumed. With the host down the step reports "skipped, host
unreachable", distinct from pass and from fail.

## 11. Data formats

`work/<book>/<chNN>/patches.json`:

```json
{
  "content_list_sha256": "…",
  "patches": [
    {
      "id": "pp-0001",
      "block": "p004-b008",
      "op": "replace",
      "old": "capi tal",
      "new": "capital",
      "source": "prepass",
      "rule": "same_letters",
      "hunk": 12,
      "note": ""
    }
  ]
}
```

`qa_report.json` gains one key, `review`; the existing keys and `validate` are untouched and
`validate_review` checks the new key:

```json
"review": {
  "prepass": {"timestamp": "…", "counts": {"same_letters": 31, "move": 8, "needs_eyes": 12}},
  "hunks": [{"verdict": "accepted_pdf", "rule": "same_letters", "patches": ["pp-0001"], "note": ""}],
  "blocks": [
    {
      "id": "p001-b006",
      "verdict": "verified",
      "checks": {
        "latex_parses": null,
        "rectangular": true,
        "rows": 6,
        "cols": 3,
        "textlayer_match": true,
        "visual": {"model": "sonnet", "match": true, "rows": 6, "cols": 3, "discrepancies": []}
      },
      "patches": [],
      "note": ""
    }
  ],
  "spot_check": [{"id": "p000-b001", "verdict": "ok", "note": ""}],
  "headings": {"sections": [9, 9], "subheadings": [16, 16], "missing": []},
  "footnotes": {"definitions": 17, "references": 17, "unmatched": []},
  "effort": {"started": "…", "finished": "…", "crops_opened": 25, "patches": 14, "notes": ""},
  "unresolved": [{"kind": "hunk", "ref": 12, "reason": "…"}]
}
```

- `hunks`: exactly one entry per `diff_hunks` entry, same order; verdicts
  `accepted_pdf | accepted_md | move | dropped | verified | patched | unresolved`.
- `blocks`: exactly one entry per `flagged_blocks` entry, matched by id; verdicts
  `verified | patched | dropped | unresolved`; `checks` keys not applicable to the type are
  `null`.
- `spot_check`: one per stage-4 sample; verdicts `ok | patched | unresolved`.
- `status` is derived by `finalize`, never set by hand.

`vault/<book>/<chNN>/manifest.json`:

```json
{
  "book": "bma",
  "chapter": 5,
  "status": "certified",
  "rendered_at": "…",
  "qa_report_sha256": "…",
  "files": {
    "bma-ch05-01-a-review-of-the-net-present-value-rule.md": {"sha256": "…", "section": 1},
    "assets/bma-ch05-p003-b000.jpg": {"sha256": "…", "section": 1}
  },
  "push": {
    "root": "raw/textbooks/",
    "host": "192.168.3.26:27123",
    "pushed_at": "…",
    "files": {"bma-ch05-01-a-review-of-the-net-present-value-rule.md": {"status": 204, "verified": true}}
  }
}
```

An asset referenced by two sections carries the lower ordinal and is pushed with either.

Note frontmatter:

```yaml
---
book: bma
chapter: 5
course: mitx
source_pages: [126, 134]
certified: true
title: The Internal Rate of Return Rule
section: "5-3"
book_title: Principles of Corporate Finance
edition: 14e (Brealey et al.)
certified_at: 2026-09-08
---
```

`section` is a quoted string so `5.10` survives YAML, `null` for unnumbered sections and the
hub; `course` comes from `config/books.yaml`; `source_pages` is the section's printed range.
An inspection render before certification writes `certified: false` and `certified_at: null`.

## 12. Error handling

Every failure names book, chapter and the offending item; nothing guesses, nothing degrades
silently, and a skipped step is never reported as passed.

- **Inputs and binding.** A missing `qa_report.json`, `guardrail.json`, `meta.json`,
  `chapter.pdf` or content list stops the stage naming the path and the make target that
  produces it. A `patches.json` whose sha256 differs from the content list fails at apply. A
  staging tree whose `qa_report_sha256` differs from the current report fails `check` and
  `push`. A `review` key that fails `validate_review` is never written; every CLI write
  validates the whole report and the whole patch list first.
- **Pre-pass.** A hunk whose raw run or `old` window is not unique becomes `needs_eyes`.
  `drop_block` is emitted only for a block with zero text-layer words in its bbox. A `replace`
  whose `old` occurs twice is rejected at creation. A hunk anchored to a VLM body is a masking
  gap and becomes `needs_eyes` with that reason; the pre-pass never touches a VLM body.
- **Slicing and rendering.** A section anchor not found fails naming title and page; a missing
  subheading is recorded and blocks certification but not rendering. A `title` matching two
  `toc_subtree` entries, or two blocks matching one anchor, fails. An unsupported block type
  raises from `blocks.py`. A `replace` whose `old` is absent at render time fails the render.
  Unmatched footnote references or definitions are recorded and block certification.
- **Certification.** `finalize` refuses while any verdict is missing; `certified` requires zero
  unresolved verdicts, zero missing headings, zero unmatched footnotes, a successful render and
  a green battery; re-running `finalize` after new verdicts is the normal loop and never
  downgrades a certified chapter unless the artifacts changed.
- **Push.** Refuses a manifest not marked `certified` and a section whose note fails the
  battery. Missing `OBSIDIAN_*` variables fail before any request; an unreachable host fails
  naming the host; a rejected key fails with "authenticated false". Each PUT is followed by a
  GET and byte comparison; a mismatch marks that file `verified: false` and the push exits
  nonzero after finishing the remaining files. `check --rendered` with the host down exits
  "skipped, host unreachable".
- **Reviewer discipline** (skill text, re-validated by `finalize`): only referenced crops and
  hunk contexts may be opened; every verdict and patch goes through `src/review.py`; tier A has
  no write path, so a malformed answer fails schema validation when relayed.

## 13. Configuration and entrypoints

Makefile targets added, all taking `BOOK` and `CH`: `prepass`, `review-checks`, `review`
(= `prepass` then `review-checks`), `render`, `check`, `push`, `benchmark-report`. `render`,
`check` and `push` accept `SECTION` (ordinal or slug); `check` accepts `RENDERED=1`; `push`
accepts `ROOT` (default `raw/textbooks/`). Module entrypoints:

```text
uv run python -m src.prepass        --book B --chapter N
uv run python -m src.review_checks  --book B --chapter N
uv run python -m src.review         start|hunk|block|spot|patch|finalize --book B --chapter N …
uv run python -m src.vault_commit   render|check|push --book B --chapter N [--section S] …
uv run python scripts/benchmark_report.py [--out metrics/gate5-benchmark-<date>.md]
```

Environment: `OBSIDIAN_HOST`, `OBSIDIAN_PORT`, `OBSIDIAN_API_KEY` for `push` and
`check --rendered` only, never committed. `.gitignore` gains `vault/**`.

Dependencies: no new packages. `pylatexenc`, `lxml` and `requests` are already installed as
mineru dependencies and are declared as direct dependencies in `pyproject.toml` so a future
mineru bump cannot remove them silently; `uv.lock` does not change. `fire` is not added.

## 14. Testing

Unit tier (`uv run pytest`, no network, no GPU), three input sources:

- The fixture cache `tests/fixtures/cache/` for real mineru blocks: the table page for HTML
  rectangularity and bag-of-tokens checks, the formula page for LaTeX parsing and text-layer
  letter matching, the chart page for the embed and collapsed data table, the control page for
  "zero patches, zero drops".
- Captured strings and hand-built blocks for every string transform: each pre-pass class, each
  render rule, slug generation, footnote continuation, aside runs, paragraph escapes, page
  comments. One failing test per rule before the rule exists, as in `tests/test_normalize.py`.
- A `workdir` marker for tests that read `work/<book>/<chNN>/` and skip with a message when it
  is absent, like the cache tests. They pin the measured numbers: bma ch05 pre-pass class
  counts, acct's `page_header` anchor, bkm's 18 footnotes closing, the 11 aside runs.

Forbidden: byte equality on any VLM body; weakening the control-page assertion (48/48 blocks,
0 hunks); reading `chapter.md`.

RED per module: `textlayer` — a raw run returns the printed curly quote and em dash, expands a
ligature, wraps a superscript-flagged glyph; `patches` — `old` occurring twice is rejected, a
stale sha256 fails, `apply` leaves its input untouched; `prepass` — seven class tests on
captured hunks, a drop cap joining `T` to `he`, `Page 83 Page 83` removed, an unanchored hunk
becoming `needs_eyes`; `review_checks` — strict pylatexenc raises on the captured unbalanced
brace, `\left` without `\right` fails pairing, a non-rectangular table fails, a definition
without a reference is reported; `review` — a write that would break `validate_review` is
rejected, `finalize` refuses a missing verdict, status derivation for each unresolved kind;
`sections`/`render` — anchor on a `page_header`, two sections on one page, preamble to the hub,
every §9 rule on a captured block; `vault_commit`/`vault_checks` — manifest sha256 round trip,
an odd `$$` count fails, an unresolved embed fails, `push` refuses `needs_attention` with a fake
transport, the REST client against a recorded response.

Integration tier, marker `vault`, skipped without `OBSIDIAN_*`: one PUT/GET/DELETE round trip
in a probe folder and the `--rendered` class-name discovery.

## 15. Gates and evidence

Counts are pasted into the plan's verification steps; `metrics/` holds counts and block ids
only, never book text.

- **Gate 4** on bma ch05 and ch06: `review.prepass.counts`; tier-A match/mismatch by type;
  tier-B patches by op; `finalize` output with `status: certified`; `check` all green;
  `check --rendered` counts when the host was up; the push manifest; the operator's seven-item
  mobile checklist (inline and display math, a simple and a complex table, a figure and a
  chart, a folding callout, a footnote jump and return, previous/hub/next links, invisible page
  comments) recorded with date and app version in `metrics/gate4-bma.md`.
- **Gate 5** on the seven ch05 chapters plus bma ch06: `scripts/benchmark_report.py` writes one
  table — pages, blocks, hunks total and by class, `needs_eyes`, unresolved, flagged by type,
  text-layer pass rates, tier-A match/mismatch, tier-B patches by op and target, formula error
  rate (patched or unresolved over total), table cell accuracy (cells with a confirmed patch
  over cells total), `edge_glyph` patches and how many were footnote markers, footnote check
  failures, headings found, wall time per step, certification outcome — plus a per-book notes
  section. The operator appends tokens where the harness exposed them (no threshold) and the
  calibration rows: 2–3 tables and 3 formulas per chapter from the stage-4 seeded sampler,
  compared to their crops by eye, recording every error the tiers missed. The operator has read
  BMA and BKM in person, so those two rows also check the sampler. A book passes when its
  chapter is `certified` and the calibration finds nothing missed; a failing book names its
  HANDOVER §8 fix (a targeted table budget, the heading-refinement hook only on a failed
  heading check, a per-book flag otherwise).
- **Glyph-loss decision** (decision 7): measured at gate 5 as above; the class stays as long as
  zero `edge_glyph` patches were wrong; a whole-book run where the class escapes the rule is the
  trigger to revisit a local fix. The upstream report is drafted from a synthetic one-page PDF
  built with PyMuPDF (right-justified lines ending in narrow glyphs) so no book content leaves
  the machine; filing it is the operator's action.

## 16. Build order

Each step is measured against the gate it serves, on the existing work dirs:

1. `textlayer`, `patches`, `prepass`, the `review` key and `validate_review`, `make prepass` —
   class counts on all eight work dirs, zero patches and zero drops on the control page.
2. `sections`, `render`, `vault_commit render`, `vault_checks check` — a full render of bma ch05
   passing the battery with `certified: false`.
3. `review_checks`, the `review` CLI, `finalize` — text-layer verification rates on bma ch05's
   38 tables and 20 formulas.
4. The skill, tier-A rubrics and schemas, a dry run on bma ch05 in one session — `certified`
   reached through the CLI only.
5. `vault_commit push`, `check --rendered` — the live round trip and read-back on bma ch05.
6. Gate 4 on bma ch05 and ch06, including the mobile pass.
7. `benchmark_report.py`, then gate 5 over the eight chapters.

Execution uses `superpowers:executing-plans` with human checkpoints at gates 4 and 5, on the
`stage-5` branch in the main checkout (no worktree: `books/`, `work/` and `tests/fixtures/`
are untracked). The operator pushes.

## 17. Out of scope

The batch loop over full reading lists (gate 6); the Mac client and Tailscale check; any change
to mineru; any change to stages 1–4 other than the additive `validate_review`; alt-text for
figures; links from textbook notes into lecture or course notes; `chapter_ranges` for
stats/acct; rendering refinements beyond "faithful and readable" until a human has read a
section.

## Amendments (2026-09-07, during planning)

Measured on the eight work dirs while writing `docs/plans/2026-09-07-stage5-plan.md`. Each item
amends the section it names; the plan implements the amended form.

1. **§9 anchors.** The single-block fold match left sections unresolved in seven of eight
   chapters (only stats was clean). Causes and the rules that fix them: headings split across
   consecutive `title` blocks (acct `APPENDIX 5A:` + title, bma `KEY` + `TAKEAWAYS`,
   `MINI-CASE` + title) → a run of up to four consecutive text-bearing blocks; the number
   printed after the title (corpfin `Why Use Net Present Value?5.1`) → forms title, number+title
   and title+number; `<sup>*</sup>` and a U+0007 control character inside outline titles (bkm)
   → the fold strips markup and category C; a case-only duplicate on the page (strat's key-term
   margin title) → exact-case match preferred, then `title` type, then the shorter run, else
   ambiguous and an error; a section whose printed heading is absent but whose first
   `toc_subtree` child is printed on the same page (acct End-of-Chapter Homework Material →
   ETHICS in the Real World) → rule `first_child`, the child heading stays in the body; the first
   section on the chapter's first page with no printed heading (ops Introduction) → rule
   `chapter_start`, the first body block after the chapter title. Left to the outline, as the
   fail-loud rule intends: bkm "End of Chapter Material" (a grouping label; the page opens with
   SUMMARY) and strat "Experiential Exercise…" (printed in the plural) get `toc.patches` renames
   at gate 5. Subheading candidates include running-matter suspects (acct's KEY TERMS is typed
   `page_footer`). A missing subheading no longer blocks certification by itself: it needs a
   reviewer verdict, `found_as` or `not_a_heading` (strat's five Strategy Spotlight entries are
   boxed features typed `page_header` and split into three blocks).
2. **§7 table text-layer check.** Exact bag equality matched 0 of 38 bma tables: HTML cells carry
   inline LaTeX (`$C_0$` against the text layer's `C0`) and ellipses differ (`...` vs `. . .`).
   The check flattens `$…$` with `flatten_latex`, joins cells with spaces and compares
   fold-per-token bags (9 of 38 exact before flattening; the plan records the new rate). The
   differing tokens go to `checks.textlayer_diff` and to tier A as spotlights; a table is
   `verified` when tier A reports a match and either the bag is equal or every spotlight token
   was resolved as an artefact.
3. **§7 formula text-layer check.** bma 19 of 20 match; stats 1 of 78, because MathematicalPi
   encodes ≥ as `$`, Σ as `o` and = as `5`. A per-book switch `review: {textlayer_math: false}`
   in `config/books.yaml` (stats) sets the check to null so tier A alone decides, instead of
   manufacturing 77 disagreements for tier B.
4. **§7 footnotes.** A definition without a reference blocks certification (the lost trailing
   superscript). A reference without a definition is informational (`footnotes.dangling`):
   strat's 74 endnote marks and acct's 16 have no footnote blocks, and exponents such as
   `1.1<sup>2</sup>` are excluded by the preceding-character rule (a digit or `)`). Measured:
   bma ch05 11 definitions / 12 references, bma ch06 13 / 13, bkm 14 definitions with 3
   unreferenced, corpfin 6 with 2.
5. **§6 classification.** Hunk texts carry the guardrail's context (the first three tokens agree
   in 531 of 622 hunks, the last three in 496), so the core is the pair minus its common prefix
   and suffix. Order: junk, duplicate (block-level period detection: bma ch06 `p026-b007` is
   five hunks on one block), folio, move (token-greedy strip against the chapter-wide insertion
   and deletion pools; a remainder re-enters classification as `move+<rule>`), then inline_math
   for blocks with inline math (tested before same_letters so their LaTeX is kept), same_letters,
   edge_glyph. A one-sided core (bma's drop cap `A` is a separate 37 pt word) is widened by one
   shared context token before the edge test. PDF-wins windows widen with context until the raw
   run is unique on the page and the `old` substring is unique in the block.
6. **§5 modules.** `src/fold.py` (`fold`, `letters`, `clean_title`) is added. `src/config.py`'s
   `WORK` and `src/vault_commit.py`'s `VAULT` honour `TRP_WORK` / `TRP_VAULT` so CLI subprocess
   tests never touch the real trees.
7. **§9, §12 empty table bodies.** acct ch05 has 15 `table` blocks with empty HTML (the VLM
   returned nothing; the crops exist). Checks record rows 0, cols 0, rectangular false; the
   renderer embeds the crop with a warning callout for inspection renders; the block stays
   unresolved until the reviewer patches it or gate 5 records the per-book fix (re-extraction
   with different table settings or a `set_html` budget, HANDOVER §8).
8. **§11 `review` key.** `checks` gains `textlayer_diff`; `headings.missing[*]` is `{title,
   page, kind, verdict, block, note}`; `footnotes` gains `dangling` and `unmatched[*]` is `{id,
   verdict, note}`; `unresolved[*]` is `{kind, ref, reason}`. `review crop --id` prints a crop
   path and counts the open; `finalize` exits 0 when certified, 3 when needs_attention, 1 on
   error.
9. **§3 facts.** PyMuPDF `rawdict` span flag bit 0 marks the footnote superscripts (bma page 4:
   `1`); omitting TEXT_PRESERVE_LIGATURES expands ops's two `ﬀ`; stats carries 267 soft-hyphen
   characters in `rawdict`; 46 of 61 footnote blocks open with `<sup>n</sup>`.
