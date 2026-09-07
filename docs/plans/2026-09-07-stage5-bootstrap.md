# Stage 5 bootstrap — design and plan drafting in a fresh session

Written 2026-09-07 after PR #1 merged stages 1–4 into `main` (`2f3a7d8`). This file carries the
exploration a fresh session would otherwise redo, fixes what is already decided, and lists the
questions the brainstorm must settle. The paste-able instruction is at the end.

## 1. Read in this order

1. `CLAUDE.md` — stack, hard rules, Superpowers deviations (brainstorming confirms HANDOVER and
   spends the session on open decisions; executing-plans with human checkpoints, never
   subagent-driven-development; no worktrees; the operator pushes).
2. This file.
3. `docs/design/HANDOVER.md` §1, §6 "Stage 5", §7 gates 4–6, §8, §9 — the fixed sketch.
4. `docs/plans/2026-09-06-stages-1-4-design.md` §1 (decision tables, incl. "Deferred to stage 5"),
   §6–§7 (what `guardrail.json` and `qa_report.json` contain), §11.
5. `docs/plans/2026-09-06-stages-1-4-plan.md` Addendum 3 — deferred items and engineering notes.
6. `metrics/hunk-stats-2026-09-06.md` (§4 mechanisms, §6 implications) and `metrics/gate3-bma.md`.
7. `src/blocks.py`, `src/qa_report.py`, `src/qa_schema.py` — the interfaces stage 5 consumes.

## 2. State

- `main` at `2f3a7d8`; 103 unit tests, ruff clean. Stages 1–4 complete; gates 1–3 passed.
- `work/<book>/ch05/` (all seven books) and `work/bma/ch06/` hold current `chapter.pdf`,
  `meta.json`, `chapter/hybrid_auto/`, `guardrail.json`, `qa_report.json`, `crops/`. No GPU or
  server is needed to design or test stage 5 against them; re-extraction (`FORCE=1`) needs
  `make serve` on GPU 0.
- `.claude/skills/chapter-review/` exists and is empty (`.gitkeep`). `src/vault_commit.py` does
  not exist. No stage-5 code has been written.
- The vault is not on this machine. `~/.claude.json` defines two `mcp-obsidian` servers
  (`obsidian`, `obsidian-01-foundations-of-modern-finance`) against an Obsidian Local REST API at
  `192.168.3.26:27123` (http), one API key per vault. Both failed to connect on 2026-09-07
  (host unreachable). Course vault name: `01-foundations-of-modern-finance`.

## 3. Fixed — confirm, do not relitigate

- HANDOVER §6 stage 5 rules: read `qa_report.json`, open only referenced crops and hunk contexts;
  adjudicate every hunk with the text layer winning unless the crop shows the layer is wrong;
  surgical patches, never regeneration; verify programmatically (LaTeX parses, table row/column
  counts match the crop, heading hierarchy matches the `meta.json` subtree); write per-item
  verdicts, patch count and effort notes back into `qa_report.json`; `status` becomes
  `certified` or `needs_attention`; then `vault_commit.py` writes note(s) + `assets/` with
  frontmatter `{book, chapter, course, source_pages, certified}`.
- Hard rules: text layer wins; VLM output only for table/formula/chart/figure bodies; stage-2
  outputs are never reshaped (patches live beside them); `qa_report.json` keeps the §6 schema
  (extra keys allowed — `qa_schema.validate` ignores them, see its docstring); only certified
  notes enter the vault; book PDFs and `work/` never enter git; fail loudly.
- Decided in the stages 1–4 design: one vault note per chapter *section* (outline level 3,
  plus end-matter entries — which ones is open); stages 1–4 stay per chapter, `meta.json`
  carries `sections` (number, title, pdf_page, printed_page, level) and `toc_subtree`
  (level 3 and 4 entries with pdf pages); heading hierarchy comes from `meta.json`, never from
  mineru (`title.level` is 1 for the chapter title and 2 for everything else).
- Skill location: `.claude/skills/chapter-review/SKILL.md` (CLAUDE.md layout; HANDOVER's
  `review/REVIEW_SKILL.md` is the older name).
