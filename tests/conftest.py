import pytest

from tests.helpers import cached_hybrid_auto


@pytest.fixture
def table_cache():
    return cached_hybrid_auto("bma", "table")


@pytest.fixture
def formula_cache():
    return cached_hybrid_auto("bma", "formula")


@pytest.fixture
def chart_cache():
    return cached_hybrid_auto("bkm", "chart")


@pytest.fixture
def text_only_cache():
    return cached_hybrid_auto("bkm", "text-only")
