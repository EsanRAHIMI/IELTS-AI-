"""Dashboard stats and progress charts."""
from __future__ import annotations
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

import database as db
from auth.dependencies import current_user_id, get_current_user
from progress.home import library_progress, listed_sources
from progress.orientation import prep_orientation
from sources.freeze import active_item_query, frozen_source_ids, studyable_card_stats
from utils.serialization import now

QUIZ_READY_COUNT = 4

router = APIRouter(tags=["progress"])


async def _streak(uid: str) -> int:
    """Consecutive days (ending today or yesterday) with at least one review."""
    days = set()
    cur = db.reviews().find({"userId": uid}, {"reviewedAt": 1}).sort("reviewedAt", -1).limit(2000)
    async for r in cur:
        days.add(r["reviewedAt"].date())
    if not days:
        return 0
    today = now().date()
    streak = 0
    day = today
    if today not in days and (today - timedelta(days=1)) in days:
        day = today - timedelta(days=1)
    while day in days:
        streak += 1
        day = day - timedelta(days=1)
    return streak


@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    uid = user["id"]
    frozen = await frozen_source_ids(uid)
    base = {"userId": uid, "hidden": {"$ne": True}, **active_item_query(frozen)}
    total_sources = await db.sources().count_documents({"userId": uid, "frozen": {"$ne": True}})
    total_words = await db.vocab().count_documents(base)
    total_phrases = await db.phrases().count_documents(base)
    total_patterns = await db.patterns().count_documents(base)
    stats = await studyable_card_stats(uid)
    cards = library_progress(stats, stats["due"])
    titles = []
    async for source in db.sources().find(
        {"userId": uid, "frozen": {"$ne": True}},
        {"title": 1},
    ).sort("createdAt", -1):
        titles.append(source.get("title"))
    shown_sources, more_sources = listed_sources(titles)
    streak = await _streak(uid)
    settings = user.get("settings", {})
    return {
        "totalSources": total_sources,
        "totalWords": total_words,
        "totalPhrases": total_phrases,
        "totalPatterns": total_patterns,
        "dueToday": cards["due"],
        "mastered": cards["mastered"],
        "learning": cards["learning"],
        "cardsNew": cards["new"],
        "studied": cards["studied"],
        "library": total_words + total_phrases + total_patterns,
        "sourceNames": shown_sources,
        "moreSources": more_sources,
        "streak": streak,
        "focus": settings.get("focusModules", []),
        "targetBand": settings.get("targetBand"),
        "examDate": settings.get("examDate"),
    }


@router.get("/progress")
async def progress(uid: str = Depends(current_user_id), days: int = Query(30, ge=1, le=365)):
    start = now() - timedelta(days=days)
    # daily review counts & accuracy
    by_day: dict[str, dict] = {}
    cur = db.reviews().find({"userId": uid, "reviewedAt": {"$gte": start}})
    async for r in cur:
        d = r["reviewedAt"].date().isoformat()
        bucket = by_day.setdefault(d, {"date": d, "reviews": 0, "correct": 0})
        bucket["reviews"] += 1
        bucket["correct"] += 1 if r.get("correct") else 0
    timeline = sorted(by_day.values(), key=lambda x: x["date"])
    for b in timeline:
        b["accuracy"] = round(100 * b["correct"] / b["reviews"]) if b["reviews"] else 0

    total_reviews = sum(b["reviews"] for b in timeline)
    total_correct = sum(b["correct"] for b in timeline)
    accuracy = round(100 * total_correct / total_reviews) if total_reviews else 0

    # status distribution, excluding cards set aside with a frozen source
    card_stats = await studyable_card_stats(uid)
    status_dist = {st: card_stats[st] for st in ("new", "learning", "review", "mastered")}

    # source coverage
    coverage = []
    cur = db.sources().find(
        {"userId": uid, "frozen": {"$ne": True}},
        {"title": 1, "stats": 1},
    ).sort("createdAt", -1).limit(15)
    async for s in cur:
        stats = s.get("stats", {})
        coverage.append({
            "title": s.get("title", "Untitled"),
            "words": stats.get("wordsExtracted", 0),
            "phrases": stats.get("phrasesExtracted", 0),
        })

    return {
        "timeline": timeline,
        "totalReviews": total_reviews,
        "accuracy": accuracy,
        "statusDistribution": status_dist,
        "sourceCoverage": coverage,
    }


@router.get("/orientation")
async def orientation(uid: str = Depends(current_user_id)):
    """Current prep stage and the one next step, from stored counts."""
    frozen = await frozen_source_ids(uid)
    visible = {"userId": uid, "hidden": {"$ne": True}, **active_item_query(frozen)}
    sources = await db.sources().count_documents({"userId": uid, "frozen": {"$ne": True}})
    words = await db.vocab().count_documents(visible)
    phrases = await db.phrases().count_documents(visible)
    patterns = await db.patterns().count_documents(visible)
    stats = await studyable_card_stats(uid)
    cards = stats["new"] + stats["learning"] + stats["review"] + stats["mastered"]
    due_study = stats["due_study"]
    due_review = stats["due_review"]
    enriched = await db.vocab().count_documents({**visible, "simpleEnglishMeaning": {"$ne": ""}})
    return prep_orientation(
        sources=sources,
        words=words,
        phrases=phrases,
        patterns=patterns,
        cards=cards,
        due_study=due_study,
        due_review=due_review,
        quiz_ready=enriched >= QUIZ_READY_COUNT,
    )
