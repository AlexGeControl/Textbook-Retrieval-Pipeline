# Gate 3 handover — stages 1–4 on branch `stages-1-4`

Written 2026-09-06 at the end of the session that passed gate 2, moved the anchor to
`content_list_v2` and dry-ran Tasks 8–10. A fresh session executes Tasks 8 → 9 → 10 → 11 → 12 of
`docs/plans/2026-09-06-stages-1-4-plan.md` from this file. Nothing here overrides CLAUDE.md, the
design doc or the plan; it tells you where they stand and what to expect.

## 0. Read in this order

1. `CLAUDE.md` — stack, hard rules, project deviations from Superpowers.
2. This file.
3. `docs/plans/2026-09-06-stages-1-4-design.md` — §6 (guardrail) and §7 (qa_report) are the current
   spec, amended for the v2 anchor; §1 decision table and §2 facts explain why.
4. `docs/plans/2026-09-06-stages-1-4-plan.md` — Tasks 1–7 and 7b are done. Read Addendum 2 at the
   end, then Tasks 8–12. Their Python blocks are byte-faithful copies of code that was dry-run green
   against the fixture cache; execute them RED → GREEN → commit, do not redesign them.
5. `metrics/block-types-2026-09-06.md` — the seven-book evidence behind the v2 decisions.

## 1. State at handover

- Branch `stages-1-4` in the main checkout (no worktree — `books/`, `work/`, `tests/fixtures/` are
  untracked and would not exist in one). 22+ commits ahead of `main`. Tree clean.
- `uv run pytest -q` → **73 passed, 4 deselected**. `uv run ruff check . && uv run ruff format --check .`
  clean.
- Done and committed: Tasks 1–7 (gate 2 passed on bma ch05/ch06, `375de18`); `check_outputs` counts
  pages from `_middle.json.pdf_info` (`85bc35e`); block-type evidence (`095cbc1`, `e274536`); design
  + plan amended for the v2 anchor (`6c617f2`, `8bf56f9`); Task 7b — `src/blocks.py` over
  `_content_list_v2.json` (`b459031`).
- Not yet built: `src/normalize.py`, `src/guardrail.py`, `src/qa_schema.py`, `src/qa_report.py`,
  their tests, the Makefile `guardrail`/`qa_report`/`chapter` targets, `metrics/gate3-bma.md`, the
  CLAUDE.md sync (Task 12).
- On this machine only (gitignored): `books/<id>/<id>.pdf` (stats and corpfin outlines patched in
  place, `.orig.pdf` kept), `work/bma/ch05` and `work/bma/ch06` fully extracted (stage 2 outputs
  under `chapter/hybrid_auto/`, 30 and 35 pages), `work/<book>/ch05` for the other six books,
  `tests/fixtures/{bkm,bma}/*.pdf` and `tests/fixtures/cache/` (four sets, v1 + v2 content lists).
  Tasks 8–11 reuse the bma extractions and need **no GPU**; `make extract` takes the reuse path.
- vLLM server (`make serve`, GPU 0, :30000) is needed only to re-extract (`FORCE=1`) or to
  regenerate the fixture cache (`uv run pytest -m integration`). Do neither unless a gate demands it.

## 2. What gate 3 is (design §10)

For **bma ch05 and ch06**: `guardrail.json.counts`, a hand classification of every plain-text hunk
(spurious vs. real) with spurious < ~10 per chapter after tuning, `qa_report.json` passing
`qa_schema.validate`, and the counts plus the number of `running_matter_suspect` flags pasted into
`metrics/gate3-bma.md`. The operator signs off on the classification before gate 3 is declared.

## 3. Execution order and stop points

| step | what | expected | commit |
|---|---|---|---|
| Task 8 | `src/normalize.py` + tests | RED = ImportError; GREEN = 12 passed; tier 85 | yes |
| Task 9 | `src/guardrail.py` + tests | RED = ImportError; GREEN = 8 passed; control page 48/48 blocks, 0 hunks, 2495 = 2495 tokens; table 4 hunks, formula 3 (2 inline-math), chart 3; tier 93 | yes |
| Task 10 | `src/qa_schema.py`, `src/qa_report.py` + tests | RED = ImportError; GREEN = 7 passed; tier 100 | yes |
| Task 11 §1–3 | Makefile targets + header comment fix; `make chapter BOOK=bma CH=5` and `CH=6`; dump all hunks to `work/gate3/` | extraction reused; guardrail and qa_report print counts | not yet |
| Task 11 §4 | classify every hunk; tune RED-first | see §5 below | per rule, or once at the end |
| **STOP** | paste the classification table + counts + suspects for both chapters | operator go | — |
| Task 11 §5–7 | `metrics/gate3-bma.md`, validate both reports, commit | gate 3 declared | yes |
| Task 12 | CLAUDE.md sync (incl. the v2 Hard-rules bullet) | tier green, lint clean | yes |

Then stop: stage 5, `vault_commit.py`, per-section slicing and the benchmark pass are the next plan.