- Gate 4: certified output in the vault that renders in Obsidian mobile (math, tables, figures).
  Gate 5: benchmark pass, one chapter per book, recording hunk count, formula error rate,
  table cell accuracy on 2–3 tables, review tokens, wall time.

## 4. Facts the design can rest on (measured)

- Hunk population, eight chapters (622 hunks after gate-3 tuning): ~half are same-letters or
  pure moves and resolve mechanically; ~40 % anchor inline-math blocks; the rest (~110) need
  eyes, of which ~60 are genuine defects, one per ~6 pages. Dominant defect: mineru drops the
  last glyph of a right-justified line or a trailing footnote superscript (its span assignment
  keeps a glyph only if the centre is strictly inside the OCR detection span).
- "Accept the PDF text" is right for split words, md-joined words, dropped punctuation and
  dashes; wrong where the PDF side is defective: symbol-font math in stats (Greek and operators
  encoded as Latin), ornaments (`®`, drawn bullets, chapter numerals), one plain-line-break soft
  hyphen. Stripping whitespace + Unicode punctuation while keeping symbols (category S) is the
  safe equality. Inline-math anchors need "keep LaTeX, mark verified", not text replacement.
- Junk regions (buttons, logos, `#` margin icons, badges, drawn bullets) share one discriminator:
  md words with no text-layer words inside the block bbox. bma's `page_aside_text` blocks are
  17 in ch05: four 1-character icons, the rest 15–32-character margin callouts.
- Cross-page paragraph merges are correct output (the continuation belongs to the paragraph);
  mineru leaves an empty paragraph block at the next page top. Section slicing must therefore
  assign a merged block by its own page/bbox, not by where its words print.
- Reflowed e-books (acct, ops) label body text `page_header`/`page_footer` (23 and 3 suspects
  in ch05) and ops injects `Page N` folios into paragraphs — stage 5 must render suspects as
  body text and strip injected folios.
- Drop caps are missing on both bma openers; duplicated spans occur (bma ch06 one paragraph
  ×15, ops folios ×2); ligature `ﬀ` arrives as `f` in two ops captions.
- mineru's crops exist for every VLM body (`Block.crop` under `hybrid_auto/images/`); stage 4
  renders `crops/<id>.png` only for suspects and spot checks.

## 5. Open decisions — the brainstorm's agenda (one question at a time)

1. **Vault transport.** Local REST API through `mcp-obsidian`/HTTP from the server box vs. a
   staging directory the operator syncs vs. a local clone of the vault. What "certified" means
   when the host is down (stage-5 output must not depend on the vault being reachable).
2. **Note layout.** Which level-3 entries become notes (numbered sections only vs. every entry;
   grouping of Key Takeaways / Further Reading / Problem Sets / Solutions / Mini-Case); folder
   and file naming per book/chapter; frontmatter beyond the fixed keys; wikilinks to course and
   lecture notes; how `assets/` is laid out and which crops are copied (tables: markdown + crop?
   formulas: LaTeX only? charts: crop, and keep/drop/collapse the generated data table?).
3. **Pre-pass over `diff_hunks`.** Where auto-patches live (a patch list keyed by block id and
   span, applied at render time — never edits to `content_list_v2.json`); the rendering
   normalization for accepted PDF text (raw words minus soft hyphens and line-end hyphens; keep
   quotes and ligature folding?); inline-math verification; chapter-wide move filter (one
   insertion may pair with several deletions); junk drop by the no-text-layer-words test.
4. **Review skill mechanics.** Input budget (which crops open, which hunks are shown); verdict
   schema written into `qa_report.json` (extra keys); programmatic checks — LaTeX parsing
   without Node (`pylatexenc`/`latex2mathml`/matplotlib mathtext are candidates; KaTeX needs
   Node), table row/column counts from the HTML vs. what the crop shows, heading tree vs.
   `meta.json`; `certified` vs `needs_attention` semantics; effort/token logging; how a chapter
   review is launched (one Claude Code session per chapter; an agent fleet for the benchmark
   pass — per-chapter review is independent work with a fixed rubric).
