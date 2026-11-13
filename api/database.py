"""MongoDB connection and collection helpers (async, via Motor)."""
import logging

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings

logger = logging.getLogger("ielts.db")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        kwargs: dict = {"serverSelectionTimeoutMS": 8000}
        if settings.mongodb_uri.startswith("mongodb+srv"):
            kwargs["tlsCAFile"] = certifi.where()
        _client = AsyncIOMotorClient(settings.mongodb_uri, **kwargs)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db]
    return _db


# Collection accessors -------------------------------------------------------
def col(name: str):
    return get_db()[name]


def users():
    return col("users")


def sources():
    return col("sources")


def vocab():
    return col("vocabulary")


def phrases():
    return col("phrases")


def patterns():
    return col("sentence_patterns")


def source_chunks():
    return col("source_chunks")


def source_pages():
    return col("source_pages")


def cards():
    return col("learning_cards")


def reviews():
    return col("review_history")


def plans():
    return col("daily_plans")


def jobs():
    return col("jobs")


async def _ensure_index(collection, keys, **kwargs) -> None:
    """Create an index. If a unique index cannot be built, keep a non-unique one."""
    try:
        await collection.create_index(keys, **kwargs)
    except Exception as exc:
        if not kwargs.get("unique"):
            logger.warning("Index %s failed: %s", keys, exc)
            return
        logger.warning("Unique index %s failed (%s); creating a non-unique index", keys, exc)
        plain = {k: v for k, v in kwargs.items() if k != "unique"}
        plain["name"] = str(plain.get("name") or "idx") + "_plain"
        try:
            await collection.create_index(keys, **plain)
        except Exception as inner:
            logger.warning("Fallback index %s failed: %s", keys, inner)


async def init_indexes() -> None:
    """Create indexes used across the app. Safe to call repeatedly."""
    try:
        await _ensure_index(users(), "email", unique=True, name="email_unique")
        for c in (vocab(), phrases(), patterns()):
            await _ensure_index(c, [("userId", 1), ("priorityScore", -1)])
            await _ensure_index(c, [("userId", 1), ("status", 1)])
        await _ensure_index(vocab(), [("userId", 1), ("lemma", 1)], unique=True, name="user_lemma_unique")
        await _ensure_index(phrases(), [("userId", 1), ("phrase", 1)], unique=True, name="user_phrase_unique")
        await _ensure_index(patterns(), [("userId", 1), ("sentence", 1)], unique=True, name="user_sentence_unique")
        await _ensure_index(cards(), [("userId", 1), ("nextReviewAt", 1)])
        await _ensure_index(cards(), [("userId", 1), ("status", 1)])
        await _ensure_index(
            cards(), [("userId", 1), ("type", 1), ("refId", 1)], unique=True, name="user_card_ref_unique",
        )
        await _ensure_index(sources(), [("userId", 1), ("createdAt", -1)])
        await _ensure_index(source_chunks(), [("sourceId", 1), ("index", 1)])
        await _ensure_index(source_chunks(), [("userId", 1)])
        await _ensure_index(source_pages(), [("sourceId", 1), ("pageNumber", 1)])
        await _ensure_index(source_pages(), [("userId", 1)])
        await _ensure_index(jobs(), [("status", 1), ("createdAt", 1)])
        await _ensure_index(jobs(), [("userId", 1), ("createdAt", -1)])
        await _ensure_index(jobs(), [("userId", 1), ("status", 1)])
        await _ensure_index(reviews(), [("userId", 1), ("reviewedAt", -1)])
        await _ensure_index(col("rate_buckets"), "expiresAt", expireAfterSeconds=0, name="rate_ttl")
        await _ensure_index(col("usage_daily"), "expiresAt", expireAfterSeconds=0, name="usage_ttl")
        logger.info("Mongo indexes ensured")
    except Exception as exc:  # pragma: no cover - startup resilience
        logger.warning("Could not ensure indexes: %s", exc)


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception as exc:
        logger.error("Mongo ping failed: %s", exc)
        return False
