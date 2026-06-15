"""Vocabulary, phrases and sentence-pattern endpoints (the 'ranker' data).

Includes filtering, pagination, manual actions (hide / important / status),
AI re-generation, and detail views.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import database as db
from auth.dependencies import current_user_id
from utils.serialization import now, oid, is_oid, serialize
from ai import service as ai

router = APIRouter(tags=["content"])


# ---- Vocabulary ------------------------------------------------------------
@router.get("/vocabulary")
async def list_vocab(
    uid: str = Depends(current_user_id),
    page: int = 1,
    limit: int = Query(50, le=200),
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
    if search:
        q["word"] = {"$regex": search, "$options": "i"}
    if section:
        q["ieltsUseCases"] = section
    if difficulty:
        q["difficulty"] = {"$regex": difficulty, "$options": "i"}
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
    skip = (max(1, page) - 1) * limit
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
            src = await db.sources().find_one({"_id": oid(sid)}, {"title": 1, "type": 1})
            if src:
                snippets.append({"id": sid, "title": src.get("title"), "type": src.get("type")})
    doc["sources"] = snippets
    return serialize(doc)


@router.post("/vocabulary/{item_id}/regenerate")
async def regenerate_vocab(item_id: str, uid: str = Depends(current_user_id)):
    doc = await _get(db.vocab(), item_id, uid)
    data = await ai.explain_word(doc["word"], doc.get("partOfSpeech", ""), (doc.get("examples") or [""])[0])
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
    page: int = 1,
    limit: int = Query(50, le=200),
    search: str | None = None,
    section: str | None = None,
    status: str | None = None,
    includeHidden: bool = False,
):
    q: dict = {"userId": uid}
    if not includeHidden:
        q["hidden"] = {"$ne": True}
    if search:
        q["phrase"] = {"$regex": search, "$options": "i"}
    if section:
        q["section"] = section
    if status:
        q["status"] = status
    skip = (max(1, page) - 1) * limit
    cur = db.phrases().find(q).sort("priorityScore", -1).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.phrases().count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post("/phrases/{item_id}/regenerate")
async def regenerate_phrase(item_id: str, uid: str = Depends(current_user_id)):
    doc = await _get(db.phrases(), item_id, uid)
    data = await ai.explain_phrase(doc["phrase"], (doc.get("examples") or [""])[0])
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
    page: int = 1,
    limit: int = Query(50, le=200),
    search: str | None = None,
    category: str | None = None,
    includeHidden: bool = False,
):
    q: dict = {"userId": uid}
    if not includeHidden:
        q["hidden"] = {"$ne": True}
    if search:
        q["sentence"] = {"$regex": search, "$options": "i"}
    if category:
        q["category"] = category
    skip = (max(1, page) - 1) * limit
    cur = db.patterns().find(q).sort("priorityScore", -1).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.patterns().count_documents(q)
    return {"items": items, "total": total, "page": page, "limit": limit}


# ---- Shared manual actions (work on any of the 3 collections) --------------
COLLECTIONS = {"vocabulary": db.vocab, "phrases": db.phrases, "patterns": db.patterns}


class StatusUpdate(BaseModel):
    status: str


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
    await col.delete_one({"_id": oid(item_id)})
    return {"ok": True}
