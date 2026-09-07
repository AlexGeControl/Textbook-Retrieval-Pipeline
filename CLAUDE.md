# CLAUDE.md — textbook retrieval pipeline

Born-digital textbook chapters → certified Obsidian markdown (faithful text,
LaTeX, tables, figure crops). Output is companion context for downstream
lecture-note synthesis; synthesis itself is out of scope here.

Design brief: `docs/design/HANDOVER.md`. Read it before brainstorming or
planning any stage. Design principles (§1), component contracts (§6) and
build order/gates (§7) are fixed. Function names, module boundaries and
normalization rules are yours. Open decisions are listed in §9.

Stages 1–4 (splitter, extract wrapper, guardrail, qa_report) are designed in
`docs/plans/2026-09-06-stages-1-4-design.md`, which supersedes HANDOVER §5–§7
for those stages and records the resolved §9 decisions (content_list anchor,
chapter-unit extraction with sections in meta.json, `table|formula|chart`
flags, GPU 1 + local model pins, BMA ch. 5–6 benchmark, optional reading lists).

Stage 5 (pre-pass, two-tier review skill, section rendering, vault commit) is
designed in `docs/plans/2026-09-07-stage5-design.md` (read its Amendments too), which
supersedes HANDOVER §6 "Stage 5" and the gate 4–5 details of §7, and built by
`docs/plans/2026-09-07-stage5-plan.md`; `docs/plans/2026-09-07-stage5-handover.md` is the
resume point for the implementation session.

## Stack

- Python managed by `uv`. Always `uv run …` / `uv add …` / `uv sync …`; never
  bare `python` or `pip`. Server box: `uv sync --extra server` (a plain
  `uv sync` prunes vllm — 115 packages) and `uv run --no-sync` for server
  commands. Plain `uv run` is inexact (no pruning), so `uv run pytest` is safe.
- Pins (verified 2026-09-06): mineru 3.4.5 (caps vllm `<0.22` → 0.20.2),
  torch 2.11.0+cu130. `[tool.uv]` constraint `fastapi<0.137` is required —
  vllm 0.20.x's prometheus middleware 500s on newer FastAPI. Extras:
  `mineru[pipeline]` = client, `mineru[vllm]` = server; `[core]`/`[all]` are
  not needed.
- Extraction: MinerU, backend `hybrid-http-client`, `--effort high`. Never
  `vlm-http-client` (generative transcription of running text — rejected).
- Text layer, TOC, guardrail diff: PyMuPDF. AGPL — personal pipeline only, do
  not vendor into work code.
- Inference server: vLLM serving `MinerU2.5-Pro-2605-1.2B`, OpenAI-compatible
  HTTP on port 30000, pinned to GPU 0 (RTX PRO 6000 Blackwell; GPU 1 is an
  RTX A6000). Client reads `MINERU_SERVER_URL`. Clients need no GPU (mineru
  auto-uses CUDA/MPS if present); the MacBook reaches the server over
  Tailscale.
- Tests: pytest. Unit tier is the default (no network). `-m integration`
  needs the live server.
- Lint/format: ruff.

## Commands

Makefile targets (verified 2026-09-07): `sync-server`, `server-models`, `client-models`,
`serve` (server box; that is the fresh-server-box order — a client needs only
`uv sync && make client-models`), the stage targets `split`, `extract`, `guardrail`, `qa_report`,
`chapter`, and the stage-5 targets `prepass`, `review-checks`, `review`, `finalize`, `render`,
`check`, `push`. Keep this list in sync.

- `uv run pytest` — unit tier, no network; reads `tests/fixtures/cache/`; must
  pass before every commit
- `uv run pytest -m integration` — regenerates the fixture cache; needs
  `MINERU_SERVER_URL`
- `uv run ruff check . && uv run ruff format --check .`
- `make chapter BOOK=<id> CH=<n>` — stages 1–4 into `work/<id>/chNN/` (`FORCE=1`
  re-extracts); `make split|extract|guardrail|qa_report BOOK=… CH=…` run one stage
- `make review BOOK=<id> CH=<n>` — stage 5a: pre-pass + mechanical checks into the `review`
  key of `qa_report.json` and `work/<id>/chNN/patches.json`; then `/chapter-review <id> <n>` in
  a Claude Code session adjudicates the residue (tier A Sonnet over crops, tier B the reviewer)
  and ends with `make finalize BOOK=… CH=…`, which derives `status`, renders
  `vault/<id>/chNN/` and runs the battery (`make -n` shows the `uv run python -m …` forms)
