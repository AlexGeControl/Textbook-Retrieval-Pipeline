# MinerU block-type evidence — ch05 of all seven books (+ bma ch06), 2026-09-06

Counts only; no book text. Reproduce: `make split extract BOOK=<id> CH=5` per book, then tally
`type` over `work/<id>/ch05/chapter/hybrid_auto/chapter_content_list*.json`. mineru 3.4.5,
`hybrid-http-client --effort high`, routing from `config/books.yaml` (strat: `-f false`).

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
| strat ch05 | 182–215 | 34 | 25 s | mineru ok; wrapper postcondition failed: p33 is a blank trailing page (0 text-layer words, 0 images), `content_list` ends at p32 while `_middle.json.pdf_info` has 34 entries → `check_outputs` fixed to count pages from `pdf_info` |

Client on GPU 1 (A6000; mineru reports `vram=47GB`), peak 7.8 GB; GPU 0 (vLLM) flat.

## content_list (v1) block types

| chapter | blocks | aside_text | chart | equation | footer | header | image | list | page_footnote | page_number | ref_text | table | text |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| acct/ch05 | 836 | 0 | 0 | 1 | 8 | 17 | 26 | 10 | 0 | 1 | 0 | 80 | 693 |
| bkm/ch05 | 506 | 1 | 16 | 38 | 0 | 42 | 9 | 15 | 18 | 42 | 0 | 22 | 303 |
| bma/ch05 | 450 | 17 | 6 | 20 | 0 | 39 | 7 | 22 | 20 | 30 | 0 | 38 | 251 |
| bma/ch06 | 521 | 23 | 1 | 18 | 0 | 41 | 4 | 30 | 13 | 35 | 0 | 31 | 325 |
| corpfin/ch05 | 545 | 0 | 7 | 33 | 0 | 64 | 11 | 30 | 6 | 36 | 0 | 39 | 319 |
| ops/ch05 | 392 | 0 | 7 | 42 | 0 | 5 | 19 | 32 | 0 | 27 | 0 | 5 | 255 |
| stats/ch05 | 771 | 0 | 2 | 78 | 0 | 51 | 3 | 81 | 3 | 51 | 0 | 40 | 462 |
| strat/ch05 | 445 | 0 | 2 | 0 | 33 | 17 | 0 | 40 | 1 | 31 | 12 | 4 | 305 |

New vs. design §2 / `src/blocks.py` (2026-09-06 morning): `aside_text`, `footer`, `ref_text`.
`sub_type`: `image/flowchart` 16, `image/text_image` 1, `list/text` 251, `list/ref_text` 9,
`chart/{line 22, bar 9, other 5, violin 3, histogram 1, state_timeline 1}`.

## content_list_v2 block types (same 8 chapters; 1:1 with v1 on every page, identical order)

`paragraph` 2329, `title` 584, `page_header` 276, `list` 272, `table` 259, `page_number` 253,
`equation_interline` 230, `image` 79, `page_footnote` 61, `chart` 41, `page_aside_text` 41,
`page_footer` 41. Span types inside text-bearing blocks: `text` 3763, `equation_inline` 293
(+28 inside list items), caption spans 139 (all `text`). `ref_text` becomes
`list/reference_list`. v2 text spans are unescaped (bma ch05: 0 `\$` vs 59 in v1; 346/346
plain-text blocks identical to v1 after unescaping v1).

## Findings

1. `_middle.json.discarded_blocks` holds `header`, `page_number`, `page_footnote`, `aside_text`,
   `footer` (v2: `page_*`). All five are absent from `chapter.md` (`page_footnote` 1/61 blocks with
   ≥12 chars appear there, `footer` 1/35). Design §6 had assumed only `header`/`page_number`.
2. `footer`: strat 33/33 are genuine running footers (bbox y 926–938 of 1000, alternating
   part/chapter). acct 8/8 sit at y 854–907 and are body/table fragments (a solution label, a key-terms
   heading, a table header row, table cells) mislabeled on a reflowed e-book.
3. `header` on reflowed e-books is body text: acct 17/17 (section titles, sentence fragments,
   table rows; acct has no running headers and a single `page_number` block), ops 4/5. bma, bkm,
   corpfin, stats, strat headers are genuine running matter. Dropping `header`/`footer` PDF words
   by type would hide text loss on acct/ops.
4. `aside_text`: bma 40 = margin callouts (label, icon glyph, title, URL); bkm 1 = part label on
   the opener. `ref_text`: strat 12 bibliography entries (in `para_blocks`, present in the `.md`).
5. `image` blocks carry VLM-generated `content` when `sub_type` is `flowchart` (16/16; generated
   mermaid with transcribed numbers) or `text_image` (1/1; transcribed spreadsheet screenshot);
   the 62 untyped images have none. `chart` content 41/41. Design §7 flagged only
   table/equation/chart.
6. `title` blocks (v2) / `text_level` (v1): acct 179 on 82 pages, strat 84 on 34 — the heading
   tree for stage 5 is dense on those books.
