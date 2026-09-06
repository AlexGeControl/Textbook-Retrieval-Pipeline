# Hunk statistics — eight sample chapters (2026-09-06)

Evidence for the stage-5 design and for the gate-3 decisions. Chapters: bma ch05 and ch06 (the
gate-3 pair) plus ch05 of acct, bkm, corpfin, ops, stats and strat. Each ran `make chapter`
(extraction reused, no GPU) at HEAD `f8b0ba0` — guardrail rules 1–8 including
`drop_zero_width_spaces`. Every hunk was bucketed mechanically, then the residue was read by
hand against one rubric (one reviewer per chapter; bma by the session operator's assistant).
Numbers only; no book text. Working files: `work/gate3/` (gitignored).

## 1. Pipeline counts

| chapter | pages | blocks | pdf tokens | md tokens | matched | unmatched | hunks | inline-math | suspects | tables | formulas | figures |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| acct ch05 | 82 | 836 | 17526 | 17538 | 709 | 33 | 38 | 1 | 23 | 80 | 1 | 26 |
| bkm ch05 | 42 | 506 | 16458 | 16268 | 362 | 72 | 110 | 61 | 0 | 22 | 38 | 25 |
| bma ch05 | 30 | 450 | 11799 | 11808 | 339 | 43 | 57 | 9 | 1 | 38 | 20 | 13 |
| bma ch06 | 35 | 521 | 15989 | 17445 | 392 | 61 | 83 | 8 | 0 | 31 | 18 | 5 |
| corpfin ch05 | 36 | 545 | 15002 | 14957 | 397 | 35 | 51 | 5 | 0 | 39 | 33 | 18 |
| ops ch05 | 55 | 392 | 12814 | 12724 | 265 | 49 | 81 | 43 | 3 | 5 | 42 | 26 |
| stats ch05 | 52 | 771 | 22487 | 21976 | 502 | 163 | 265 | 139 | 4 | 40 | 78 | 5 |
| strat ch05 | 34 | 445 | 20056 | 20077 | 381 | 49 | 92 | 0 | 6 | 4 | 0 | 2 |
| **all** | 366 | 4466 | 132131 | 132793 | 3347 | 505 | 777 | 266 | 37 | | | |

All sixteen `qa_report.json` files validate. Suspects = `running_matter_suspect` flags (acct 23
and ops 3 are the reflowed e-books' mislabeled body text, as predicted in
`metrics/block-types-2026-09-06.md`; strat 6 are margin tab numbers; stats 4 single-page section
heads; bma 1 boxed-feature heading). The ch06 md-token excess is one duplicated block (§4).

## 2. Mechanical classification

First match wins: (a) anchor block has an `equation_inline` span → *inline-math*; (b) a pure
deletion whose words equal a pure insertion elsewhere in the chapter → *move* (cross-page when
the pages differ); (c) equal after removing whitespace and Unicode punctuation → *spacing*
(split word = md has more tokens, joined = fewer, punctuation = same count); (d) equal only after
removing every non-word character → *symbol-only*; else *deletion* / *insertion* / *replace*.
The operator's proposed rule is (c)+(d); it accepts two more hunks than (c) alone (§6).

| chapter | hunks | IM | split | joined | punct | move x-page | move same | icon # | symbol | deletion | insertion | replace | residue |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| acct ch05 | 38 | 1 | 0 | 4 | 6 | 12 | 2 | 0 | 0 | 1 | 9 | 3 | 13 |
| bkm ch05 | 110 | 61 | 6 | 1 | 6 | 9 | 9 | 0 | 0 | 2 | 1 | 15 | 18 |
| bma ch05 | 57 | 9 | 24 | 0 | 2 | 7 | 0 | 2 | 1 | 3 | 3 | 6 | 15 |
| bma ch06 | 83 | 8 | 41 | 0 | 5 | 6 | 4 | 4 | 0 | 2 | 6 | 7 | 19 |
| corpfin ch05 | 51 | 5 | 12 | 2 | 5 | 8 | 0 | 0 | 0 | 10 | 0 | 9 | 19 |
| ops ch05 | 81 | 43 | 0 | 2 | 1 | 18 | 3 | 0 | 0 | 5 | 7 | 2 | 14 |
| stats ch05 | 265 | 139 | 0 | 111 | 0 | 3 | 4 | 0 | 0 | 6 | 1 | 1 | 8 |
| strat ch05 | 92 | 0 | 32 | 0 | 12 | 4 | 6 | 0 | 1 | 22 | 3 | 12 | 38 |
| **all** | 777 | 266 | 115 | 120 | 37 | 67 | 28 | 6 | 2 | 51 | 30 | 55 | 144 |

Residue = everything not inline-math, spacing or move. Spot checks of three random hunks per
bucket per chapter found the buckets right, with two caveats folded into the table above: the
move detector needs both sides ≥ 30 letters for a containment match (two false pairs otherwise),
and the 111 stats *joined* hunks are the PDF side split at soft-hyphen line ends (§4, §5), not md.

## 3. Hand classification of the residue

| chapter | residue | dropped chars | drop cap | duplication | other real | junk md | junk pdf | move | masking | normalization | unknown |
|---|---|---|---|---|---|---|---|---|---|---|---|
| acct ch05 | 13 | 1 | 0 | 0 | 0 | 8 | 0 | 4 | 0 | 0 | 0 |
| bkm ch05 | 18 | 9 | 0 | 0 | 4 | 0 | 0 | 3 | 0 | 1 | 1 |
| bma ch05 | 15 | 5 | 1 | 0 | 0 | 3 | 1 | 5 | 0 | 0 | 0 |
| bma ch06 | 19 | 6 | 1 | 5 | 0 | 5 | 0 | 0 | 1 | 1 | 0 |
| corpfin ch05 | 19 | 4 | 0 | 0 | 1 | 1 | 0 | 2 | 0 | 11 | 0 |
| ops ch05 | 14 | 3 | 0 | 6 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| stats ch05 | 8 | 0 | 0 | 0 | 1 | 1 | 0 | 3 | 1 | 2 | 0 |
| strat ch05 | 38 | 10 | 0 | 0 | 0 | 2 | 0 | 5 | 0 | 21 | 0 |
| **all** | 144 | 38 | 2 | 11 | 6 | 20 | 1 | 27 | 2 | 36 | 1 |

`real/dash` scored 0 here because the dash class lands in *punctuation* mechanically (2 in bma
ch06). Stats shows two labelled items fewer than its residue: they became a detected move pair
after the reviewer's file was cut; the reviewer also called them moves.

## 4. Mechanisms behind the hunks (counts across the eight chapters)

- **Line-final glyph dropped by mineru** — the last narrow glyph (`l`, `r`, `t`, `s`, `y`, `.`) of a right-justified line, or a trailing footnote superscript at a paragraph end, is missing. bkm's reviewer traced it in `chapter_middle.json`: the OCR detection span ends 0.1–7 pt short of the glyph centre and `mineru/utils/span_pre_proc.py` keeps a glyph only if its centre is strictly inside the span. Seen in every book with a text layer margin: bkm 13, strat 10, bma 11, corpfin 4, acct 1, ops 1 (ops's is a block-bbox clip). About 40 of the 144 residue items, i.e. the whole `dropped chars`/`other real` columns bar the ones below.
- **Words split at former hyphenation points** (`spacing/split-word`, 115) and **md joining two words** (`joined` outside stats, 9): mineru's line merge; same letters, resolved by "PDF wins".
- **Cross-page paragraph merge**: mineru appends the next page's opening lines to the previous page's paragraph and leaves an empty paragraph block at the top of the next page (acct 7 empty blocks, strat 1, bma several). 67 `move x-page` hunks plus a handful fused with other causes; nothing lost.
- **Soft hyphens in the text layer** (stats): 143 PDF words end in U+00AD at a line end; rule 4 deletes the hyphen but the line break stays, so the PDF side reads `invest ing` while md has `investing`. 111 stats hunks + 21 of its inline-math hunks. Here the PDF side is the defective one.
- **Rule 6 (`^N. ` list marker) asymmetries**: (i) PyMuPDF puts bold question ordinals on their own line, so the PDF marker is not followed by a space and survives while md's `N. text` is stripped — corpfin 11 and strat 21 residue items (36 ordinals in corpfin alone); (ii) a sentence-final `0.` at a PDF line start is eaten (bma ch06, stats); (iii) strat's md keeps question numbers in a separate block that rule 6 strips to empty. Neither side ever drops a real list number in the sample, so digit stripping never helps.
- **Reflowed e-book folios absorbed into body text** (ops): 9 of 30 `Page N` folios have their centre inside a widened paragraph bbox; 7 are injected mid-sentence, doubled, with the page's `page_number` block left empty. 11 of ops's 14 residue items.
- **Raster/vector UI transcribed as text** (`junk md`, 20): acct's blue *Solution* button 11× (typed title/paragraph/page_footer/page_header), the Connect logo (bma 2, corpfin 1 as two titles), margin icons as `#` (bma 6 `page_aside_text`), stats's DATA-file badge, strat's drawn square bullets as U+53E3/U+25A1. None has text-layer words; all are drop items for stage 5.
- **Duplicated text** (bma ch06 1 block × 15, ops 7 folios × 2): span-level duplication in mineru's text-layer path (`middle.json` holds each line twice), not VLM output.
- **Chapter opener drop cap dropped** (bma ch05, ch06): the large initial letter is not in md's first paragraph. Systematic for this book design; the 103 pt chapter numeral is also text-layer-only (junk pdf).
- **Symbol fonts in the text layer** (stats): MathematicalPi encodes μ as `m`, = as `5`, Σ as `o`, − as `2`; a footnote formula is glyph soup on both sides and the MFR's LaTeX is the better source. `flatten_latex` maps `\\mu` to nothing, so Greek letters can never match. Also bkm's Key Equations list typed `paragraph`: fraction rules arrive as underscore runs.
- **Ligature ﬀ** (ops 2): the PDF has U+FB00 in bold captions; md has a single `f` although mineru maps the ligature — the character stream already lost one `f`.
- **Masking gaps** (2): a display-formula glyph whose word box is widened 5.5 pt by a trailing U+202F (bma ch06); a table total row 8.4 pt below the mask that the VLM's HTML also omits (stats) — a real table-content loss as well.
- **Table footnotes attributed to the next table's caption list** (bma ch05, 1); **two-column exercise table read row-wise by the text layer** (stats, 5 moves); **margin key-term titles consuming the inline bold occurrence** (strat, 3 moves).

