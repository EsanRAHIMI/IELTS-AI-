"""An item stays visible only while one of its sources is still open."""
from sources.freeze import active_item_query, index_in_full, item_is_frozen, without_frozen_questions


def test_an_item_needs_one_open_source():
    open_ids = {"source-a"}
    assert item_is_frozen(["source-a", "source-b"], open_ids) is False
    assert item_is_frozen(["source-b"], open_ids) is True
    assert item_is_frozen([], open_ids) is True
    assert item_is_frozen(None, open_ids) is True
    assert item_is_frozen("source-a", open_ids) is False
    assert item_is_frozen(["source-a"], set()) is True


def test_active_query_matches_only_open_sources():
    assert active_item_query(set()) == {"sourceIds": {"$in": []}}
    query = active_item_query({"source-a"})
    assert set(query["sourceIds"]["$in"]) == {"source-a"}


def test_a_filtered_quiz_place_maps_back_onto_the_stored_list():
    full = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    kept = [{"id": "a"}, {"id": "c"}]
    assert index_in_full(full, kept, 1) == 2
    assert index_in_full(full, kept, 0) == 0
    assert index_in_full(full, kept, 9) == 3


def test_quiz_skips_a_frozen_question_and_keeps_the_place():
    questions = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    kept, index = without_frozen_questions(questions, 1, {"b"})
    assert [item["id"] for item in kept] == ["a", "c"]
    assert index == 1

    kept, index = without_frozen_questions(questions, 0, {"a"})
    assert [item["id"] for item in kept] == ["b", "c"]
    assert index == 0

    kept, index = without_frozen_questions(questions, 2, {"a", "b"})
    assert [item["id"] for item in kept] == ["c"]
    assert index == 0
