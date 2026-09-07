# Stage 5 handover — implementing the plan in a fresh session

Written 2026-09-07 after the stage-5 design and plan were approved. This file carries the
session state, the reading order, the execution protocol and the measured numbers a fresh
session needs to execute `docs/plans/2026-09-07-stage5-plan.md`. It retires the stage-5
bootstrap note (its fixed items are design §1, its measured facts design §3 and Amendments).
Retire this file into a plan addendum when gate 5 closes, as the gate-3 handover was.

## 1. Read in this order

1. `CLAUDE.md` — stack, hard rules, Superpowers deviations (executing-plans with human
   checkpoints, never subagent-driven-development; no worktrees; the operator pushes).
2. This file.
3. `docs/plans/2026-09-07-stage5-design.md` §1 (decisions), §2 (terms), Amendments (measured
   corrections the plan already implements); the other sections on demand per task.
4. `docs/plans/2026-09-07-stage5-plan.md` — header, Global Constraints, File structure; then
   one task at a time, in order.
5. `src/blocks.py`, `src/normalize.py`, `src/guardrail.py` (lines 26–100: `block_masks`,
   `pdf_page_text`, `block_text`, `block_tokens`), `src/qa_report.py`, `src/qa_schema.py`,
   `tests/helpers.py`, `tests/conftest.py` — the interfaces stage 5 consumes and the test style.

## 2. State

- Branch `stage-5` in the main checkout, pushed to `origin/stage-5`. `main` is `2f3a7d8` (PR #1,
  stages 1–4). Stage-5 commits: `f33853d` design, `2dae0c2` plan + design Amendments, then this
  handover. 103 unit tests green (`uv run pytest`, 4 integration tests deselected), ruff clean.
- No stage-5 code exists. `.claude/skills/chapter-review/` holds only `.gitkeep`. `vault/` does
  not exist and is not yet gitignored (plan Task 1 adds it).
- `work/<book>/ch05/` for all seven books and `work/bma/ch06/` hold current `chapter.pdf`,
  `meta.json`, `chapter/hybrid_auto/`, `guardrail.json`, `qa_report.json` (status
  `pending_review`, no `review` key yet) and `crops/`. No GPU or MinerU server is needed for
  Tasks 1–14; re-extraction (`make chapter … FORCE=1`) would need `make serve` on GPU 0 and
  would invalidate `patches.json` by design (sha256 binding).
- The vault (`01-foundations-of-modern-finance`) is on another machine. Its Local REST API at
  `http://192.168.3.26:27123` answers only while the operator has Obsidian open there. Of the
  two `mcp-obsidian` entries in `~/.claude.json`, only the key of
  `obsidian-01-foundations-of-modern-finance` authenticates; the generic `obsidian` key is for
  a different vault. The MCP servers may fail to connect in the session; the plan uses direct
  HTTP (`requests`) and needs `OBSIDIAN_HOST`, `OBSIDIAN_PORT`, `OBSIDIAN_API_KEY` only for
  Task 10 and the gate pushes. Read the key from `~/.claude.json` in a script; never print it.
- Vault layout seen 2026-09-07: `raw/{transcripts,html,problems}/`, `notes/<NN-module>/`,
  `references/`. Push root default `raw/textbooks/`.

## 3. How to execute

