"""Small request helpers: flags, paging, search, filenames, client IP."""
from __future__ import annotations

import re

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None or str(value).strip() == "":
        return default
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError("invalid boolean")


def first_query(params, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in params:
            return params.get(name)
    return None


def read_bool(params, names: tuple[str, ...], default: bool) -> bool:
    return parse_bool(first_query(params, names), default)


def clamp_page(page: int, *, maximum: int = 500) -> int:
    if page < 1:
        return 1
    return min(page, maximum)


def clamp_limit(limit: int, *, default: int, maximum: int) -> int:
    """``limit=0`` is not 'everything'. PyMongo treats 0 as unlimited."""
    if limit < 1:
        return min(default, maximum)
    return min(limit, maximum)


def search_regex(value: str | None, *, max_len: int = 80) -> dict | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return {"$regex": re.escape(text[:max_len]), "$options": "i"}


def content_disposition(filename: str | None) -> str:
    raw = filename or "download"
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "._- ")
    cleaned = " ".join(cleaned.split())[:120] or "download"
    return f'attachment; filename="{cleaned}"'


def client_ip(request, *, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1][:80]
    client = getattr(request, "client", None)
    if client and getattr(client, "host", None):
        return str(client.host)[:80]
    return "unknown"
