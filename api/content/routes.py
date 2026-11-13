"""Vocabulary, phrases and sentence-pattern endpoints (the 'ranker' data).

Includes filtering, pagination, manual actions (hide / important / status),
AI re-generation, and detail views.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import database as db
from auth.dependencies import current_user_id
from config import settings
from http_util import clamp_page, search_regex
from quotas import consume_ai_call
from utils.serialization import now, oid, is_oid, serialize
from ai import service as ai

router = APIRouter(tags=["content"])


# ---- Vocabulary ------------------------------------------------------------
@router.get("/vocabulary")
async def list_vocab(
    uid: str = Depends(current_user_id),
    page: int = Query(1, ge=1, le=500),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
    section: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    pos: str | None = None,
    source: str | None = None,
    minPriority: int = 0,
    includeHidden: bool = False,
    sort: str = "priority",
):
    q: dict = {"userId": uid}
    if not includeHidden:
        q["hidden"] = {"$ne": True}
    word_search = search_regex(search)
    if word_search:
        q["word"] = word_search
    if section:
        q["ieltsUseCases"] = section
    difficulty_search = search_regex(difficulty)
    if difficulty_search:
        q["difficulty"] = difficulty_search
    if status:
        q["status"] = status
    if pos:
        q["partOfSpeech"] = pos
    if source:
        q["sourceIds"] = source
    if minPriority:
        q["priorityScore"] = {"$gte": minPriority}

    sort_field = {"priority": "priorityScore", "frequency": "frequency", "word": "word"}.get(sort, "priorityScore")
    direction = 1 if sort_field == "word" else -1
    page = clamp_page(page)
    skip = (page - 1) * limit
    cur = db.vocab().find(q).sort(sort_field, direction).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.vocab().count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/vocabulary/{item_id}")
async def vocab_detail(item_id: str, uid: str = Depends(current_user_id)):
    doc = await _get(db.vocab(), item_id, uid)
    # attach source snippets
    snippets = []
    for sid in (doc.get("sourceIds") or [])[:5]:
        if is_oid(sid):
            src = await db.sources().find_one(
                {"_id": oid(sid), "userId": uid}, {"title": 1, "type": 1},
            )
            if src:
                snippets.append({"id": sid, "title": src.get("title"), "type": src.get("type")})
    doc["sources"] = snippets
    return serialize(doc)


@router.post("/vocabulary/{item_id}/regenerate")
async def regenerate_vocab(item_id: str, uid: str = Depends(current_user_id)):
    doc = await _get(db.vocab(), item_id, uid)
    provider_name = await _reserve_ai(uid)
    data = await ai.explain_word(
        doc["word"], doc.get("partOfSpeech", ""), (doc.get("examples") or [""])[0], provider_name,
    )
    update = {"aiEnriched": True, "updatedAt": now()}
    for k in ("persianMeaning", "simpleEnglishMeaning", "difficulty", "ieltsUseCases",
              "collocations", "examples", "commonMistakes", "notes"):
        if data.get(k):
            update[k] = data[k]
    await db.vocab().update_one({"_id": oid(item_id)}, {"$set": update})
    return serialize(await db.vocab().find_one({"_id": oid(item_id)}))


# ---- Phrases ---------------------------------------------------------------
@router.get("/phrases")
async def list_phrases(
    uid: str = Depends(current_user_id),
    page: int = Query(1, ge=1, le=500),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
    section: str | None = None,
    status: str | None = None,
    includeHidden: bool = False,
):
    q: dict = {"userId": uid}
    if not includeHidden:
        q["hidden"] = {"$ne": True}
    phrase_search = search_regex(search)
    if phrase_search:
        q["phrase"] = phrase_search
    if section:
        q["section"] = section
    if status:
        q["status"] = status
    page = clamp_page(page)
    skip = (page - 1) * limit
    cur = db.phrases().find(q).sort("priorityScore", -1).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.phrases().count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/phrases/{item_id}/regenerate")
async def regenerate_phrase(item_id: str, uid: str = Depends(current_user_id)):
    doc = await _get(db.phrases(), item_id, uid)
    provider_name = await _reserve_ai(uid)
    data = await ai.explain_phrase(doc["phrase"], (doc.get("examples") or [""])[0], provider_name)
    update = {"aiEnriched": True, "updatedAt": now()}
    for k in ("persianMeaning", "simpleEnglishMeaning", "examples", "notes"):
        if data.get(k):
            update[k] = data[k]
    await db.phrases().update_one({"_id": oid(item_id)}, {"$set": update})
    return serialize(await db.phrases().find_one({"_id": oid(item_id)}))


# ---- Sentence patterns -----------------------------------------------------
@router.get("/patterns")
async def list_patterns(
    uid: str = Depends(current_user_id),
    page: int = Query(1, ge=1, le=500),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
    category: str | None = None,
    includeHidden: bool = False,
):
    q: dict = {"userId": uid}
    if not includeHidden:
        q["hidden"] = {"$ne": True}
    sentence_search = search_regex(search)
    if sentence_search:
        q["sentence"] = sentence_search
    if category:
        q["category"] = category
    page = clamp_page(page)
    skip = (page - 1) * limit
    cur = db.patterns().find(q).sort("priorityScore", -1).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.patterns().count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


# ---- Shared manual actions (work on any of the 3 collections) --------------
COLLECTIONS = {"vocabulary": db.vocab, "phrases": db.phrases, "patterns": db.patterns}


class StatusUpdate(BaseModel):
    status: Literal["new", "learning", "review", "mastered"] = Field()


def _col(kind: str):
    if kind not in COLLECTIONS:
        raise HTTPException(404, "Unknown collection")
    return COLLECTIONS[kind]()


async def _get(collection, item_id: str, uid: str) -> dict:
    if not is_oid(item_id):
        raise HTTPException(404, "Not found")
    doc = await collection.find_one({"_id": oid(item_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.patch("/{kind}/{item_id}/status")
async def set_status(kind: str, item_id: str, body: StatusUpdate, uid: str = Depends(current_user_id)):
    col = _col(kind)
    await _get(col, item_id, uid)
    await col.update_one({"_id": oid(item_id)}, {"$set": {"status": body.status, "updatedAt": now()}})
    return {"ok": True}


@router.patch("/{kind}/{item_id}/important")
async def toggle_important(kind: str, item_id: str, uid: str = Depends(current_user_id)):
    col = _col(kind)
    doc = await _get(col, item_id, uid)
    new_val = not doc.get("important", False)
    await col.update_one({"_id": oid(item_id)}, {"$set": {"important": new_val, "updatedAt": now()}})
    return {"important": new_val}


@router.patch("/{kind}/{item_id}/hide")
async def toggle_hide(kind: str, item_id: str, uid: str = Depends(current_user_id)):
    col = _col(kind)
    doc = await _get(col, item_id, uid)
    new_val = not doc.get("hidden", False)
    await col.update_one({"_id": oid(item_id)}, {"$set": {"hidden": new_val, "updatedAt": now()}})
    return {"hidden": new_val}


@router.delete("/{kind}/{item_id}")
async def delete_item(kind: str, item_id: str, uid: str = Depends(current_user_id)):
    col = _col(kind)
    await _get(col, item_id, uid)
    card_type = {"vocabulary": "word", "phrases": "phrase", "patterns": "sentence_pattern"}[kind]
    card_ids = [
        str(card["_id"])
        async for card in db.cards().find({"userId": uid, "type": card_type, "refId": item_id}, {"_id": 1})
    ]
    await col.delete_one({"_id": oid(item_id), "userId": uid})
    if card_ids:
        await db.cards().delete_many({"userId": uid, "_id": {"$in": [oid(cid) for cid in card_ids]}})
        await db.reviews().delete_many({"userId": uid, "cardId": {"$in": card_ids}})
    return {"ok": True}


async def _provider_name(uid: str) -> str:
    user = await db.users().find_one({"_id": oid(uid)}, {"settings.aiProvider": 1})
    choice = ((user or {}).get("settings") or {}).get("aiProvider")
    return choice or settings.ai_provider


async def _reserve_ai(uid: str) -> str:
    provider_name = await _provider_name(uid)
    if ai.get_provider(provider_name) is None:
        raise HTTPException(409, "The selected AI provider is not configured")
    if not await consume_ai_call(uid, settings.max_ai_calls_per_day):
        raise HTTPException(429, "Daily AI quota reached")
    return provider_name
