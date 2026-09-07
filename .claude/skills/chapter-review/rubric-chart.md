# Tier A — chart, flowchart, text image

Input: the crop image and the block's `content` (a Markdown data table for a chart, mermaid for
a flowchart, a transcription for a text image).

Answer (JSON only): `match` true only if every series, category, value label, node and edge in
the crop appears in the content and nothing in the content is absent from the crop. For charts
without printed values, `match` is true when categories, series names and the ordering of
magnitudes agree; say so in `note`. `discrepancies` as for tables (`where` = the label or node).
`rows`/`cols` = the data table's shape when the content is a table, else null.

Obtain the content with:
`uv run python -c "from src.review import Chapter; ch=Chapter('<book>',<n>); print({b.id:b for b in ch.patched_blocks()}['<block>'].content)"`
