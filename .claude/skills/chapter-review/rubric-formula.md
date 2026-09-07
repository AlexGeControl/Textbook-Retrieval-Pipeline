# Tier A — display formula

Input: the crop image and the LaTeX (patches applied).

Answer (JSON only): `match` true only if every symbol, subscript, superscript, operator,
fraction bar, summation limit and tag in the crop appears in the LaTeX with the same structure.
`discrepancies`: one entry per difference — `where` a short locator ("second term",
"subscript of C"), `crop` what the image shows, `html` what the LaTeX says, `resolution`
"error". Spacing inside the LaTeX (`C _ { 0 }`) is never a discrepancy. `rows`/`cols` are null.

Obtain the LaTeX with:
`uv run python -c "from src.review import Chapter; ch=Chapter('<book>',<n>); print({b.id:b for b in ch.patched_blocks()}['<block>'].math)"`
