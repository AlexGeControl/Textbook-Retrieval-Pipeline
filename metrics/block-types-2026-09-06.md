# MinerU block-type evidence — ch05 of all seven books (+ bma ch06), 2026-09-06

Counts only; no book text. Reproduce: `make split extract BOOK=<id> CH=5` per book, then load
`work/<id>/ch05/chapter/hybrid_auto/chapter_content_list_v2.json` with `src.blocks.load_pages`.
mineru 3.4.5, `hybrid-http-client --effort high`, routing from `config/books.yaml` (strat: `-f false`).
Restated in `content_list_v2` terms after the anchor moved to v2 (design amendment, same day); the
original v1 tables are in git history (`095cbc1`). v1 → v2 names: `text` → `paragraph` + `title`,
`equation` → `equation_interline`, `header`/`footer`/`aside_text` → `page_header`/`page_footer`/
`page_aside_text`, `ref_text` → `list` with `reference_list`. v1 and v2 are 1:1 per page in
identical order on all 4,466 blocks.

## Runs

| chapter | pdf pages (0-based) | pages | wall | result |
|---|---|---|---|---|
| acct ch05 | 269–350 | 82 | 34 s | ok |
| bkm ch05 | 153–194 | 42 | 26 s | ok |
| bma ch05 | 149–178 | 30 | 26 s | ok (gate 2) |
| bma ch06 | 179–213 | 35 | 26 s | ok (gate 2) |
| corpfin ch05 | 165–200 | 36 | 24 s | ok |
| ops ch05 | 185–239 | 55 | 26 s | ok |
| stats ch05 | 253–304 | 52 | 32 s | ok |
| strat ch05 | 182–215 | 34 | 25 s | mineru ok; wrapper postcondition failed: p33 is a blank trailing page (0 text-layer words, 0 images), `content_list` ends at p32 while `_middle.json.pdf_info` has 34 entries → `check_outputs` fixed to count pages from `pdf_info` (`85bc35e`) |

Client on GPU 1 (A6000; mineru reports `vram=47GB`), peak 7.8 GB; GPU 0 (vLLM) flat.

## content_list_v2 block types

| chapter | blocks | pages | blank | paragraph | title | list | table | equation_interline | chart | image | page_header | page_footer | page_number | page_footnote | page_aside_text |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| acct/ch05 | 836 | 82 | 0 | 514 | 179 | 10 | 80 | 1 | 0 | 26 | 17 | 8 | 1 | 0 | 0 |
| bkm/ch05 | 506 | 42 | 0 | 242 | 61 | 15 | 22 | 38 | 16 | 9 | 42 | 0 | 42 | 18 | 1 |
| bma/ch05 | 450 | 30 | 0 | 202 | 49 | 22 | 38 | 20 | 6 | 7 | 39 | 0 | 30 | 20 | 17 |
| bma/ch06 | 521 | 35 | 0 | 268 | 57 | 30 | 31 | 18 | 1 | 4 | 41 | 0 | 35 | 13 | 23 |
| corpfin/ch05 | 545 | 36 | 0 | 274 | 45 | 30 | 39 | 33 | 7 | 11 | 64 | 0 | 36 | 6 | 0 |
| ops/ch05 | 392 | 55 | 0 | 225 | 30 | 32 | 5 | 42 | 7 | 19 | 5 | 0 | 27 | 0 | 0 |
| stats/ch05 | 771 | 52 | 0 | 383 | 79 | 81 | 40 | 78 | 2 | 3 | 51 | 0 | 51 | 3 | 0 |
| strat/ch05 | 445 | 34 | 1 | 221 | 84 | 52 | 4 | 0 | 2 | 0 | 17 | 33 | 31 | 1 | 0 |
| **total** | 4466 | 366 | 1 | 2329 | 584 | 272 | 259 | 230 | 41 | 79 | 276 | 41 | 253 | 61 | 41 |

No `code`, `algorithm`, `index` or `phonetic` in this corpus (they would raise `BlockError`).

## Spans, sub-types and the VLM set

| chapter | text spans (body) | `equation_inline` spans (body) | blocks with inline math | caption text spans | tables simple / complex | lists text / reference | images with `content` / without | VLM blocks (crop file exists) |
|---|---|---|---|---|---|---|---|---|
| acct/ch05 | 768 | 1 | 1 | 26 | 54 / 26 | 9 / 1 | 7 / 19 | 88 (88) |
| bkm/ch05 | 588 | 85 | 44 | 32 | 14 / 8 | 15 / 0 | 0 / 9 | 76 (76) |
| bma/ch05 | 479 | 17 | 11 | 21 | 15 / 23 | 22 / 0 | 2 / 5 | 66 (66) |
| bma/ch06 | 608 | 10 | 6 | 10 | 13 / 18 | 30 / 0 | 0 / 4 | 50 (50) |
| corpfin/ch05 | 565 | 5 | 5 | 18 | 32 / 7 | 30 / 0 | 0 / 11 | 79 (79) |
| ops/ch05 | 472 | 54 | 32 | 13 | 4 / 1 | 32 / 0 | 6 / 13 | 60 (60) |
| stats/ch05 | 1202 | 149 | 66 | 26 | 32 / 8 | 81 / 0 | 2 / 1 | 122 (122) |
| strat/ch05 | 706 | 0 | 0 | 6 | 2 / 2 | 32 / 20 | 0 / 0 | 6 (6) |
| **total** | 5388 | 321 | 165 | 152 | 166 / 93 | 251 / 21 | 17 / 62 | 547 (547) |

