---
name: chapter-review
description: Stage-5 review of one extracted textbook chapter under work/<book>/chNN/ — adjudicate the pre-pass residue, run the Sonnet perception tier over every crop, write verdicts and surgical patches through src.review, finalize, and report. Use when asked to review, certify or re-certify a chapter.
---

# Chapter review (stage 5, tier B)

You are the reviewer for exactly one chapter: `$ARGUMENTS` = `<book> <chapter>` (for example
`bma 5`). Design: `docs/plans/2026-09-07-stage5-design.md` §8. You patch; you never regenerate.
The text layer wins unless a crop shows the layer itself is wrong.

Below, `B` and `N` stand for the book id and the chapter number from `$ARGUMENTS`. Every write
goes through `uv run python -m src.review <subcommand> … --book B --chapter N`; the `make`
targets are the composite entry points (`make -n <target> BOOK=B CH=N` shows what they run).

## What you may open

- `work/B/chNN/qa_report.json` (the `review` key is your worklist) and `patches.json`.
- Crops, only through `uv run python -m src.review crop --id <block> --book B --chapter N`,
  which prints the path and counts the open. Read the printed file with the Read tool.
- The block bodies, only through the one-liners in the rubrics (they read patches-applied
  blocks via `src.review.Chapter`).
- Nothing else. Not `chapter.md`, not `chapter.pdf`, not `hybrid_auto/*.json`, not other
  chapters, not `vault/`, not the Obsidian vault. Never edit `qa_report.json` or `patches.json`
  with a text tool.

## Steps

1. `make review BOOK=B CH=N` (pre-pass + mechanical checks). If it fails naming a section
   anchor, stop and report: the outline needs a `toc.patches` fix, not a review.
   Then `uv run python -m src.review start --book B --chapter N`.
2. Read `review.prepass.counts`, every hunk with `verdict: unresolved` (with its
   `diff_hunks[i]` context), every `blocks[*]` entry with its `checks`, `headings.missing`,
   `footnotes.unmatched`, and `spot_check`.
3. **Tier A.** For every flagged block and every spot-check block, dispatch perception agents
   with `model: sonnet`, about ten crops per agent, using the rubric for the block type
   (`rubric-table.md`, `rubric-formula.md`, `rubric-chart.md` for chart and figure,
   `rubric-text.md` for `running_matter_suspect` and spot checks). Give each agent, per block:
   the crop path (from `review crop`), the block's current rendering (HTML, LaTeX, data table
   or text, obtained with the rubric's one-liner), and the `checks.textlayer_diff` tokens as
   spotlights. Agents answer with the JSON in `answer-schema.json` and nothing else. Use the
   Workflow tool when the operator has opted in for this session, otherwise the Agent tool;
   both with `model: sonnet`. Agents read crops; they write nothing.
4. Relay every answer: `review block --id <block> --visual '<json>'`, or for spot checks
   `review spot --id <block> --verdict ok|unresolved --note "<agent note>"`. A block is
   `--verdict verified` only when the agent reports `match: true` with no `error`
   discrepancies AND (`checks.textlayer_match` is true or null, or every spotlight token was
   resolved as an artefact in the agent's `discrepancies` with `resolution: artefact`).
5. **Tier B (you).** Open the crop yourself for: every block not verified in step 4, every
   `unresolved` hunk, every `headings.missing` entry, every `footnotes.unmatched` entry, and
   every spot check the agent did not clear. Decide, then write:
   - hunks: `review hunk --index i --verdict accepted_pdf|accepted_md|move|dropped|patched
     --rule manual --patch <ids> --note "…"`, with a `review patch --block … --op replace
     --old … --new … --hunk i` first when text changes. `accepted_md` is for a defective text
     layer (symbol fonts, ornaments). Never `set_*` on running text.
   - blocks: `review patch … --op replace|set_math|set_html|set_content` against the crop, then
     `review block --id … --verdict patched --patch <id>`; or `--verdict verified`; or
     `--verdict dropped` for a suspect that is running matter. Leave `unresolved` with a note
     when the crop does not settle it.
   - headings: `review heading --title "…" --verdict found_as --block <id>` or
     `--verdict not_a_heading --note "boxed feature"`.
   - footnotes: `review footnote --id n --verdict accepted --note "referenced inside table X"`
     or patch the lost marker (`review patch … --op replace --old "flows." --new
     "flows.<sup>n</sup>"`) and `--verdict patched`.
   A patch whose `--old` is absent or ambiguous is refused and nothing is written; narrow it.
6. `make finalize BOOK=B CH=N`. It prints `finalize: B chNN -> certified` or
   `-> needs_attention` followed by the `unresolved` list (make itself exits 2 on the latter;
   the underlying `uv run python -m src.review finalize` exits 0 / 3 / 1). On
   `needs_attention`, report the `unresolved` list verbatim and stop. Never push.
7. Report: the pre-pass counts, tier-A match/mismatch by type, your patches by op, the
   finalize status, `effort.crops_opened`, and any outline or per-book issue you noticed.

## Rules you must not break

- Surgical: a `replace` changes the smallest unique substring. A `set_*` rewrites one VLM body
  against its crop and nothing else.
- Text layer wins on running text; VLM bodies are judged against their crop.
- No verdict without evidence: a hunk you did not look at stays `unresolved`.
- Counts only in your report: never paste book text into anything committed.
