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


def cards():
    return col("learning_cards")


def reviews():
    return col("review_history")


def plans():
    return col("daily_plans")


def jobs():
    return col("jobs")


async def init_indexes() -> None:
    """Create indexes used across the app. Safe to call repeatedly."""
    try:
        await users().create_index("email", unique=True)
        for c in (vocab(), phrases(), patterns()):
            await c.create_index([("userId", 1), ("priorityScore", -1)])
            await c.create_index([("userId", 1), ("status", 1)])
        await vocab().create_index([("userId", 1), ("lemma", 1)])
        await cards().create_index([("userId", 1), ("nextReviewAt", 1)])
        await cards().create_index([("userId", 1), ("status", 1)])
        await sources().create_index([("userId", 1), ("createdAt", -1)])
        await source_chunks().create_index([("sourceId", 1), ("index", 1)])
        await source_chunks().create_index([("userId", 1)])
        await jobs().create_index([("status", 1), ("createdAt", 1)])
        await reviews().create_index([("userId", 1), ("reviewedAt", -1)])
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
