"""A refresh keeps today's remaining study cards instead of restarting the session."""
from study.day_progress import remaining_ids, today_key


def test_reviewed_cards_are_left_out_of_the_session():
    cards = ["a", "b", "c", "d"]
    assert remaining_ids(cards, ["a", "c"]) == ["b", "d"]


def test_remaining_order_matches_the_original_session():
    assert remaining_ids(["c", "a", "b"], []) == ["c", "a", "b"]


def test_progress_key_is_per_user_and_day():
    assert today_key("user-1", "2026-11-15") == "user-1:2026-11-15"
    assert today_key("user-2", "2026-11-15") != today_key("user-1", "2026-11-15")