5. **Rendering policy.** Footnotes (`[^n]` at section end?); `page_aside_text` (drop 1-char
   icons, render callouts as Obsidian callouts?); running-matter suspects as body text; display
   math as `$$…$$`, inline as `$…$`; tables as Markdown or HTML when nested/complex
   (`table_type`); figures as `![[assets/…]]`; drop-cap and duplicate repairs as patches.
6. **Gate 4 verification without a phone in the loop.** What can be checked mechanically for
   Obsidian rendering (delimiters balanced, pipes per row, embeds resolve, frontmatter valid)
   and what the operator checks once on mobile.
7. **mineru's line-final glyph loss.** Patch locally (a span-padding fix or upstream report)
   before whole-book runs, or accept it as a stage-5 patch class. Decide before gate 5.
8. **Benchmark pass shape (gate 5).** Which seven chapters (ch05 of each book is extracted);
   which metrics are automatic vs. spot-checked; where they are recorded (`metrics/`).

## 6. How to run the session

- `superpowers:brainstorming`, architectural path, with CLAUDE.md's deviations: confirm §3,
  ask §5 one question at a time, propose 2–3 approaches where they differ materially (vault
  transport, note layout, pre-pass placement), present the design in sections, write it to
  `docs/plans/2026-09-07-stage5-design.md` (not `docs/superpowers/specs/`), self-review, wait
  for the operator's review.
- Then `superpowers:writing-plans` → `docs/plans/2026-09-07-stage5-plan.md`. Each task's
  verification is a gate criterion or a measured number on the eight work dirs, not "tests
  pass". Build order: pre-pass and patch model (unit-testable against `work/bma/ch05`) →
  section slicing and rendering → review skill → `vault_commit.py` → gate 4 on bma ch05/ch06
  → benchmark pass.
- Execution later uses `superpowers:executing-plans` with human checkpoints at gates 4 and 5.
  Agent fleets fit per-chapter review runs; pipeline runs and statistics stay in one
  deterministic script.
- Work on a branch (`stage-5`) in the main checkout; `books/`, `work/`, `tests/fixtures/` are
  untracked. Ruff formats Python blocks inside Markdown and rejects raw U+200B in source; every
  new normalization rule is RED-first from a captured string; never fold a real defect; never
  weaken the control-page assertion (48/48 blocks, 0 hunks). The operator pushes.

## 7. Bootstrap instruction (paste into the fresh session)

```text
Start the stage-5 design for the textbook retrieval pipeline. Read, in this order:
  1. CLAUDE.md
  2. docs/plans/2026-09-07-stage5-bootstrap.md   ← state, fixed items, facts, open questions
  3. docs/design/HANDOVER.md §1, §6 "Stage 5", §7 gates 4–6, §8, §9
  4. docs/plans/2026-09-06-stages-1-4-design.md §1, §6–§7, §11
  5. docs/plans/2026-09-06-stages-1-4-plan.md — Addendum 3 only
  6. metrics/hunk-stats-2026-09-06.md §4 and §6; metrics/gate3-bma.md
  7. src/blocks.py, src/qa_report.py, src/qa_schema.py
Then use superpowers:brainstorming on the architectural path with the CLAUDE.md deviations:
treat bootstrap §3 as fixed and confirm it in one message; work through bootstrap §5 one
question at a time, leading with your recommendation; propose 2–3 approaches only where
they differ materially; present the design in sections and wait for my yes after each; write
the design to docs/plans/2026-09-07-stage5-design.md, self-review it, and stop for my review.
After my approval use superpowers:writing-plans to write docs/plans/2026-09-07-stage5-plan.md
whose task verifications are gate-4/gate-5 criteria measured on the existing work/ dirs.
Constraints: branch `stage-5` in the main checkout, no worktree; no code before the plan is
approved; no GPU or server needed (all eight sample chapters are extracted under work/); the
vault host 192.168.3.26 may be unreachable — design so certification does not depend on it;
uv run for everything; ruff-clean Markdown; I push.
```