## 4. Numbers to expect (drift detectors)

- bma ch05 (v2): 450 blocks / 30 pages — paragraph 202, title 49, list 22, table 38 (23 complex),
  equation_interline 20, chart 6, image 7 (2 with `content`), page_header 39, page_number 30,
  page_footnote 20, page_aside_text 17; 17 `equation_inline` spans in 11 blocks; VLM set 66, every
  crop present; running-matter suspects 1 (a boxed-feature heading).
- bma ch06 (v2): 521 / 35 — paragraph 268, title 57, list 30, table 31 (18 complex),
  equation_interline 18, chart 1, image 4, page_header 41, page_number 35, page_footnote 13,
  page_aside_text 23; 10 spans in 6 blocks; VLM set 50; suspects 0.
- Text-layer facts for bma ch05 (design §2): 69 soft hyphens, 464 thin/en/em spaces, 266 tabs, 139
  curly quotes, 63 `●` bullets, 4 hard line-end hyphens; running head alternates folio / `Chapter 5
  Title`; footnotes 8 pt. Rules 2–6 exist for these; expect the residue to be small.
- If the fixture numbers in §3 do not reproduce, the cache or the code drifted — stop and find out
  which before tuning anything.

## 5. Hunk classification protocol (Task 11 Step 4, restated)

Read every hunk. Bucket it:

- **spurious / normalization** — same words, different rendering. Add the captured string as a
  failing test in `tests/test_normalize.py`, append a rule (both tuples unless md-only), make it
  pass, log the rule in `metrics/gate3-bma.md`. Never reorder existing rules silently.
- **spurious / masking** — text-layer words of a table, figure, caption or display formula that sit
  outside the block bbox. Failing test in `tests/test_guardrail.py` first; smallest change to
  `block_masks` (padding) that fixes it.
- **inline math** — the owning block has an `equation_inline` span; already counted in
  `hunks_inline_math`. Leave it: review item, not false positive. If dozens appear, a RED-first
  rule removing spaces around `= + < >` on both sides is the anticipated fix.
- **real** — words missing, duplicated or altered in mineru's output. Leave it; count it. Known
  classes: words split at former hyphenation points (`capi tal`, `inven tory`), dropped characters
  (`ou company`), an em dash rendered `- `.

Do not fold real defects. Do not weaken the control-page assertion (`hunks == 0`, `unmatched == 0`).
Rule 7 (`join_letter_spaced_caps`) is already in; it came from the control page's tracked `PART III`.

## 6. Working agreements (operator-confirmed)

- `superpowers:executing-plans` with human checkpoints at the gates; single operator, GPU server in
  the loop; not subagent-driven-development.
- RED → GREEN → commit per task; `uv run pytest`, `uv run ruff check .` and
  `uv run ruff format --check .` before every commit. **ruff formats Python blocks inside Markdown**,
  so any plan/design/handover edit must pass `ruff format --check .` too.
- Evidence = pasted output (test results, counts, `qa_report.json` counts). "Looks right" is not
  evidence. Report failures verbatim.
- Always `uv run …`; never bare `python`/`pip`. Text layer wins; never let a VLM transcribe running
  text. Never reshape mineru output. Never guess a page range. No pre-built fallbacks.
- No golden-file byte equality on VLM-generated blocks.
- The operator edits inline comments in `src/split.py` themselves — leave that file alone.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Pushing to the remote is the operator's action (the auto-mode classifier blocks it).

## 7. Pitfalls met this session

- `ruff check` enforces `re.IGNORECASE` over `re.I` (FURB167) and dict literals over `dict(...)`
  (C408); the plan code already complies.
- PyMuPDF `get_text("words")` keeps em spaces inside a "word" (`6  Making`), so tests
  compare word lists, not `.split()` counts.
- Hunk context (`pdf_text`/`md_text`) is drawn from the *residual* streams after block alignment,
  not from the full page.
- `Foreground` waits: mineru runs ~26 s per bma chapter; run long jobs in the background and poll.
- To re-validate plan code before pasting it, the dry-run recipe is a scratch tree that symlinks
  the repo's `src/*.py` (except the module under test), `tests/helpers.py`, `tests/conftest.py`
  and `tests/fixtures`, plus its own `pyproject.toml` with `pythonpath=["."]`; run
  `uv run --project <repo> --no-sync pytest -q` from the scratch dir.
- `MINERU_SERVER_URL` defaults to `http://127.0.0.1:30000` via the Makefile; `extract.py` sets the
  GPU-1 / local-model env itself — never export those by hand.

## 8. Deferred (recorded, not gate-3 work)

Stage-5 policy for `page_aside_text` callouts, chart data tables, footnote rendering and the
rendering of `running_matter_suspect` blocks; heading hierarchy must come from `meta.json`
(mineru `title.level` never goes below 2); acct/ops header mislabels are a gate-4 concern; the Mac
client over Tailscale; `chapter_ranges` for stats/acct.
