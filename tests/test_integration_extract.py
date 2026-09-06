"""Regenerates tests/fixtures/cache/ against the live server. Run: uv run pytest -m integration."""

import os

import pytest

from src.extract import check_outputs, run
from tests.helpers import CACHE, FIXTURE_SETS, FIXTURES

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("book", "name"), sorted(FIXTURE_SETS))
def test_regenerate_fixture_cache(book, name):
    url = os.environ.get("MINERU_SERVER_URL")
    assert url, "MINERU_SERVER_URL must point at the running server"
    pdf = FIXTURES / book / f"{name}.pdf"
    out = run(pdf, CACHE / book / name, url, {"inline_formula": True}, force=True, stem=name)
    check_outputs(out, FIXTURE_SETS[(book, name)], stem=name)
