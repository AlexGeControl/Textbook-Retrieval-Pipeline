# books/ — PDF landing zone

One directory per corpus ID from `config/books.yaml`, one file `<id>/<id>.pdf`.
Keep the original PDF as well if you renamed it — drop it in the same directory;
only the `<id>.pdf` name is referenced by config.

    books/bkm/bkm.pdf          Bodie, et al.,Investments 13e
    books/bma/bma.pdf          Brealey et al., Principles of Corporate Finance 14e
    books/ops/ops.pdf          Cachon & Terwiesch, Matching Supply with Demand 5e
    books/strat/strat.pdf      Dess et al., Strategic Management 13e
    books/stats/stats.pdf      Anderson et al., Statistics for Business and Economics 15e
    books/corpfin/corpfin.pdf  Ross et al., Corporate Finance 13e
    books/acct/acct.pdf        Pratt, Financial Accounting 11e

Rules:
- Nothing under `books/` is committed except this README, `.gitkeep` files and
  `manifest.json` (hashes and page counts only). `.gitignore` enforces this.
- After dropping files in, run `uv run scripts/check_books.py`. It fails if a
  book is missing, lacks a text layer, or has no outline and no
  `manual_ranges` entry. Fix `config/books.yaml` until it passes.
- Set `toc.chapter_level`, `toc.chapter_pattern` and `toc.page_offset` in
  `config/books.yaml` once you have looked at the outline (`printed = pdf_1based -
  page_offset`; stage 1 prefers PDF page labels and only falls back to the offset).
  `body_range` is the 0-based index range `scripts/check_books.py` samples.
- If a book's outline does not fit `chapter_level` + `chapter_pattern` (unnumbered
  chapter titles, section numbers split from titles), add `toc.patches` rules and run
  `uv run scripts/patch_toc.py <id>` (dry run), then `--apply`. The outline is rewritten
  in `<id>.pdf` itself; the untouched original stays next to it as `<id>.orig.pdf`. Run
  `scripts/check_books.py` afterwards to refresh the manifest hash.
