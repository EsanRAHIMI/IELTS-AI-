"""A refresh keeps today's remaining study cards instead of restarting the session."""
from study.day_progress import hidden_source, remaining_ids, session_for_reload, session_without_card, today_key


def test_reviewed_cards_are_left_out_of_the_session():
    cards = ["a", "b", "c", "d"]
    assert remaining_ids(cards, ["a", "c"]) == ["b", "d"]


def test_remaining_order_matches_the_original_session():
    assert remaining_ids(["c", "a", "b"], []) == ["c", "a", "b"]


def test_reported_card_leaves_the_session_and_stays_out():
    kept, reviewed = session_without_card(["a", "b", "c"], ["a"], "b")
    assert kept == ["a", "c"]
    assert remaining_ids(kept, reviewed) == ["c"]


def test_hidden_source_is_not_shown_again():
    hidden = {("word", "word-1")}
    assert hidden_source({"type": "word", "refId": "word-1"}, hidden)
    assert hidden_source({"type": "phrase", "refId": "word-1"}, hidden) is False


def test_reload_after_finishing_returns_the_same_cards():
    finished = remaining_ids(["a", "b", "c"], ["a", "b", "c"])
    assert finished == []
    cards, reviewed = session_for_reload(["a", "b", "a", "c"])
    assert cards == ["a", "b", "c"]
    assert remaining_ids(cards, reviewed) == ["a", "b", "c"]


def test_progress_key_is_per_user_and_day():
    assert today_key("user-1", "2026-11-15") == "user-1:2026-11-15"
    assert today_key("user-2", "2026-11-15") != today_key("user-1", "2026-11-15")
