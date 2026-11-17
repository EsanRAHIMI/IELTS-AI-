"""Shape stored library and card counts for the signed-in home."""
from __future__ import annotations


def library_progress(status_counts: dict | None, due: int) -> dict:
    """Cards by the statuses the home shows.

    ``learning`` includes cards already in spaced review. ``due`` is every card
    whose review time has arrived, which can overlap the other counts.
    ``studied`` is cards that have left ``new``.
    """
    counts = status_counts or {}
    new = _count(counts.get("new"))
    learning = _count(counts.get("learning")) + _count(counts.get("review"))
    mastered = _count(counts.get("mastered"))
    return {
        "new": new,
        "learning": learning,
        "due": max(0, int(due or 0)),
        "mastered": mastered,
        "studied": learning + mastered,
    }


def listed_sources(titles: list | None, limit: int = 12) -> tuple[list[str], int]:
    """Imported source titles, newest first, and how many names did not fit.

    A missing title is Untitled. A blank title is skipped.
    """
    names: list[str] = []
    for title in titles or []:
        if title is None:
            names.append("Untitled")
            continue
        text = str(title).strip()
        if text:
            names.append(text)
    return names[:limit], max(0, len(names) - limit)


def _count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