## 5. Candidate normalization changes (dry run; no code changed)

`narrow6` = rule 6 strips only `- `/`* ` markers, never `N.`. `shy-join` = rule 4 joins across a
soft hyphen followed by a line break before dropping remaining soft hyphens. hunks / inline-math /
unmatched blocks:

| target | baseline | narrow6 | shy-join | both |
|---|---|---|---|---|
| acct ch05 | 38 / 1 / 33 | 38 / 1 / 33 | 38 / 1 / 33 | 38 / 1 / 33 |
| bkm ch05 | 110 / 61 / 72 | 111 / 62 / 72 | 110 / 61 / 72 | 111 / 62 / 72 |
| bma ch05 | 57 / 9 / 43 | 57 / 9 / 43 | 57 / 9 / 43 | 57 / 9 / 43 |
| bma ch06 | 83 / 8 / 61 | 82 / 8 / 60 | 83 / 8 / 61 | 82 / 8 / 60 |
| corpfin ch05 | 51 / 5 / 35 | 40 / 4 / 34 | 51 / 5 / 35 | 40 / 4 / 34 |
| ops ch05 | 81 / 43 / 49 | 81 / 43 / 49 | 81 / 43 / 49 | 81 / 43 / 49 |
| stats ch05 | 265 / 139 / 163 | 264 / 139 / 163 | 141 / 118 / 77 | 140 / 118 / 76 |
| strat ch05 | 92 / 0 / 49 | 72 / 0 / 45 | 93 / 0 / 49 | 73 / 0 / 45 |
| bkm/text-only | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| bma/table | 4 / 0 / 3 | 4 / 0 / 3 | 4 / 0 / 3 | 4 / 0 / 3 |
| bma/formula | 3 / 2 / 3 | 3 / 2 / 3 | 3 / 2 / 3 | 3 / 2 / 3 |
| bkm/chart | 3 / 0 / 2 | 3 / 0 / 2 | 3 / 0 / 2 | 3 / 0 / 2 |
| **eight chapters, hunks** | 777 | 745 | 654 | 622 |

