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
- Set `toc.page_offset` in `config/books.yaml` once you know the printed-page
  vs PDF-index offset for each book; the manifest's first outline titles
  help you find it.
