"""Home counts come from stored cards and source titles."""
from progress.home import library_progress, listed_sources


def test_card_statuses_keep_due_separate_from_learning():
    progress = library_progress({"new": 10, "learning": 2, "review": 3, "mastered": 4}, 5)
    assert progress == {"new": 10, "learning": 5, "due": 5, "mastered": 4, "studied": 9}


def test_missing_cards_are_zero():
    assert library_progress({}, 0)["studied"] == 0
    assert library_progress(None, -3)["due"] == 0


def test_source_names_skip_blanks_and_keep_order():
    assert listed_sources([" Cambridge ", "", None, "Notes"], limit=3) == (["Cambridge", "Untitled", "Notes"], 0)
    assert listed_sources(["a", "b", "c"], limit=2) == (["a", "b"], 1)
