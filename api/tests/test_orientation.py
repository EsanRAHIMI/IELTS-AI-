"""The prep stage comes from stored counts, one stage at a time."""
from progress.orientation import prep_orientation


def _facts(**overrides):
    base = dict(
        sources=1,
        words=10,
        phrases=2,
        patterns=1,
        cards=8,
        due_study=0,
        due_review=0,
        quiz_ready=True,
    )
    base.update(overrides)
    return prep_orientation(**base)


def test_empty_library_is_import():
    step = _facts(sources=0, words=0, phrases=0, patterns=0, cards=0, quiz_ready=False)
    assert step["stage"] == "import"
    assert step["href"] == "/import"
    assert step["action"] == "Import a source"


def test_source_without_items_stays_on_import():
    step = _facts(sources=2, words=0, phrases=0, patterns=0, cards=0, quiz_ready=False)
    assert step["stage"] == "import"
    assert step["action"] == "Check Import Center"


def test_material_without_cards_is_the_daily_plan():
    step = _facts(cards=0, quiz_ready=False)
    assert step["stage"] == "daily_plan"
    assert step["href"] == "/daily-plan"
    assert step["action"] == "Open today's plan"


def test_due_new_cards_are_study_even_when_reviews_are_also_due():
    step = _facts(due_study=3, due_review=2)
    assert step["stage"] == "study"
    assert step["href"] == "/study"
    assert step["action"] == "Study 3 cards"
    assert "2 cards are due to review after that" in step["detail"]


def test_one_due_learning_card():
    step = _facts(due_study=1, due_review=0, quiz_ready=False)
    assert step["stage"] == "study"
    assert step["action"] == "Study 1 card"
    assert step["detail"] == "1 card is due to learn."


def test_only_spaced_repetition_is_review():
    step = _facts(due_study=0, due_review=4)
    assert step["stage"] == "review"
    assert step["href"] == "/study"
    assert step["action"] == "Review 4 cards"


def test_clear_queue_with_enough_words_is_quiz():
    step = _facts(due_study=0, due_review=0, quiz_ready=True)
    assert step["stage"] == "quiz"
    assert step["href"] == "/quiz"
    assert step["action"] == "Take a quiz"


def test_clear_queue_without_a_quiz_returns_to_the_plan():
    step = _facts(due_study=0, due_review=0, quiz_ready=False)
    assert step["stage"] == "daily_plan"
    assert step["action"] == "See today's plan"


def test_negative_counts_do_not_invent_a_later_stage():
    step = prep_orientation(
        sources=-1,
        words=-3,
        phrases=0,
        patterns=0,
        cards=-1,
        due_study=-2,
        due_review=-4,
        quiz_ready=True,
    )
    assert step["stage"] == "import"
