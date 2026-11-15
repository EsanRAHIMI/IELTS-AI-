"""One study session per user per day.

The ordered card list is fixed the first time the queue is opened that day.
Cards already reviewed are kept on the same document, so a refresh continues
with the cards that are still left.
"""
from __future__ import annotations

from datetime import timedelta

from pymongo.errors import DuplicateKeyError

import database as db
from utils.serialization import now


def today_key(user_id: str, day: str | None = None) -> str:
    stamp = day or now().date().isoformat()
    return f"{user_id}:{stamp}"


def session_without_card(card_ids: list | None, reviewed_ids: list | None, card_id: str) -> tuple[list[str], list[str]]:
    """Drop a reported card from today's list and remember it so it cannot return."""
    removed = str(card_id)
    kept: list[str] = []
    for item in card_ids or []:
        sid = str(item)
        if sid and sid != removed and sid not in kept:
            kept.append(sid)
    reviewed: list[str] = []
    for item in list(reviewed_ids or []) + [removed]:
        sid = str(item)
        if sid and sid not in reviewed:
            reviewed.append(sid)
    return kept, reviewed


def hidden_source(card: dict, hidden_refs: set[tuple[str, str]]) -> bool:
    return (card.get("type"), str(card.get("refId") or "")) in hidden_refs


def remaining_ids(card_ids: list | None, reviewed_ids: list | None) -> list[str]:
    reviewed = {str(item) for item in (reviewed_ids or [])}
    remaining: list[str] = []
    for card_id in card_ids or []:
        sid = str(card_id)
        if sid and sid not in reviewed and sid not in remaining:
            remaining.append(sid)
    return remaining


async def mark_reviewed(user_id: str, card_id: str) -> None:
    day = now().date().isoformat()
    await db.study_progress().update_one(
        {"_id": today_key(user_id, day)},
        {
            "$setOnInsert": {
                "userId": user_id,
                "day": day,
                "expiresAt": now() + timedelta(days=3),
            },
            "$addToSet": {"reviewedIds": str(card_id)},
        },
        upsert=True,
    )


async def ensure_session(user_id: str, card_ids: list[str]) -> dict:
    """Return today's session, creating it from ``card_ids`` only if it has no list yet."""
    day = now().date().isoformat()
    key = today_key(user_id, day)
    existing = await db.study_progress().find_one({"_id": key})
    if existing and existing.get("cardIds"):
        return existing
    if existing:
        await db.study_progress().update_one({"_id": key}, {"$set": {"cardIds": card_ids}})
        existing["cardIds"] = card_ids
        return existing
    doc = {
        "_id": key,
        "userId": user_id,
        "day": day,
        "cardIds": card_ids,
        "reviewedIds": [],
        "expiresAt": now() + timedelta(days=3),
    }
    try:
        await db.study_progress().insert_one(doc)
    except DuplicateKeyError:
        found = await db.study_progress().find_one({"_id": key})
        return found or doc
    return doc