Exceptions found: `narrow6` exposes previously hidden dropped periods after ordinals (strat 2,
bkm 1 — genuine defects that digit stripping had masked) and splits one merged bkm hunk in two;
`shy-join` wrongly joins one strat line end where U+00AD marks a plain line break (`be` +
`selective`), 1 wrong join against 143 right ones. Both leave the control page at 48/48 blocks,
0 hunks. Both were applied RED-first at gate 3 on the operator's go (`src/normalize.py`,
`tests/test_normalize.py`); re-running stages 3–4 on all eight chapters afterwards gave acct 38,
bkm 111, bma ch05 57, bma ch06 82, corpfin 40, ops 81, stats 140, strat 73 — 622 hunks, as the
dry run predicted.

## 6. Implications for the stage-5 pre-pass

- Of 777 hunks, 367 (47 %) are same-letters or pure moves and can be resolved mechanically; 266 (34 %) anchor inline-math blocks; 144 (18 %) need eyes. Inside the residue, 21 are UI/ornament junk and 36 are rule-6 artefacts, leaving about 60 genuine defects in 366 pages — roughly one per 6 pages.
- "Accept the PDF text" is right for split words, md-joined words, dropped punctuation and dashes, and wrong where the PDF side is the defective one: soft-hyphen line ends (stats), symbol-font stand-ins for Greek letters and operators (stats), the strat plain-line-break soft hyphen, ornaments such as `®` and drawn bullets, and chapter numerals. Stripping punctuation but keeping symbols (Unicode category S) removes the `®`/`≤` cases mechanically (2 hunks); the soft-hyphen and symbol-font cases need the normalization fixes above or a per-book rule, not a pattern list.
- Inline-math anchors need their own action: keep the MFR LaTeX, mark it verified when the flattened letters match the text layer, and review the rest (`\\mathbb{S}` for `$`, lost subscripts, `560,500` for `$60,500`). The text layer is not ground truth for math glyphs in stats.
- The move filter must be chapter-wide and allow one insertion to pair with several deletions (stats's row-wise table) and a deletion to pair with an inline-math insertion (bma, bkm). The cross-page merge itself is desirable output; only its empty next-page block needs no action.
- Stage-5 drop list from this sample: acct *Solution* buttons, Connect logos, `#` margin icons, DATA-file badges, drawn bullets, folios injected into ops body text, duplicated spans. All are identifiable by "md words with no text-layer words in the block bbox", which is the general discriminator, not the token.
- The line-final glyph loss is the dominant genuine defect and has a known mechanism in mineru's span assignment; it is worth a targeted fix or upstream report before scaling to whole books, since it recurs at every right-justified margin.
