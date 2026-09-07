# Tier A — text block (spot check or running-matter suspect)

Input: the crop image and the block text (patches applied).

Answer (JSON only): `match` true only if the crop text equals the block text word for word
(hyphenation and line breaks excepted). `discrepancies`: `where` = the word position, `crop` /
`html` = the differing words. In `note` say one of: `body text`, `heading`, `running head`,
`folio`, `caption` — what the crop shows this block to be. `rows`/`cols` null.

Obtain the text with:
`uv run python -c "from src.review import Chapter; ch=Chapter('<book>',<n>); print({b.id:b for b in ch.patched_blocks()}['<block>'].text())"`
