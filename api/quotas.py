"""Per-user quotas and a windowed rate limiter backed by MongoDB.

Counters live in Mongo so more than one API process shares them.
The decision helpers are pure so tests do not need a database.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import database as db
from utils.serialization import now

logger = logging.getLogger("ielts.quotas")


def quota_block(
    *,
    sources: int,
    max_sources: int,
    used_bytes: int,
    extra_bytes: int,
    max_bytes: int,
    active_jobs: int,
    max_jobs: int,
) -> str | None:
    if sources >= max_sources:
        return "Source limit reached. Delete an old source and try again."
    if used_bytes + max(0, extra_bytes) > max_bytes:
        return "Storage quota reached."
    if active_jobs >= max_jobs:
        return "Too many files are already processing."
    return None


def take_ai_slot(used: int, cap: int) -> bool:
    return int(used) < int(cap)


class MemoryWindowLimiter:
    """Single-process limiter used by tests."""

    def __init__(self):
        self.counts: dict[tuple[str, int], int] = {}

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = int(time.time()) // max(1, window_seconds)
        slot = (key, bucket)
        self.counts[slot] = self.counts.get(slot, 0) + 1
        return self.counts[slot] <= limit


class MongoWindowLimiter:
    def __init__(self, collection):
        self.collection = collection

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        window = max(1, int(window_seconds))
        bucket = int(time.time()) // window
        doc_id = f"{key}:{bucket}"
        expires = now() + timedelta(seconds=window * 2)
        try:
            doc = await self.collection.find_one_and_update(
                {"_id": doc_id},
                {"$inc": {"n": 1}, "$setOnInsert": {"expiresAt": expires}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except Exception:
            logger.exception("Rate limit store failed for %s", key)
            return True
        return int(doc.get("n") or 0) <= int(limit)


def rate_limiter() -> MongoWindowLimiter:
    return MongoWindowLimiter(db.col("rate_buckets"))


async def allow(key: str, limit: int, window_seconds: int = 3600) -> bool:
    return await rate_limiter().allow(key, limit, window_seconds)


async def consume_ai_call(user_id: str, cap: int) -> bool:
    """Reserve one AI call for today. False when the user is already at the cap."""
    day = now().date().isoformat()
    doc_id = f"{user_id}:{day}"
    collection = db.col("usage_daily")
    expires = now() + timedelta(days=3)
    try:
        doc = await collection.find_one_and_update(
            {"_id": doc_id, "aiCalls": {"$lt": int(cap)}},
            {"$inc": {"aiCalls": 1}, "$set": {"expiresAt": expires}},
            return_document=ReturnDocument.AFTER,
        )
    except Exception:
        logger.exception("AI quota update failed")
        return False
    if doc:
        return True
    try:
        await collection.insert_one({"_id": doc_id, "aiCalls": 1, "expiresAt": expires})
        return True
    except DuplicateKeyError:
        return False