- `make render|check|push BOOK=… CH=… [SECTION=<ordinal|slug>]` — inspect, re-check or push
  the staging tree; `check PARSED=1` compares Obsidian's parse of the pushed notes; it and
  `push` read `OBSIDIAN_HOST`, `OBSIDIAN_PORT`, `OBSIDIAN_API_KEY` from the environment (never
  committed). Only a `certified` manifest pushes; default `ROOT=raw/textbooks/`
- `make sync-server` — install/refresh the `server` extra via the TUNA
  mirror and restore the pypi.org `uv.lock`. Never commit a mirror lock.
- `make server-models` — `hf download` of the VLM `VLM_REPO@VLM_REVISION`
  (pinned commit, ~2.2 GB) into the HF cache; idempotent, resumes, retries
  stalls. Direct HF works from here; `hf-mirror.com` does not (huggingface_hub
  metadata check fails) — never set `HF_ENDPOINT` to it.
- `make client-models` — the PDF-Extract-Kit models the hybrid client runs
  locally (`KIT_REPO@KIT_REVISION`, ~1.06 GB: OCR det/rec, PP-DocLayoutV2
  layout, UniMERNet MFR for inline formulas); same retry loop.
  `KIT_MODELS="$(make -s print-kit-base)"` skips the MFR (`-f false` books).
- `make serve` — VLM server on GPU 0, :30000; server box only. Resolves the
  pinned snapshot offline and passes `--model`. Vars: `GPU PORT GPU_MEM_UTIL
  VLM_REPO VLM_REVISION`. First request takes ~26 s (warm-up).

## Layout

```
Makefile                   sync-server, server-models, client-models, serve, split, extract,
                           guardrail, qa_report, chapter
books/<id>/<id>.pdf        PDF landing zone; gitignored, never leaves this machine. Outline may be
                           patched in place by scripts/patch_toc.py; <id>.orig.pdf keeps the original
books/manifest.json        hashes/page counts from scripts/check_books.py (committed)
config/books.yaml          per-book pdf path, TOC hints, routing flags
config/readings/*.yaml     optional per-course chapter lists (mitx.yaml today)
src/config.py              books.yaml loader, chapter slug/number, work_dir
src/readings.py            reading-list resolution against the outline
src/toc.py                 outline helpers: chapter_entries + toc.patches rules (shared)
src/split.py               stage 1  chapter splitter
src/extract.py             stage 2  mineru wrapper
src/blocks.py              block model over <stem>_content_list_v2.json (stages 3-5)
src/normalize.py           guardrail normalization rules (MD_RULES, PDF_RULES)
src/guardrail.py           stage 3  PyMuPDF text-layer diff -> guardrail.json
src/qa_schema.py           qa_report.json validator (HANDOVER §6)
src/qa_report.py           stage 4  qa_report.json builder
src/vault_commit.py        stage 5b move certified output into vault
scripts/check_books.py     landing-zone intake check; run after adding any PDF
scripts/probe_toc.py       outline evidence for books.yaml toc.*; --check resolves all chapters
scripts/patch_toc.py       write toc.patches rules into a book's PDF outline (dry run by default)
.claude/skills/chapter-review/SKILL.md   stage 5 reviewer instructions
work/<book>/chNN/          chapter.pdf meta.json chapter/hybrid_auto/ guardrail.json
                           qa_report.json crops/  (gitignored)
metrics/                   block-type evidence, gate3-bma.md, hunk-stats-2026-09-06.md
tests/helpers.py           fixture-cache lookup shared by unit tests
tests/fixtures/            fixture PDFs + cached MinerU outputs (gitignored)
docs/design/               handover and design docs, loaded on demand
docs/plans/                design + plan for stages 1–4; addenda record the gates
```

## Hard rules

- Text layer wins. VLM output is used only for blocks typed table, formula
  or figure. Never let a VLM transcribe running text.
- Review patches, never regenerates. No "rewrite this section" in code,
  prompts or skills.
- Fail loudly. Missing or wrong PDF outline → error naming book and chapter.
  Never guess a page range.
- Do not pre-build fallbacks (HANDOVER §8): no OCR path, no Qwen refinement
  stage, no heading-refinement hook until a gate fails.
- Book PDFs, `work/`, fixture PDFs and MinerU outputs never enter git. Only
  certified notes enter the vault.
- Stage 2 outputs stay MinerU-native: `<stem>/hybrid_auto/` holding `<stem>.md`,
  `<stem>_content_list.json` (+`_v2`), `<stem>_middle.json`, `images/`. Don't
  reshape them.
- `qa_report.json` follows the schema in HANDOVER §6 exactly. Validate it in
  stage 4.
- Stages 3–5 anchor on `<stem>_content_list_v2.json` (one list per page,
  span-level text). v1 and the `.md` are reference renderings; never diff or
  slice from them.

