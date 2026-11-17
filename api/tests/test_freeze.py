"""Freezing a source hides only the content that has nowhere else to live."""
from sources.freeze import active_item_query, index_in_full, item_is_frozen, without_frozen_questions


def test_shared_item_stays_when_one_source_is_frozen():
    frozen = {"source-b"}
    assert item_is_frozen(["source-a", "source-b"], frozen) is False
    assert item_is_frozen(["source-b"], frozen) is True
    assert item_is_frozen([], frozen) is False
    assert item_is_frozen(None, frozen) is False
    assert item_is_frozen(["source-b"], set()) is False


def test_active_query_is_empty_until_something_is_frozen():
    assert active_item_query(set()) == {}
    query = active_item_query({"source-b"})
    assert "$nor" in query
    assert "source-b" in query["$nor"][0]["sourceIds"]["$not"]["$elemMatch"]["$nin"]


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
