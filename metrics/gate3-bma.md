# Gate 3 — bma ch05 / ch06 (2026-09-06)

Stages 1–4 end to end (`make chapter BOOK=bma CH=5|6`, extraction reused) at the tuned
normalization rules; hunk classification per the gate-3 handover protocol, every hunk read.
The same pipeline ran on ch05 of the other six books; that evidence, gathered with one
mechanical classifier and one reviewing agent per chapter, is in
`metrics/hunk-stats-2026-09-06.md` and drove two of the three rule changes below.

| chapter | pages | pdf_tokens | md_tokens | matched | unmatched | hunks | inline-math | spurious (hand) | real (hand) | running-matter suspects |
|---|---|---|---|---|---|---|---|---|---|---|
| ch05 | 30 | 11842 | 11851 | 339 | 43 | 57 | 9 | 9 | 39 | 1 |
| ch06 | 35 | 16075 | 17527 | 393 | 60 | 82 | 8 | 1 | 73 | 0 |

Real (hand) = mineru text defects + non-text regions emitted as text + the move pair such a
block produces when it fails verbatim matching. Spurious = alignment artefacts where nothing
is lost. Both chapters are under the gate's spurious < 10.

## Classification

| class | ch05 | ch06 |
|---|---|---|
| real: word split at a former hyphenation point | 24 | 44 |
| real: dropped character or punctuation (line-final glyph, apostrophe, final period) | 7 | 10 |
| real: chapter-opener drop cap dropped | 1 | 1 |
| real: em dash rendered `- ` | 0 | 2 |
| real: one paragraph duplicated 15× (`p026-b007`, five hunks) | 0 | 5 |
| real: margin icon emitted as `page_aside_text` text `#` | 2 | 4 |
| real: Connect logo emitted as a `title` (PDF side: its `®` glyph) | 2 | 1 |
| real: move pair of a block that failed for one of the reasons above | 3 | 6 |
| inline-math (owning block has an `equation_inline` span; review items, counted by the tool) | 9 | 8 |
| spurious: cross-page paragraph merge, block otherwise clean | 6 | 0 |
| spurious: cross-page merge, block also defective | 2 | 0 |
| spurious: Table 5.1 footnotes listed in Table 5.2's caption list, PDF stream order differs | 1 | 0 |
| spurious: display-formula glyph whose word box a trailing U+202F widens 5.5 pt past the mask | 0 | 1 |
| total | 57 | 82 |

Inline-math hunks: spacing around `= + ,` after `flatten_latex`, `\mathbb{S}` for `$`, a lost
`\leq`, lost `rent` subscripts, `560,500` for `$60,500` — MFR review items, not false positives.

## qa_report

- ch05: counts {blocks 450, tables 38, formulas 20, figures 13, diff_hunks 57}; flagged 67 —
  vlm_generated table 38, formula 20, chart 6, figure 2; running_matter_suspect text 1
  (`p016-b015`, a boxed-feature heading typed `page_header`, as predicted by the seven-book
  audit); spot_check 16. Extraction: hybrid-http-client, effort high, mineru 3.4.5.
- ch06: counts {blocks 521, tables 31, formulas 18, figures 5, diff_hunks 82}; flagged 50 —
  table 31, formula 18, chart 1; suspects 0; spot_check 20.
- Both validate with `qa_schema.validate`; every flagged crop and spot-check crop exists.

## Rules added or changed during tuning (RED-first from captured strings, `tests/test_normalize.py`)

- `drop_zero_width_spaces` — rule 8, appended to both tuples. U+200B, which PyMuPDF emits as
  words of its own or glued to glyphs where display formulas are set as running text (246 and
  227 such PDF words in ch05/ch06, mostly inside masked formulas). ch06 87 → 83.
- `drop_bullets_and_list_markers` — narrowed to `- `/`* `; numbered markers stay on both sides.
  Digit stripping ate a sentence-final `0.` at a PDF line start (ch06) and was asymmetric
  wherever PyMuPDF sets a bold ordinal on its own line (corpfin 11 and strat 21 hunks in the
  eight-chapter sample); no side ever drops a real list number. ch06 83 → 82.
- `drop_soft_hyphens` — a soft hyphen at a line end now joins the word it broke. The stats text
  layer has 143 such line ends and mineru holds the joined word (stats 265 → 141); bma
  unchanged; one wrong join in strat where U+00AD marks a plain line break.

Control page after all three: 48/48 blocks, 0 hunks, 2495 = 2495 tokens; table 4, formula 3
(2 inline-math), chart 3 hunks unchanged.

## Decisions taken at the gate

- Mask pad stays 2 pt: pad 4 changes nothing, pad 6 fixes the one masking hunk but swallows
  body words in ch05 (57 → 59).
- No cross-page carry in the alignment: a strict tail/head variant gives ch05 57 → 54 and ch06
  unchanged, and the merged paragraph is desirable output; the stage-5 pre-pass resolves these
  as moves.
- Icon `#` blocks and logo titles count as real: the output is wrong and stage 5 drops them.

## Real hunks left for stage 5

ch05: 39 on printed pages 119 (1), 121 (1), 123 (2), 124 (1), 125 (3), 126 (1), 127 (1), 128 (3),
131 (3), 132 (1), 134 (3), 135 (1), 137 (4), 138 (3), 139 (4), 140 (3), 142 (1), 143 (1), 146 (2).
ch06: 73 on printed pages 149 (1), 150 (3), 151 (1), 152 (3), 153 (1), 155 (4), 156 (1), 157 (1),
158 (5), 159 (1), 160 (5), 161 (2), 163 (5), 164 (2), 165 (1), 166 (3), 167 (2), 168 (1), 169 (3),
170 (2), 171 (5), 172 (1), 175 (5), 176 (1), 177 (2), 178 (1), 181 (1), 182 (3), 183 (2).
Dominant mechanism (bkm reviewer, `chapter_middle.json`): mineru keeps a glyph only if its
centre lies strictly inside the OCR detection span, which ends short of the last glyph at a
right-justified margin — the line-final letter and trailing-superscript losses above.
