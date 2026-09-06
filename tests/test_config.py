from pathlib import Path

import yaml


def test_books_yaml_matches_landing_zone():
    cfg = yaml.safe_load(Path("config/books.yaml").read_text())["books"]
    assert set(cfg) == {"bkm", "bma", "ops", "strat", "stats", "corpfin", "acct"}
    for bid, b in cfg.items():
        assert b["pdf"] == f"books/{bid}/{bid}.pdf"