`equation_inline` spans inside captions: 0. `complex_table` = colspan/rowspan or nested. Images with
`content`: `flowchart` 16 (acct 7, ops 6, stats 2, bma 1), `text_image` 1 (bma); the 62 without
`content` have no `sub_type`. Chart `sub_type`: line 22, bar 9, other 5, violin 3, histogram 1,
state_timeline 1 (all 41 carry a data table in `content`). VLM set = table + equation_interline +
chart + image-with-content; every one of the 547 has its `image_source` file under `images/`.

## Title levels

| chapter | level 1 | level 2 | deeper |
|---|---|---|---|
| acct/ch05 | 0 | 179 | 0 |
| bkm/ch05 | 1 | 60 | 0 |
| bma/ch05 | 1 | 48 | 0 |
| bma/ch06 | 1 | 56 | 0 |
| corpfin/ch05 | 2 | 43 | 0 |
| ops/ch05 | 5 | 25 | 0 |
| stats/ch05 | 1 | 78 | 0 |
| strat/ch05 | 3 | 81 | 0 |

## Running matter and `running_matter_suspect`

Heuristic (design §7): a `page_header`/`page_footer`/`page_number` block is running matter when its
folded text is a folio (digits, roman numerals, `Page N`), starts with `Chapter`/`Part` (letter-spaced
caps joined first), repeats verbatim on ≥2 pages, or contains the chapter title. Everything else is a
suspect. Two refinements came out of this audit: `Page N` folios (ops writes them as words, 20 blocks)
and letter-spaced caps (bma's opener label, 2 blocks).

| chapter | running-matter blocks | suspects | header / footer / number | what the suspects are (hand classification) |
|---|---|---|---|---|
| acct/ch05 | 26 | 23 | 16 / 6 / 1 | 8 section or box headings, 7 sentence fragments, 7 table rows/cells/labels, 1 folio-like token — all real (the `.md` dropped them) |
| bkm/ch05 | 84 | 0 | – | – |
| bma/ch05 | 69 | 1 | 1 / 0 / 0 | boxed-feature heading — real |
| bma/ch06 | 76 | 0 | – | – |
| corpfin/ch05 | 100 | 0 | – | – |
| ops/ch05 | 32 | 3 | 3 / 0 / 0 | 1 sentence fragment, 1 exhibit label, 1 section heading — all real |
| stats/ch05 | 102 | 4 | 4 / 0 / 0 | section titles used as the running head on a single page — harmless false positives |
| strat/ch05 | 81 | 6 | 6 / 0 / 0 | 1 photo credit, 5 margin tab numbers — harmless |
| **total** | 570 | 37 | 30 / 6 / 1 | 27 real, 10 harmless |

Suppressing the harmless ones by bbox position or by matching outline titles was rejected: acct's
real mislabels are also section titles at the top of the page.

## Findings

1. The five `_middle.json.discarded_blocks` types are exactly v2's `page_header`, `page_footer`,
   `page_number`, `page_footnote`, `page_aside_text`; the `.md` drops all of them (`page_footnote`
   1/61 blocks with ≥12 chars appear there, `page_footer` 1/35). The guardrail aligns them from v2
   instead of masking them; nothing is dropped by type on the PDF side.
2. `page_footer`: strat 33/33 are genuine running feet (bbox y 926–938 of 1000, alternating
   part/chapter). acct 8/8 sit at y 854–907 and are body/table fragments mislabeled on a reflowed
   e-book.
3. `page_header` on reflowed e-books is body text: acct 17/17 (section titles, sentence
   fragments, table rows; acct has no running heads and a single `page_number` block), ops 4/5.
   bkm, bma, corpfin, stats, strat heads are genuine running matter.
4. `page_aside_text`: bma 40 = margin callouts (label, icon glyph, title, URL); bkm 1 = part label
   on the opener. `reference_list`: strat 20 (bibliography; 12 were v1 `ref_text` blocks and 8
   v1 `list/ref_text`), acct 1.
5. `image` blocks carry VLM `content` only as `flowchart` (generated mermaid with transcribed
   numbers) or `text_image` (transcribed spreadsheet screenshot): 17/79. They are flagged as
   `figure`; the 62 plain images are counted, not flagged.
6. mineru's `title.level` never goes below 2, and acct's chapter title is not recognized as level 1
   (179 level-2 titles, 0 level-1). The outline has 3–4 levels (BMA sections at 3, subsections at 4),
   so stage 5 must take heading hierarchy from `meta.json` (`sections`, `toc_subtree`) and use
   `title` blocks only as anchors.
7. Inline math is a v2 span, never markdown: 321 `equation_inline` spans in 165 blocks, none in
   captions; stats 149, bkm 85, ops 54, bma 27 across two chapters, corpfin 5, acct 1, strat 0
   (`-f false`). This is the `hunks_inline_math` population for gate 3.
8. 93/259 tables are `complex_table` (colspan/rowspan or nested) — bma ch05 23/38, bma ch06
   18/31: the harder half of the table review at gate 3.
9. v2 text spans are unescaped (bma ch05: 0 `\$` vs 59 in v1; 346/346 plain-text blocks identical
   to v1 once v1 is unescaped) and carry `<sup>`/`<sub>` tags only (13 in bma ch05) — the sole
   markup rule left on the md side.
