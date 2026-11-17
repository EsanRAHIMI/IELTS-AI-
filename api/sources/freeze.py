"""A frozen source stays stored, but its exclusive content is set aside.

An item linked to at least one unfrozen source stays available. An item with
no source stays available. An item whose every source is frozen does not.
"""
from __future__ import annotations

import database as db
from utils.serialization import now


def item_is_frozen(source_ids, frozen_ids: set[str]) -> bool:
    if not frozen_ids or not isinstance(source_ids, list):
        return False
    ids = [str(source_id) for source_id in source_ids if source_id]
    if not ids:
        return False
    return all(source_id in frozen_ids for source_id in ids)


def active_item_query(frozen_ids: set[str]) -> dict:
    """Mongo clause for items the learner can still study."""
    if not frozen_ids:
        return {}
    ids = list(frozen_ids)
    return {
        "$nor": [
            {
                "sourceIds.0": {"$exists": True},
                "sourceIds": {"$not": {"$elemMatch": {"$nin": ids}}},
            }
        ]
    }


def index_in_full(full: list, kept: list, filtered_index) -> int:
    """Map a place in the visible quiz back onto the stored question list."""
    if not kept:
        return 0
    try:
        cursor = int(filtered_index or 0)
    except (TypeError, ValueError):
        cursor = 0
    if cursor >= len(kept):
        return len(full or [])
    cursor = max(cursor, 0)
    target = str((kept[cursor] or {}).get("id") or "")
    for position, question in enumerate(full or []):
        if str((question or {}).get("id") or "") == target:
            return position
    return 0


def without_frozen_questions(questions: list, index, blocked_ids: set[str]) -> tuple[list, int]:
    """Drop quiz questions from frozen sources and stay on the same remaining one."""
    try:
        cursor = int(index or 0)
    except (TypeError, ValueError):
        cursor = 0
    kept: list = []
    removed_before = 0
    for position, question in enumerate(questions or []):
        qid = str((question or {}).get("id") or "")
        if qid and qid in blocked_ids:
            if position < cursor:
                removed_before += 1
            continue
        kept.append(question)
    return kept, max(0, cursor - removed_before)


async def frozen_source_ids(uid: str) -> set[str]:
    found: set[str] = set()
    cursor = db.sources().find({"userId": uid, "frozen": True}, {"_id": 1})
    async for doc in cursor:
        found.add(str(doc["_id"]))
    return found


async def frozen_ref_pairs(uid: str) -> set[tuple[str, str]]:
    """Cards to hide: ``(card type, item id)`` for items only on frozen sources."""
    frozen = await frozen_source_ids(uid)
    if not frozen:
        return set()
    pairs: set[tuple[str, str]] = set()
    collections = (
        ("word", db.vocab()),
        ("phrase", db.phrases()),
        ("sentence_pattern", db.patterns()),
    )
    for card_type, col in collections:
        cursor = col.find({"userId": uid, "sourceIds.0": {"$exists": True}}, {"sourceIds": 1})
        async for doc in cursor:
            if item_is_frozen(doc.get("sourceIds"), frozen):
                pairs.add((card_type, str(doc["_id"])))
    return pairs


async def studyable_card_stats(uid: str) -> dict:
    """Status and due counts for cards the learner can still open."""
    blocked = await frozen_ref_pairs(uid)
    counts = {"new": 0, "learning": 0, "review": 0, "mastered": 0, "due": 0, "due_study": 0, "due_review": 0}
    async for card in db.cards().find({"userId": uid}, {"status": 1, "type": 1, "refId": 1}):
        if (card.get("type"), str(card.get("refId") or "")) in blocked:
            continue
        status = str(card.get("status") or "new")
        if status in ("new", "learning", "review", "mastered"):
            counts[status] += 1
    moment = now()
    async for card in db.cards().find(
        {"userId": uid, "nextReviewAt": {"$lte": moment}},
        {"status": 1, "type": 1, "refId": 1},
    ):
        if (card.get("type"), str(card.get("refId") or "")) in blocked:
            continue
        counts["due"] += 1
        status = str(card.get("status") or "new")
        if status in ("new", "learning"):
            counts["due_study"] += 1
        elif status in ("review", "mastered"):
            counts["due_review"] += 1
    return counts
