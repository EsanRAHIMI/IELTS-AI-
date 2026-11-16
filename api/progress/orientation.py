"""Where the learner is, from counts already stored for that user.

One stage and one next step. This is not a checklist of every stage.
"""
from __future__ import annotations


def _cards(count: int) -> str:
    return "1 card" if count == 1 else f"{count} cards"


def _step(
    stage: str,
    label: str,
    action: str,
    detail: str,
    href: str,
) -> dict:
    return {
        "stage": stage,
        "stageLabel": label,
        "action": action,
        "detail": detail,
        "href": href,
    }


def prep_orientation(
    *,
    sources: int,
    words: int,
    phrases: int,
    patterns: int,
    cards: int,
    due_study: int,
    due_review: int,
    quiz_ready: bool,
) -> dict:
    """Pick the current prep stage from stored totals.

    ``due_study`` is due cards still new or learning.
    ``due_review`` is due cards already in review or mastered.
    ``quiz_ready`` is true when enough enriched vocabulary exists for a quiz.
    """
    sources = max(0, sources)
    items = max(0, words) + max(0, phrases) + max(0, patterns)
    cards = max(0, cards)
    due_study = max(0, due_study)
    due_review = max(0, due_review)

    if sources == 0 and items == 0:
        return _step(
            "import",
            "Import",
            "Import a source",
            "Nothing is in your library yet. Add a PDF, notes, or a link.",
            "/import",
        )
    if items == 0:
        return _step(
            "import",
            "Import",
            "Check Import Center",
            "A source is saved, but no words or phrases are ready yet.",
            "/import",
        )
    if cards == 0:
        return _step(
            "daily_plan",
            "Daily plan",
            "Open today's plan",
            "You have material. Choose what to study today.",
            "/daily-plan",
        )
    if due_study > 0:
        detail = f"{_cards(due_study)} {'is' if due_study == 1 else 'are'} due to learn."
        if due_review > 0:
            detail += f" {_cards(due_review)} {'is' if due_review == 1 else 'are'} due to review after that."
        return _step("study", "Study", f"Study {_cards(due_study)}", detail, "/study")
    if due_review > 0:
        return _step(
            "review",
            "Review",
            f"Review {_cards(due_review)}",
            f"{_cards(due_review)} {'is' if due_review == 1 else 'are'} due for spaced repetition.",
            "/study",
        )
    if quiz_ready:
        return _step(
            "quiz",
            "Quiz",
            "Take a quiz",
            "Nothing is due. A quiz checks the words you already have.",
            "/quiz",
        )
    return _step(
        "daily_plan",
        "Daily plan",
        "See today's plan",
        "Nothing is due right now. The plan shows what to add next.",
        "/daily-plan",
    )