- `superpowers:executing-plans`. Batches with a human checkpoint after each: Tasks 1–3
  (scaffolding, text layer, patches), Tasks 4–6 (review record and CLI, pre-pass, sections),
  Tasks 7–9 (renderer, checks, staging tree and finalize), Task 10 (needs the vault host open),
  Task 11 (the skill; dry run is a `/chapter-review bma 5` session run by the operator), Task 12
  (gate 4, operator's mobile pass), Task 13 (gate 5 fleet + benchmark report), Task 14 (docs).
- Per task: write the failing test exactly as the plan shows, run it, implement, run
  `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`, paste the measured
  numbers into the task's verification step **in the plan file itself**, commit code and plan
  together. The plan's Python blocks are ruff-formatted; after editing the plan run
  `uv run ruff format docs/plans/2026-09-07-stage5-plan.md`. Extract code blocks with
  `sed -n '<start>,<end>p'` by fence line numbers when copying, and keep `­` / `​`
  as escapes, never as raw characters (PLE2515 rejects raw U+200B in source).
- Where a plan test pins a number (`>= 9`, `<= 20`, `== 57`), the bound comes from a measurement
  listed in §4. If a real-chapter test fails, look at the data before loosening the bound, and
  record why in the plan step.
- Commits are local. The operator pushes. Nothing is pushed to the vault before gate 4.
- A fresh reviewer session for Task 11 / gate 4 / gate 5 opens the repo and runs
  `/chapter-review <book> <chapter>`; the fleet for gate 5 dispatches one such session per
  chapter. Tier A uses `model: sonnet`; Workflow needs the operator's opt-in per session, Agent
  fan-out is the fallback.

## 4. Expected numbers (measured 2026-09-07; compare, do not copy)

- Hunks (`guardrail.json`): acct 38, bkm 111, bma ch05 57, bma ch06 82, corpfin 40, ops 81,
  stats 140, strat 73 = 622. Fold-equal pairs (same letters after NFKC, whitespace and
  punctuation removed, symbols kept, casefolded) when tested before the inline-math class: acct
  10, bkm 53, bma ch05 31, bma ch06 53, corpfin 23, ops 22, stats 87, strat 45 = 324; the
  plan tests inline-math blocks first, so `same_letters` may come out a little lower and
  `inline_math` higher. Hunk contexts: first three tokens equal in 531 of 622, last three in 496.
- Flagged blocks (`qa_report.json`): acct 111, bkm 76, bma ch05 67, bma ch06 50, corpfin 79, ops
  63, stats 126, strat 12 = 584; every crop file exists. Running-matter suspects: acct 23, bma
  ch05 1, ops 3, stats 4, strat 6.
- Junk with no text-layer words in the bbox: bma ch05 `p009-b015`, `p009-b019` (`#` icons); the
  Connect logo `p021-b005` has a `®` glyph in the text layer and is **not** junk (tier B). bma
  ch06 `p026-b007`: one paragraph duplicated, five hunks. ops: 7 paragraphs with `Page N Page N`
  injected.
- Text-layer checks on bma ch05: formulas 19 of 20 letters-equal; tables 9 of 38 bag-equal
  before `$…$` flattening (the differences were `$C_0$` vs `C0` and `...` vs `. . .`); table
  `p001-b006` is exactly equal. stats: 1 of 78 formulas (symbol fonts → `textlayer_math: false`).
  acct: 15 `table` blocks with empty `html`.
- Section anchors after the amended rules: bma ch05 9 via headings; acct 9 via headings (one on
  a `page_header`, `p006-b008`) + 1 `first_child` (End-of-Chapter → ETHICS in the Real World);
  ops 9 + 1 `chapter_start` (Introduction); corpfin 7; stats 7; bkm and strat raise until the
  gate-5 outline renames ("End of Chapter Material" → "Summary"; "Experiential Exercise" →
  "Experiential Exercises"). Subheadings found with the old single-block fold: bkm 23/23, bma
  ch05 12/12, bma ch06 22/22, corpfin 11/11, ops 4/4, stats 12/14, acct 8/10, strat 0/5 (the
  five Strategy Spotlight boxes are `page_header` triples → `not_a_heading` verdicts).
- Footnotes: 61 `page_footnote` blocks, 46 open with `<sup>n</sup>`. Definitions / references
  by the preceding-character rule: bma ch05 11/12 (ref 16 dangling), bma ch06 13/13, bkm 14/17
  (defs 4, 8, 9 unreferenced → blocking until adjudicated; refs 2, 7, 10, 17 dangling),
  corpfin 6/14 (defs 1, 8 unreferenced), stats 2/1 (def 1 unreferenced), acct 0/16 and strat
  0/74 (endnotes, dangling only).
- Layout facts: 41 `page_aside_text` blocks in 11 consecutive runs (bma ch05 17, ch06 23, bkm 1);
  62 decorative images without `content`, 4 captioned, 58 under 1.5 % of the page, none larger.
  PyMuPDF `rawdict` span flag bit 0 marks the footnote superscripts (bma page 4: `1`); omitting
  `TEXT_PRESERVE_LIGATURES` expands ops's two `ﬀ`; stats has 267 soft-hyphen characters; bma's
  drop cap `A` is a 37 pt single-letter word.
- Vault REST API (plugin 4.1.3, Obsidian 1.13.7): PUT into a missing nested folder → 204 and
  parents created; PNG round-trips byte for byte; `Accept: application/vnd.olrapi.note+json`
  returns parsed frontmatter; directory GET → `{"files": [...]}`; `DELETE ?permanent=true` → 204
  and emptied folders vanish. The `text/html` rendering's class names are not yet observed
  (plan Task 10 Step 6).

## 5. Engineering notes

- `ruff format --check .` formats Python blocks inside Markdown; `ruff check` does not lint
  Markdown, so unused imports inside plan code blocks surface only once copied into `.py` files
  (the plan was swept for them on 2026-09-07).
- `src/extract.hybrid_auto_dir(out_dir)` is `work/<book>/<chNN>/chapter/hybrid_auto`; the stem
  is `chapter`. `tests/helpers.make_work_dir` (plan Task 4) builds a fake work dir and redirects
  `src.config.WORK`, `src.vault_commit.VAULT`, `TRP_WORK` and `TRP_VAULT`; tests must never
  touch the real `work/` or `vault/`.
- Plain `uv run` is fine on this box (`--no-sync` only matters for server commands).
- `scripts/patch_toc.py <book>` dry-runs `toc.patches`; `--apply` writes the outline into the
  PDF; `make split BOOK=… CH=5` then rewrites `meta.json` without touching the content list, so
  `patches.json` stays bound. The `rename` rule takes `level`, `match` (regex), `replace`.
- The gate-3 numbers to preserve: control page 48/48 blocks, 0 hunks; bma ch05 57 hunks, ch06 82.
- Metrics files hold counts and block ids only; never book text, hunk text or note text.

## 6. Bootstrap instruction (paste into the fresh session)

```text
Implement stage 5 of the textbook retrieval pipeline. Read, in this order:
  1. CLAUDE.md
  2. docs/plans/2026-09-07-stage5-handover.md   ← state, protocol, expected numbers
  3. docs/plans/2026-09-07-stage5-design.md §1, §2 and the Amendments section
  4. docs/plans/2026-09-07-stage5-plan.md — header, Global Constraints, File structure
Then use superpowers:executing-plans on docs/plans/2026-09-07-stage5-plan.md with the
CLAUDE.md deviations: batches Tasks 1–3, 4–6, 7–9, then 10, 11, 12, 13, 14, stopping for my
checkpoint after each batch; RED first for every step; paste the measured numbers into the
plan's verification steps and commit them with the code; ruff-clean Python and Markdown.
Constraints: branch `stage-5` in the main checkout, no worktree; uv run for everything; no GPU
or server; the vault host 192.168.3.26 is up only when I say so (Task 10 and the gates);
never push to git or to the vault — I push and I run the /chapter-review sessions.
Start with Task 1 and report each batch as counts, not prose.
```
