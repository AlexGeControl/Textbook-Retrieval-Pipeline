import json

import pymupdf
import pytest

from tests.helpers import FIXTURE_SETS, FIXTURES, cached_hybrid_auto


@pytest.mark.parametrize(("book", "name"), sorted(FIXTURE_SETS))
def test_cached_output_matches_fixture_pdf(book, name):
    hybrid_auto = cached_hybrid_auto(book, name)
    pdf = FIXTURES / book / f"{name}.pdf"
    assert pdf.exists(), f"fixture PDF missing: {pdf}"
    pages = pymupdf.open(pdf).page_count
    assert pages == FIXTURE_SETS[(book, name)]
    content_list = json.loads((hybrid_auto / f"{name}_content_list.json").read_text())
    assert max(b["page_idx"] for b in content_list) + 1 == pages
    for suffix in (".md", "_content_list_v2.json", "_middle.json"):
        assert (hybrid_auto / f"{name}{suffix}").exists(), suffix
    assert (hybrid_auto / "images").is_dir()
