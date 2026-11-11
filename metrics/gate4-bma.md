# Gate 4 — bma ch05 and ch06 (2026-09-07)

Stage 5 end-to-end on the two Brealey–Myers–Allen chapters: pre-pass → two-tier review →
finalize → push → Obsidian's parse compared → the operator's mobile pass. Counts and block ids
only. Design: `docs/plans/2026-09-07-stage5-design.md`; plan Tasks 11–12 carry the step-level
measurements.

- Desktop vault: Obsidian 1.13.7, Local REST API plugin 4.1.3 (renders no HTML; `check --parsed`
  compares its `note+json` and `document-map+json` views). Push root `raw/textbooks/`.
- Phone: the operator's Android phone, Obsidian mobile via Obsidian Sync (version not recorded);
  pushed notes arrived within minutes.
- Reviewer sessions: `/chapter-review bma 5` 05:44–06:22 UTC, `/chapter-review bma 6` 06:54–07:08
  UTC. Tier A `model: sonnet`, 100 % of crops. Token counts: `/cost` is not available on the
  operator's subscription.

## Review and certification

| | bma ch05 | bma ch06 |
|---|---|---|
| pages / blocks / hunks | 30 / 1 084 / 57 | 26 / 780 / 82 |
| pre-pass: same_letters · move · edge_glyph · inline_math · junk · duplicate · folio | 26 · 8 · 4 · 4 · 2 · 0 · 0 | 46 · 10 · 6 · 3 · 4 · 5 · 0 |
| pre-pass `needs_eyes` (tier B) | 13 | 8 |
| final hunk verdicts: accepted_pdf · move · patched · verified · dropped · accepted_md | 30 · 16 · 5 · 4 · 2 · 0 | 52 · 10 · 11 · 3 · 5 · 1 |
| flagged blocks (tier A answered) | 67 (67) | 50 (50) |
| tier A `match: true` / mismatch — table | 38 / 0 | 30 / 1 |
| tier A `match: true` / mismatch — formula | 18 / 2 | 12 / 6 |
| tier A `match: true` / mismatch — chart, figure, text | 9 / 0 | 0 / 1 |
| block verdicts verified / patched | 60 / 7 | 43 / 7 |
| spot checks ok / patched | 16 / 0 | 19 / 1 |
| headings: sections, subheadings found | 9/9, 12/12 | 10/10, 22/22 |
| footnotes: definitions / references / dangling | 11 / 12 / `16` | 13 / 13 / none |
| review patches by op: replace · set_math · set_content · set_inline_math · drop_block | 5 · 2 · 6 · 3 · 0 | 5 · 6 · 1 · 4 · 1 |
| `crops_opened` | 87 | 81 |
| `finalize` | certified | certified |
| staging tree files (notes + assets) | 20 (10 + 10) | 12 (11 + 1) |
| `make push` read-back | 20/20 verified, 0 failed | 12/12 verified, 0 failed |
| `make check PARSED=1` | OK | OK |

ch05 needed a second finalize: its first `/chapter-review` ended `needs_attention` with three hunks
(2, 6, 29). Hunk 6 was a guardrail alignment artefact (the "dropped" footnote is `p004-b017`);
hunks 2 and 29 were MFR inline-formula defects that no patch op could reach → `set_inline_math`
was added and applied. A concurrent `make review` / pytest run then wiped 13 manual hunk verdicts
and invalidated the certified render's sha; both causes are fixed (pre-pass keeps `rule: manual`
entries; `workdir` tests run in a sandbox) and the verdicts were re-entered from the pre-wipe
histogram.

## Mobile checklist (operator, reading view)

| item | ch05 | ch06 (3 sections: 6-1, 6-3, 6-4) |
|---|---|---|
| 1 inline and display math render | pass (5-1 opener, eq. 5.1) | pass |
| 2 a `simple_table` and a `complex_table` render | pass (5-2) | pass |
| 3 a figure and a chart show | pass (Fig. 5.1 crop, Fig. 5.2 chart) | pass (`p003-b000` in 6-1) |
| 4 a callout folds | pass (Chart data, BEYOND THE PAGE) | pass |
| 5 a footnote jumps and returns | pass (`[^1]` in 5-2) | pass |
| 6 previous, hub and next links from a middle section | pass (5-3) | pass (6-3) |
| 7 page comments invisible in reading view | pass (`%% p. 119 %%` in 5-1) | pass |

## Verdict

Gate 4 **passed**: both chapters `certified`, both pushes verified every file, Obsidian's parse
agrees with the staging trees, and the checklist is clean on both.

Known limits carried to gate 5 (not gate-4 failures): `$…$` inside complex-table HTML shows
literally (Obsidian does not parse Markdown inside HTML blocks); mineru types some ornaments and
logo text as `title` blocks (`### connect` in ch05 note 07), left for the rendering stop rule;
the REST API cannot confirm rendering, so the phone remains the only rendering check.
