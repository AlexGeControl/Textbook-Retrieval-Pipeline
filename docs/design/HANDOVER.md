# Handover: textbook retrieval pipeline (FMF + FMBA → Obsidian)

Design agreed in a claude.ai session on 2026-09-05. This document is the
implementation brief. Treat the contracts and guardrails as fixed; treat
implementation details (function names, exact normalization rules) as yours
to decide. §3–§4 revised 2026-09-06 after server bring-up (gate 1 passed):
the environment baseline there is verified, not projected.

## 1. Mission

Retrieve recommended textbook chapters from born-digital PDFs into Obsidian
markdown **as-is** — faithful text, LaTeX formulas, tables, and embedded
figure images — to serve as companion context (alongside lecture video
transcripts) for downstream lecture-note and assignment synthesis by Claude
Code. Synthesis is out of scope here; this pipeline only produces certified
chapter notes.

Design principles (fixed):
- Deterministic extraction wherever a text layer exists; VLM inference only
  for tables, formulas, layout, and scanned/ambiguous regions.
- Every VLM-touched region is auditable: flagged, cropped, spot-checkable.
- The reviewer **patches, never re-transcribes**. Whole-section regeneration
  reintroduces the statistical failure mode this design exists to remove.
- Cost and review effort scale with defect count, not corpus size.
- All book content stays on local machines; only final certified notes enter
  the vault. Personal study use only.

## 2. Corpus

| ID | Book / source | Expected difficulty profile |
|----|---------------|------------------------------|
| bkm | Bodie, et al., *Investments*, 13e | formulas, heavy |
| bma | Brealey et al., *Principles of Corporate Finance*, 14e | formulas, heavy |
| ops | Cachon & Terwiesch, *Matching Supply with Demand*, 5e | diagrams + some math |
| strat | Dess et al., *Strategic Management*, 13e | prose + exhibits (easy) |
| stats | Anderson et al., *Statistics for Business and Economics*, 15e | formulas + tables |
| corpfin | Ross et al., *Corporate Finance*, 13e | formulas + tables (hardest) |
| acct | Pratt, *Financial Accounting*, 11e | tables everywhere |

