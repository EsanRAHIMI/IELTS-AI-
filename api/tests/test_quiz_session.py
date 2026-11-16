"""An unfinished quiz is restored; a finished one is not."""
from study.quiz_session import clean_questions, quiz_progress, resumable


def _questions():
    return [
        {
            "id": "q1",
            "prompt": "What does 'english' mean?",
            "options": ["A long definition.", "The language spoken in England."],
            "correct": "The language spoken in England.",
            "word": "english",
        },
        {
            "id": "q2",
            "prompt": "What does 'research' mean?",
            "options": ["Finding out new information.", "A short visit."],
            "correct": "Finding out new information.",
            "word": "research",
        },
    ]


def test_resume_keeps_the_open_question_and_the_score():
    saved = resumable({
        "mode": "meaning",
        "questions": _questions(),
        "index": 1,
        "answers": [{"questionId": "q1", "choice": "The language spoken in England."}],
    })
    assert saved["index"] == 1
    assert saved["score"] == 1
    assert saved["questions"][1]["word"] == "research"
    assert saved["answers"][0]["choice"].startswith("The language")


def test_a_choice_on_the_open_question_is_kept():
    progress = quiz_progress(_questions(), 1, [
        {"questionId": "q1", "choice": "The language spoken in England."},
        {"questionId": "q2", "choice": "A short visit."},
    ])
    assert progress["index"] == 1
    assert progress["score"] == 1
    assert progress["answers"][1]["choice"] == "A short visit."


def test_finishing_is_not_resumed():
    assert resumable({
        "mode": "fill_blank",
        "questions": _questions(),
        "index": 2,
        "answers": [],
    }) is None


def test_a_new_list_drops_broken_questions():
    cleaned = clean_questions([
        {"id": "ok", "prompt": "Prompt", "options": ["yes", "no"], "correct": "yes", "word": "ok"},
        {"id": "bad", "prompt": "", "options": ["yes"], "correct": "yes"},
        {"id": "ok", "prompt": "Duplicate", "options": ["yes", "no"], "correct": "yes"},
    ])
    assert [item["id"] for item in cleaned] == ["ok"]


def test_unknown_mode_falls_back_without_losing_the_question():
    saved = resumable({"mode": "other", "questions": _questions(), "index": 0, "answers": []})
    assert saved["mode"] == "meaning"
    assert saved["index"] == 0
