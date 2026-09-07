# Stage 5 handover — gate 5 (Task 13) and Task 14 in a fresh session

Written 2026-09-07 after gate 4 closed (`metrics/gate4-bma.md`, commit `10430e4`). It replaces
`docs/plans/2026-09-07-stage5-handover.md`, retired into the stage-5 plan's gate-4 addendum. Retire
this file the same way when gate 5 closes.

## 1. Read in this order

1. `CLAUDE.md` — stack, hard rules, Superpowers deviations (executing-plans with operator
   checkpoints, never subagent-driven-development; no worktrees; the operator pushes to git and
   to the vault unless they say otherwise in the session).
2. This file.
3. `docs/plans/2026-09-07-stage5-plan.md` — Task 13 and Task 14 only (everything before is ticked
   and carries "Measured 2026-09-07" notes); the Task 1, 3, 5, 8, 9, 10 addenda list what changed
   against the plan text. Then `docs/plans/2026-09-07-stage5-design.md` §1, §15 (gates and
   evidence), §16 and the Amendments.
4. `metrics/gate4-bma.md` — the gate-4 record; its table is the shape the gate-5 report extends.
5. On demand: `src/review.py` (Chapter, CLI, finalize), `src/prepass.py`, `src/review_checks.py`,
   `src/vault_commit.py`, `src/vault_checks.py`, `tests/helpers.py` (`make_work_dir`,
   `work_chapter_sandbox`), `.claude/skills/chapter-review/SKILL.md`.

## 2. State

