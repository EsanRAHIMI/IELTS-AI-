"""Helpers to convert Mongo documents to JSON-safe dicts."""
from typing import Any
from datetime import datetime, timezone
from bson import ObjectId


def now() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str) -> ObjectId:
    return ObjectId(value)


def is_oid(value: str) -> bool:
    return ObjectId.is_valid(value)


def serialize(doc: Any) -> Any:
    """Recursively make a Mongo document JSON serializable.

    - ObjectId -> str (renaming `_id` to `id`)
    - datetime -> ISO string
    """
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(d) for d in doc]
    if isinstance(doc, dict):
        out: dict[str, Any] = {}
        for k, v in doc.items():
            key = "id" if k == "_id" else k
            out[key] = serialize(v)
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
