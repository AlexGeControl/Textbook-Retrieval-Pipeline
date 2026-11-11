# Tier A — table

Input: the crop image, the table HTML (patches applied), `rows`/`cols` from the checks, and the
spotlight tokens (`textlayer_diff`: tokens the text layer and the HTML disagree on).

Answer (JSON only, schema `answer-schema.json`):
- `rows`, `cols`: what the crop shows, header rows included.
- `match`: true only if every cell value in the crop equals the HTML cell at the same position.
- `discrepancies`: one entry per differing cell — `where` is `r<row>c<col>` (1-based), `crop` is
  the value you read, `html` is the value in the HTML; for a spotlight token that is a mere
  tokenization difference (a split like `$ 1,000`, an en space, a footnote mark inside a cell),
  add `{"where": "<token>", "crop": "<as printed>", "html": "<as in HTML>", "resolution":
  "artefact"}`; for a real error use `"resolution": "error"`.
- `note`: one sentence at most.

Obtain the HTML with:
`uv run python -c "from src.review import Chapter; ch=Chapter('<book>',<n>); print({b.id:b for b in ch.patched_blocks()}['<block>'].html)"`