- Branch `stage-5` in the main checkout, pushed to `origin/stage-5` (this commit). `main` is
  `2f3a7d8` (PR #1, stages 1–4). Tasks 1–12 are done: 21 stage-5 commits from `3733be8`
  (scaffolding) to `10430e4` (gate 4). Unit tier 226 passed, 5 deselected (4 `integration`, 1
  `vault`); ruff clean. Plan: 73 steps ticked, 11 open (all in Tasks 13–14).
- Makefile stage-5 targets exist (Task 14 Step 1 pulled forward): `prepass`, `review-checks`,
  `review`, `finalize`, `render`, `check` (`PARSED=1`, `ROOT`, `SECTION`), `push`. Missing:
  `benchmark-report` (Task 13's script). CLAUDE.md Commands are synced; Layout and Hard rules are
  not (Task 14 Step 3).
- `work/`: bma ch05 and ch06 `certified`, pushed to `raw/textbooks/bma/ch05/` (20 files) and
  `ch06/` (12 files), `check PARSED=1` OK, mobile checklist 7/7. acct, bkm, corpfin, ops, stats,
  strat ch05: `pending_review` with the pre-pass run (`patches.json` present, `review` key
  present, `effort.started` empty). The operator also extracted bkm ch15, ch20–23 and bma ch09;
  bkm ch15 and bma ch09 carry a pre-pass `review` key. They are **not** in the gate-5 set —
  `benchmark_report.py` reads every work dir with a `review` key, so filter or note them.
- `vault/`: staging trees for bma ch05 and ch06 only (gitignored). The Obsidian vault
  `01-foundations-of-modern-finance` holds `raw/textbooks/bma/{ch05,ch06}/`; no probe residue.
- Vault access: Local REST API at `http://192.168.3.26:27123`, up only while the operator has
  Obsidian open. The plugin (4.1.3) renders no HTML; `check --parsed` compares its `note+json`
  (frontmatter, content, *resolved* links/embeds) and `document-map+json` (unique `::` heading
  paths, parent = nearest smaller level). Env recipe, never printing the key:

  ```bash
  eval "$(python3 -c "
  import json, shlex
  from pathlib import Path
  env = json.loads(Path.home().joinpath('.claude.json').read_text())['mcpServers']['obsidian-01-foundations-of-modern-finance']['env']
  for k in ('OBSIDIAN_API_KEY', 'OBSIDIAN_HOST', 'OBSIDIAN_PORT', 'OBSIDIAN_PROTOCOL'): print(f'export {k}={shlex.quote(env[k])}')
  ")"
  ```

## 3. How to execute Task 13

- `superpowers:executing-plans`, one task at a time, RED first, measured numbers pasted into the
  plan step, plan `ruff format`ed, code + plan committed together. Batches: Task 13 Steps 1–4 (no
  host, no session), then Step 5 (operator sessions), Step 6, Step 7; then Task 14.
- Step 1–3: `scripts/benchmark_report.py` + test. Write it against the sandbox helper
  (`work_chapter_sandbox`) or `make_work_dir`; never against the real `work/`. Scope the report to
  the plan's eight chapters (see §2 about the extra work dirs) or add a `--chapters` filter.
- Step 4: bkm and strat `toc.patches` renames (`rename` rule: `level`, `match`, `replace`), dry run
  then `--apply` with `scripts/patch_toc.py`, then `make split BOOK=… CH=5` (rewrites `meta.json`;
  the content list is untouched so `patches.json` stays bound). Then
  `uv run pytest tests/test_sections.py -q` — `test_bkm_and_strat_need_outline_renames_until_gate_5`
  must pass through its `else` branch and `test_real_chapters_resolve` should gain bkm and strat
  rows (add them: bkm `{"heading": 9}` or whatever `resolve` reports, strat likewise; strat's five
  Strategy Spotlight subheadings are `page_header` triples → `not_a_heading` verdicts in review).
- Step 5: the operator runs six `/chapter-review <book> 5` sessions (acct bkm corpfin ops stats
  strat), **one writer per work dir at a time** — never run `make review`, `pytest` or any
  `src.review` write on a chapter while a session owns it (gate 4 lost 13 verdicts to exactly that;
  the pre-pass now keeps `rule: manual` entries and `workdir` tests are sandboxed, but the rule
  stands). Pushes need the operator's word per chapter. `/cost` is unavailable on the
  subscription: no token figures. Then `uv run python scripts/benchmark_report.py`, the per-book
  notes and the calibration sample (2–3 tables + 3 formulas per chapter via `spot_sample`).
- acct decision (plan Step 5 expects it written down, not silently picked): 15 `table` blocks have
  empty HTML → either re-extraction with different table settings (needs `make serve` on GPU 0,
  invalidates `patches.json` by design) or a reviewer `set_html` budget for 15 tables.
- Step 6: `metrics/mineru-glyph-loss-report.md` (synthetic reproduction; no book content).
- Task 14: `benchmark-report` target + help line (the `make help` grep then prints 7), CLAUDE.md
  Layout (all stage-5 modules, skill files, `vault/`, `patches.json`, metrics files) and Hard
  rules, and the design Amendments listed in §5. Then retire this file into a plan addendum.

## 4. Expected numbers (measured 2026-09-07; compare, do not copy)

- Pre-pass (622 hunks): acct 38 (needs_eyes 11), bkm 111 (29), bma ch05 57 (13), bma ch06 82 (8),
  corpfin 40 (7), ops 81 (30), stats 140 (43), strat 73 (12). Classes fleet-wide: same_letters
  159, inline_math 165, move 84, edge_glyph 34, junk 15, duplicate 5 (bma ch06 only), folio 7 (ops
  only), needs_eyes 153. Residue by note: inline math differs 63, one-sided core 44, masking-gap
  anchor 20, letters differ 10, non-unique window 15, missing anchor 1.
- Review checks: bma ch05 formulas 20 (19 text-layer, 18 parse), tables 38 (32 bag-equal, 38
  rectangular); stats formulas 78 → `null` (`review.textlayer_math: false`), tables 40 (25),
  subheadings 12/14, 1 unmatched footnote; acct tables 80 (15 empty, 65 rectangular, 45
  bag-equal), subheadings all found with heading runs.
- Sections: bma 9 heading; acct 9 + 1 first_child; ops 9 + 1 chapter_start; corpfin 7; stats 7;
  bkm/strat raise until the renames.
- Gate 4 as calibration for a review session: bma ch05 87 crops, 16 review patches, 38 min;
  ch06 81 crops, 17 patches, 14 min; tier A 65/67 and 42/50 matches; every mismatch was patched.
- Footnotes: bkm 14 definitions with 3 unreferenced (blocking until adjudicated), corpfin 6 with 2,
  stats 1 with 1; acct and strat are endnote books (0 definitions, dangling only).

## 5. Decisions pending and design amendments due at Task 14

Write these into `docs/plans/2026-09-07-stage5-design.md` Amendments (all measured, all in the
plan's "Measured"/addendum notes):

1. Decision 6 / §10: the REST API renders no HTML; `check --parsed` replaces the rendered count;
   rendering fidelity is the phone. Document-map path rules (unique, `::`, nearest smaller level).
2. Amendment 5: bma ch06 `p026-b007` is line-wise duplication (7 segments × 15), not a whole-block
   period; the collapser confirms against the bbox text layer. Junk hunks may span several
   unmatched blocks (`Verdict.also`).
3. §6/§11 patch ops: `set_inline_math` (reviewer-only) added.
4. §9 rendering: currency `$` escaped as `\$` in text spans, captions and pipe cells (LaTeX pairs
   kept); the space after an inline formula restored; multi-line asides quoted per line; `%%`
   pairs and the battery's ordered inline-`$` pairing.
5. §9 rule 3: `chapter_start` requires a level-1 chapter title on the page.
6. §7: `latex_ok` counts delimited `\left`/`\right`, checks unescaped `$` before the parser;
   table bags fold after `punctuation_variants`.
7. §8 / skill: one writer per work dir; the pre-pass keeps `rule: manual` hunk entries; `workdir`
   tests are sandboxed; `make finalize` exits 2 on `needs_attention` (read the printed status).
8. Known limits carried: `$…$` inside complex-table HTML shows literally in Obsidian; mineru
   types some ornaments/logo text as `title` (`### connect`); acct's 15 empty tables.

## 6. Engineering notes

- The Bash tool's working directory persists across calls: never `cd` into a subdirectory (a
  chain ran from `.claude/skills/chapter-review/` and silently did nothing). One heredoc per
  command line, or write scripts to the scratchpad first; heredoc bodies attach in operator order.
- Heredocs must write `­` / `​` as escapes. The plan's code blocks carry
  Markdown-invisible lint (PLW1510, SIM905, I001, F821 on fragments): `ruff check --fix` after
  copying and mirror the fix into the block.
- `ruff format --check .` formats Python blocks in Markdown: keep the handover and metrics files
  free of ```python fences unless formatted.
- `make` exits 2 on any failing recipe; `uv run python -m src.review finalize` exits 0/3/1.
- GNU `set -e` is not reliable inside the tool's chained commands; use `&&` chains and print a
  marker after each step, then verify with `git log`/`git status`.
- `Chapter.save()` validates the whole report and applies the whole patch list before writing;
  a refused patch writes nothing. `patches.json` is bound to the content list's sha256 —
  re-extraction invalidates it by design.

## 7. Bootstrap instruction (paste into the fresh session)

```text
Continue stage 5 of the textbook retrieval pipeline at Task 13 (gate 5). Read, in this order:
  1. CLAUDE.md
  2. docs/plans/2026-09-07-stage5-gate5-handover.md   ← state, protocol, expected numbers
  3. docs/plans/2026-09-07-stage5-plan.md — Tasks 13 and 14 only, plus the Task 1/3/5/8/9/10 addenda
  4. docs/plans/2026-09-07-stage5-design.md §1, §15, §16 and the Amendments
  5. metrics/gate4-bma.md
Then use superpowers:executing-plans on docs/plans/2026-09-07-stage5-plan.md with the CLAUDE.md
deviations: batches Task 13 Steps 1–4, then Step 5 (my six /chapter-review sessions; you never
write to a work dir while a session owns it), then Steps 6–7, then Task 14; stop for my checkpoint
after each batch; RED first for every step; paste the measured numbers into the plan's
verification steps and commit them with the code; ruff-clean Python and Markdown.
Constraints: branch `stage-5` in the main checkout, no worktree; uv run for everything; never cd
into a subdirectory; no GPU or server unless I say so (the acct re-extraction option); the vault
host 192.168.3.26 is up only when I say so and you push a chapter only on my word; never push to
git — I push. Start with Task 13 Step 1 and report each batch as counts, not prose.
```