## Testing conventions

- Fixtures live in `tests/fixtures/<book>/<set>.pdf`, 1~4 pages each,
  The baseline set comes from MITx MicroMaster in Finance, Foundations of Modern Finance suggested readings. A fetch/split script builds them; nothing is committed. The stratified baseline set: 
  - text-only control page at `tests/fixtures/bkm/text-only.pdf`
  - table page at `tests/fixtures/bma/table.pdf`
  - display-formula page at `tests/fixtures/bma/formula.pdf`
  - chart page at `tests/fixtures/bkm/chart.pdf`.
- The control page (`bkm/text-only.pdf`) carries two decorative check-mark
  icons that mineru types `image`: assert zero table/formula blocks there, not
  zero image blocks. mineru types plots as `chart`, not `image`.
- RED for extraction work is a failing structural assertion: guardrail hunk
  count > 0 on the control page, table row/column count ≠ crop, expected
  formula block absent, LaTeX not parseable, heading tree ≠ `meta.json`.
- No golden-file byte equality on VLM-generated blocks. MinerU output is not
  deterministic; such tests are forbidden.
- Unit tier runs against cached MinerU outputs in `tests/fixtures/cache/`.
  Integration tier regenerates the cache against the live server.
- Guardrail normalization is the highest-iteration area. Each normalization
  rule gets its own failing test before implementation.
- Fixture cache: `tests/fixtures/cache/<book>/<set>/hybrid_auto/`, seeded once
  from a live run (`uv run pytest -m integration`). Unit tests skip with a
  message if it is missing.
- Guardrail rules live in `src/normalize.py` (`MD_RULES`, `PDF_RULES`); append,
  never reorder silently; every rule has a captured-string test in
  `tests/test_normalize.py`.

## Superpowers — project deviations

- Brainstorming: confirm and formalize `docs/design/HANDOVER.md`. Do not
  relitigate fixed items; spend the session on §9 open decisions.
- Use `executing-plans` (batches with human checkpoints), not
  `subagent-driven-development`. Single operator, GPU server in the loop.
- Plans follow the build order in HANDOVER §7. Each task's verification step
  is the gate criterion for that stage, not just "tests pass".
- Verification before completion means pasting test output and
  `qa_report.json` counts. "Looks right" is not evidence.
- Once brainstorming writes its design doc to `docs/plans/`, that doc
  supersedes HANDOVER.md. Update the pointer at the top of this file.
- Do not use git worktrees. Work on a branch in the main checkout: `books/`,
  `work/` and `tests/fixtures/` are untracked and do not exist in a worktree.

## Environment notes

- Server model: `MinerU2.5-Pro-2605-1.2B` (mineru 3.4.5's default), pinned to
  commit `bff20d4…` as `VLM_REVISION`; `make server-models` fetches it with the
  venv's `hf` CLI and `make serve` loads that snapshot offline via `--model`.
  Bump a pin only after validating the new commit.
- Client models: `PDF-Extract-Kit-1.0` subset pinned as `KIT_REVISION`
  (~1.06 GB; the UniMERNet MFR does *inline* formulas locally, display
  formulas/tables/charts go to the VLM). Run `make client-models` before the
  first `hybrid-http-client` run on any machine — otherwise mineru
  auto-downloads without the stall-proof retry loop. HF large files run fast
  then stall to 0 KB/s; ModelScope (`MINERU_MODEL_SOURCE=modelscope`) is steady
  but ~0.4 MB/s.
- Shanghai network: wheels >~180 MB stall from PyPI's origin CDN (small ones
  are fine) → `make sync-server` (TUNA). Model weights: the `*-models` targets
  retry through HF stalls; ModelScope is the slow fallback. Probe with a full
  large file — a 20 MB range hides the stall.
- Changing uv's index relocks `uv.lock` (mirror URLs + different platform
  markers) and `uv lock` does not switch back; `make sync-server` handles
  the backup/compare/restore. Don't set `UV_DEFAULT_INDEX` globally.
- Two GPUs: `nvidia-smi` index 0 = RTX PRO 6000 Blackwell (SM120), 1 = RTX
  A6000. Use `CUDA_DEVICE_ORDER=PCI_BUS_ID` so CUDA indices match.
- Versions are pinned (see Stack); re-verify against MinerU/vLLM docs before
  bumping — both move fast.
- The extraction client on this box runs on GPU 1 with pinned local models:
  `extract.py` sets `CUDA_DEVICE_ORDER=PCI_BUS_ID MINERU_DEVICE_MODE=cuda:1
  MINERU_MODEL_SOURCE=local` and reads `models-dir` from `~/mineru.json`. Never
  export these by hand; run through `make extract`/`make chapter`.
