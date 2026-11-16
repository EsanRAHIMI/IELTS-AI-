"""One unfinished quiz per user.

The question list, the open question, and the answers already chosen stay
until the learner finishes or starts another quiz.
"""
from __future__ import annotations

MAX_QUESTIONS = 20
MODES = {"meaning", "fill_blank", "collocation"}


def clean_questions(raw: list | None) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[str] = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or "").strip()
        if not qid or qid in seen:
            continue
        options: list[str] = []
        for option in item.get("options") or []:
            text = str(option).strip()
            if text and text not in options:
                options.append(text)
        correct = str(item.get("correct") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not prompt or len(options) < 2 or correct not in options:
            continue
        seen.add(qid)
        cleaned.append({
            "id": qid,
            "prompt": prompt,
            "options": options[:8],
            "correct": correct,
            "word": str(item.get("word") or "").strip(),
        })
        if len(cleaned) >= MAX_QUESTIONS:
            break
    return cleaned


def quiz_progress(questions: list[dict], index: int | None, answers: list | None) -> dict:
    allowed = {q["id"]: q for q in questions}
    choices: dict[str, str] = {}
    stored: list[dict] = []
    for answer in answers or []:
        if not isinstance(answer, dict):
            continue
        qid = str(answer.get("questionId") or "").strip()
        choice = str(answer.get("choice") or "")
        question = allowed.get(qid)
        if not question or qid in choices or choice not in question["options"]:
            continue
        choices[qid] = choice
        stored.append({"questionId": qid, "choice": choice})
    count = len(questions)
    try:
        cursor = int(index or 0)
    except (TypeError, ValueError):
        cursor = 0
    cursor = min(max(cursor, 0), count)
    score = sum(1 for question in questions if choices.get(question["id"]) == question["correct"])
    return {"index": cursor, "answers": stored, "score": score}


def resumable(doc: dict | None) -> dict | None:
    """The saved quiz, or nothing when it is missing or already finished."""
    if not doc:
        return None
    questions = clean_questions(doc.get("questions"))
    if not questions:
        return None
    mode = doc.get("mode") if doc.get("mode") in MODES else "meaning"
    progress = quiz_progress(questions, doc.get("index") or 0, doc.get("answers"))
    if progress["index"] >= len(questions):
        return None
    return {"mode": mode, "questions": questions, **progress}
