"""Simplified SM-2 spaced repetition.

Grades map to SM-2 quality:
    again -> 1, hard -> 3, good -> 4, easy -> 5
"""
from __future__ import annotations
from datetime import timedelta

from utils.serialization import now

GRADE_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}


def review(card: dict, grade: str) -> dict:
    quality = GRADE_QUALITY.get(grade, 4)
    ease = card.get("easeFactor", 2.5)
    reps = card.get("repetitions", 0)
    interval = card.get("interval", 0)

    if quality < 3:  # failed -> reset
        reps = 0
        interval = 1
        status = "learning"
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = round(interval * ease)
        status = "review" if reps < 4 else "mastered"

    # update ease factor
    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, ease)

    next_review = now() + timedelta(days=interval)
    return {
        "easeFactor": round(ease, 3),
        "repetitions": reps,
        "interval": interval,
        "status": status,
        "nextReviewAt": next_review,
        "lastReviewedAt": now(),
    }
