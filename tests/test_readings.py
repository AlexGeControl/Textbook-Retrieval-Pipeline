from src.readings import list_chapters, load_readings, outline_chapters

TOC = [
    [1, "Part One", 1],
    [2, "1: Intro", 1],
    [3, "1-1: A", 1],
    [2, "2: Second", 3],
    [1, "Part Two", 5],
    [2, "3: Third", 5],
]
CFG = {"toc": {"chapter_level": 2, "chapter_pattern": r"^(\d+):"}, "chapter_ranges": {}}


def test_missing_course_file_means_no_reading_list(tmp_path):
    assert load_readings("fmba", tmp_path) is None
    assert list_chapters("ops", CFG, TOC, None) == [1, 2, 3]


def test_book_absent_from_reading_list_means_all_chapters(tmp_path):
    (tmp_path / "mitx.yaml").write_text("bma: [5, 6]\n")
    readings = load_readings("mitx", tmp_path)
    assert readings == {"bma": [5, 6]}
    assert list_chapters("bkm", CFG, TOC, readings) == [1, 2, 3]


def test_reading_list_wins_when_it_names_the_book(tmp_path):
    (tmp_path / "mitx.yaml").write_text("bma: [6, 5, 5]\n")
    assert list_chapters("bma", CFG, TOC, load_readings("mitx", tmp_path)) == [5, 6]


def test_chapter_ranges_add_chapters_the_outline_lacks():
    cfg = {**CFG, "chapter_ranges": {"ch09": [10, 12]}}
    assert list_chapters("x", cfg, TOC, None) == [1, 2, 3, 9]


def test_unconfigured_outline_yields_nothing():
    cfg = {"toc": {"chapter_level": None, "chapter_pattern": None}, "chapter_ranges": {}}
    assert outline_chapters(TOC, cfg) == []
    assert list_chapters("x", cfg, TOC, None) == []


def test_shipped_mitx_reading_list_is_the_benchmark():
    assert load_readings("mitx") == {"bma": [5, 6]}