All inspected by Yao: born-digital, text layer copyable. No OCR path needed
in v1 (hybrid backend falls back to OCR automatically if a scanned page
appears; don't build anything for it).

## 3. Hardware & topology

- **Inference server**: RTX PRO 6000 Blackwell (96 GB, CUDA index 0) Linux
  box; a second GPU (RTX A6000, index 1) is present, so the server is pinned
  to index 0. Runs vLLM serving the MinerU VLM. Headless service, `make serve`.
- **Extraction clients**: the server box itself (primary) and, over
  Tailscale, a MacBook Pro (decided 2026-09-06; supersedes "client == server
  box"). Client work is CPU-light — mineru auto-uses CUDA/MPS when present,
  none required. Runs chapter splitting, MinerU hybrid client, guardrail
  diff, QA report build, and the Claude Code review session.
- One network hop total: OpenAI-compatible HTTP to the server, port 30000
  (binds 0.0.0.0; the Mac reaches it via the tailnet IP).

## 4. Environment setup

Verified 2026-09-06 (gate 1 passed). Pinned in `pyproject.toml` / `uv.lock`:
mineru 3.4.5, vllm 0.20.2 (mineru caps `<0.22`), torch 2.11.0+cu130,
mineru-vl-utils 1.2.1; VLM `opendatalab/MinerU2.5-Pro-2605-1.2B` (mineru's
default) pinned to commit `bff20d4…` in the Makefile. Serves on SM120
(Blackwell) with driver 580.

```bash
# server box (Linux): extras, both model sets, server — in this order
make sync-server     # uv sync --extra server via the TUNA mirror; uv.lock stays on pypi.org
make server-models   # hf download of the VLM (VLM_REPO@VLM_REVISION, ~2.2 GB), idempotent
make client-models   # PDF-Extract-Kit models the hybrid client runs locally (~1.06 GB)
make serve           # GPU 0, :30000, --gpu-memory-utilization 0.3, --model <cached snapshot>, offline

# any client (server box or Mac): client extra + client models
uv sync && make client-models
uv run mineru -p <chapter.pdf> -o <outdir> -b hybrid-http-client \
  -u http://<server>:30000 --effort high
```

Notes:
- Extras: `mineru[pipeline]` is the client (`hybrid-http-client` runs
  layout/detection locally; only VLM calls cross the network); `mineru[vllm]`
  is the server, in the Linux-only `server` extra. `[core]`/`[all]` add only
  accelerate/gradio/mlx — for in-process `vlm-engine` and the Gradio UI,
  neither used here.
- Every client also needs mineru's pipeline models (`opendatalab/PDF-Extract-Kit-1.0`
  subset, ~1.0 GB: OCR det/rec, PP-DocLayoutV2 layout, unimernet MFR for
  *inline* formulas — display formulas, tables and charts go to the VLM).
  `make client-models` fetches them (pinned `KIT_REVISION`, stall-proof retry
  loop); without it mineru auto-downloads on first use and may stall.
  `-f false` drops the MFR (the `strat` routing case:
  `KIT_MODELS="$(make -s print-kit-base)"`).
- Backend is `hybrid-http-client`, **not** `vlm-http-client` (hybrid pulls
  running text from the PDF text layer; vlm transcribes everything
  generatively — rejected for hallucination risk on digits).
- `--effort high` everywhere; corpus is bounded, pay for accuracy.
- `uv sync` without `--extra server` prunes vllm; server commands use
  `uv run --no-sync`. `[tool.uv] constraint-dependencies = ["fastapi<0.137"]`
  is required: FastAPI ≥0.137 makes vllm 0.20.x's prometheus middleware
  return 500 on every request (fixed upstream only in vllm newer than
  mineru allows).
- Shanghai network: wheels >~180 MB (torch, vLLM, CUDA libs) stall from
  PyPI's origin CDN; `make sync-server` routes them through TUNA and
  restores the pypi.org lock. Model weights download directly from
  huggingface.co (reachable here); `hf-mirror.com` fails huggingface_hub's
  metadata check — do not use it. mineru's documented fallback for pipeline
  models is `MINERU_MODEL_SOURCE=modelscope`.
- First request after `make serve` takes ~26 s (one-off warm-up; steady
  state is milliseconds). Warm the server before timing benchmarks (§7.5).
- MinerU supports an optional LLM-aided heading refinement hook via
  `mineru.json` pointing at any OpenAI-compatible endpoint. Leave OFF in v1;
  it is the first lever if heading hierarchy turns out to be the main defect.
- PyMuPDF is AGPL: fine for this personal pipeline; do not vendor it into
  anything work-related without checking.

## 5. Repo layout (proposal — adjust freely)

```
pipeline/
  Makefile                # sync-server, server-models, client-models, serve (verified); chapter (first plan)
  config/
    books.yaml            # per-book: pdf path, TOC hints, routing flags
    readings/             # per-course chapter lists (bkm.yaml, bkm.yaml)
  src/
    split.py              # stage 1
    extract.py            # stage 2 wrapper around mineru CLI
    guardrail.py          # stage 3
    qa_report.py          # stage 4
    vault_commit.py       # stage 5b: move certified output into vault
  review/
    REVIEW_SKILL.md       # stage 5 instructions for Claude Code reviewer
  work/                   # per-chapter working dirs (gitignored)
  metrics/                # benchmark + per-chapter metrics logs
```

## 6. Component contracts

### Stage 1 — chapter splitter (`split.py`)
- Input: book PDF + reading list entry (chapter/section identifiers).
- Uses the PDF outline (PyMuPDF `get_toc()`) to resolve page ranges; falls
  back to a manual page-range field in `books.yaml` when the outline is
  missing/wrong. Never guess ranges silently — fail loudly.
- Output: `work/<book>/<chapter-slug>/chapter.pdf` + `meta.json`
  (book id, chapter title, source page range, TOC subtree for later heading
  verification).

### Stage 2 — extraction (`extract.py`)
- Runs mineru `hybrid-http-client` on `chapter.pdf`.
- Output (MinerU-native, don't fight it), verified on the fixtures 2026-09-06:
  `<stem>/hybrid_auto/<stem>.md`; `<stem>_content_list.json` (flat blocks:
  type, page_idx, bbox, text | table_body HTML | img_path); `_content_list_v2.json`
  (per page, richer types, nested `content`); `<stem>_middle.json` (spans);
  `images/` figure and table crops. One VLM call per page (layout) plus one
  per table/formula/chart block.
- Per-book routing flags from `books.yaml` (e.g. inline-formula toggle off
  for `strat`).

### Stage 3 — guardrail diff (`guardrail.py`)
- Extract raw text layer for the same pages via PyMuPDF.
- Normalize BOTH sides before diffing: whitespace collapse, soft-hyphen /
  line-end hyphenation repair, drop running headers/footers and page
  numbers, Unicode NFKC. Expect iteration here — normalization quality
  determines false-positive rate, which determines review cost.
- Diff against the stage-2 markdown (`<stem>.md`) running text **excluding**
  blocks typed table/formula/figure-caption in the layout JSON.
- Output: list of residual hunks with page + block anchors. Target state on
  a clean chapter: zero hunks.

### Stage 4 — QA report (`qa_report.py`)
Single file `qa_report.json` per chapter — the entire work order for stage 5
and the metrics record. Schema (v1):

```json
{
  "book": "bma", "chapter": "ch05", "pages": [119, 148],
  "extraction": {"backend": "hybrid-http-client", "effort": "high",
                  "mineru_version": "", "timestamp": ""},
  "counts": {"blocks": 0, "tables": 0, "formulas": 0, "figures": 0,
              "diff_hunks": 0},
  "diff_hunks": [{"page": 0, "anchor": "", "pdf_text": "", "md_text": ""}],
  "flagged_blocks": [{"id": "", "type": "table|formula",
                       "crop": "images/….png", "reason": "vlm_generated"}],
  "spot_check": [{"id": "", "crop": ""}],
  "status": "pending_review"
}
```
- `flagged_blocks`: ALL tables and formulas (they are VLM-generated by
  construction) plus anything low-confidence.
- `spot_check`: small random sample (e.g. 5%) of unflagged blocks.

### Stage 5 — Claude Code review (`review/REVIEW_SKILL.md`)
Write this as a skill/instruction file the review session loads. Rules:
- Read `qa_report.json`; open ONLY referenced crops and hunk contexts.
- Adjudicate each diff hunk (text-layer wins unless the crop shows the
  layer itself is wrong, e.g. ligature garbage).
- For each flagged table/formula: compare crop to markdown; emit a
  **surgical patch** if wrong. Never regenerate a section.
- Verify programmatically, not by eye: LaTeX must compile (or KaTeX-parse),
  table row/column counts must match the crop structure, heading hierarchy
  must match `meta.json` TOC subtree.
- Update `qa_report.json` with per-item verdicts, patch count, token/effort
  notes; set `status: certified` or `status: needs_attention`.
- Then `vault_commit.py`: write chapter note + `assets/` into the Obsidian
  vault with frontmatter `{book, chapter, course, source_pages, certified}`.

## 7. Build order & acceptance gates

1. **Server bring-up** — one command (`make serve`); gate: OpenAI-compatible
   endpoint answers on :30000 from the client machine. **Passed 2026-09-06**
   from the server box; the Mac-over-Tailscale check is pending.
2. **Stage 2 on one benchmark chapter** (start with `bma`, a
   formula+table-heavy chapter — hardest case first). Gate: `<stem>.md` +
   content-list/middle JSON + crops produced end-to-end.
3. **Stages 3–4** on that chapter. Gate: diff false-positive rate low enough
   that hunk list is reviewable by hand (< ~10 spurious hunks/chapter after
   normalization tuning); qa_report.json validates against schema.
4. **Stage 5 skill** on that chapter. Gate: certified output in vault;
   renders correctly in Obsidian mobile (math, tables, embedded figures).
5. **Benchmark pass**: one representative chapter per book (7 chapters).
   Record per chapter: diff-hunk count, formula error rate (spot-checked),
   table cell accuracy on 2–3 tables, review tokens consumed, wall time.
   Gate: metrics acceptable per book, or a per-book routing fix identified.
6. **Batch loop** over full reading lists, streaming per-chapter (don't
   batch the whole corpus into one run; write results incrementally).

## 8. Fallbacks (do NOT pre-build; add only if a gate fails)

- Heading hierarchy bad → enable MinerU's LLM-aided heading refinement hook
  (cheapest lever) before anything custom.
- A specific book's tables below bar (bet: `acct`) → targeted Claude
  spot-fix budget for that book, or per-book effort/routing tweak.
- Systematic VLM defects → contingency: serve Qwen3-VL-32B-FP8 on the
  6000 Pro as a local refinement endpoint. Explicitly rejected for v1 —
  a stage with no customer while Claude Code reviews.

## 9. Open decisions for the implementation session

- Exact vault note layout: one note per chapter vs per section; wikilink
  scheme to course/lecture notes.
- Figure captions: keep MinerU's extracted captions as-is (default) or
  have review add alt-text (only if mobile reading suffers without it).
- Diff normalization rules — expect the most iteration time here.
- Whether stage 2–4 run as one `make chapter BOOK=x CH=y` entrypoint
  (recommended) or separate invocations.
- Added after the setup work (2026-09-06):
  - Which stage-2 JSON anchors stages 3–4: `_content_list.json` (flat, v1),
    `_content_list_v2.json` (per page, richer types) or `_middle.json` (spans).
  - Block-type vocabulary in rules and `qa_report.json`: mineru's `table`,
    `equation`, `chart`, `image` (+ captions) vs this brief's
    "table/formula/figure"; whether `chart`/`image` blocks are flagged.
  - Client model resolution: rely on mineru resolving `main` (pins agree
    today) vs `MINERU_MODEL_SOURCE=local` + `mineru.json` pointing at the
    pinned snapshot for fully deterministic runs.
  - Routing flags → CLI (`inline_formula` → `-f`, plus `-t`,
    `--image-analysis`, `--lang`), and whether the server-box client should
    use GPU 1 (A6000) rather than share GPU 0 with vLLM.
  - Mac client: verify Tailscale reachability before any Mac-side stage.
