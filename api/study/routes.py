"""Study system: flashcards, review queue, daily plan, quiz."""
from __future__ import annotations
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import database as db
from auth.dependencies import current_user_id, get_current_user
from http_util import clamp_limit
from utils.serialization import now, oid, is_oid, serialize
from study import sm2
from study.plan import focus_query, focus_skill_tokens, plan_sizes

router = APIRouter(prefix="/study", tags=["study"])


# ---- Card creation ---------------------------------------------------------
class AddCard(BaseModel):
    type: str  # word | phrase | sentence_pattern
    refId: str


def _build_card(uid: str, item_type: str, item: dict) -> dict:
    if item_type == "word":
        front = item["word"]
        back = {
            "persianMeaning": item.get("persianMeaning", ""),
            "simpleEnglishMeaning": item.get("simpleEnglishMeaning", ""),
            "examples": item.get("examples", []),
            "collocations": item.get("collocations", []),
            "notes": item.get("notes", ""),
        }
    elif item_type == "phrase":
        front = item["phrase"]
        back = {
            "persianMeaning": item.get("persianMeaning", ""),
            "simpleEnglishMeaning": item.get("simpleEnglishMeaning", ""),
            "examples": item.get("examples", []),
            "collocations": [],
            "notes": item.get("notes", ""),
        }
    else:  # sentence_pattern
        front = item.get("template") or item.get("sentence", "")
        back = {
            "persianMeaning": "",
            "simpleEnglishMeaning": item.get("category", ""),
            "examples": [item.get("sentence", "")],
            "collocations": [],
            "notes": item.get("notes", ""),
        }
    return {
        "userId": uid, "type": item_type, "refId": str(item["_id"]), "front": front, "back": back,
        "status": "new", "easeFactor": 2.5, "interval": 0, "repetitions": 0,
        "nextReviewAt": now(), "lastReviewedAt": None, "createdAt": now(), "updatedAt": now(),
    }


_TYPE_COL = {"word": db.vocab, "phrase": db.phrases, "sentence_pattern": db.patterns}


@router.post("/cards", status_code=201)
async def add_card(body: AddCard, uid: str = Depends(current_user_id)):
    if body.type not in _TYPE_COL:
        raise HTTPException(400, "Invalid card type")
    if not is_oid(body.refId):
        raise HTTPException(400, "Invalid refId")
    col = _TYPE_COL[body.type]()
    item = await col.find_one({"_id": oid(body.refId), "userId": uid})
    if not item:
        raise HTTPException(404, "Item not found")
    existing = await db.cards().find_one({"userId": uid, "type": body.type, "refId": body.refId})
    if existing:
        return {"id": str(existing["_id"]), "existing": True}
    card = _build_card(uid, body.type, item)
    res = await db.cards().insert_one(card)
    await col.update_one({"_id": item["_id"]}, {"$set": {"status": "learning", "updatedAt": now()}})
    return {"id": str(res.inserted_id), "existing": False}


@router.get("/cards")
async def list_cards(
    uid: str = Depends(current_user_id),
    status: str | None = None,
    limit: int = Query(100, ge=1, le=100),
):
    q: dict = {"userId": uid}
    if status:
        q["status"] = status
    cur = db.cards().find(q).sort("nextReviewAt", 1).limit(clamp_limit(limit, default=100, maximum=100))
    return {"items": [serialize(d) async for d in cur]}


@router.get("/queue")
async def review_queue(uid: str = Depends(current_user_id), limit: int = Query(40, ge=1, le=100)):
    """Cards that are due now (nextReviewAt <= now), new first."""
    q = {"userId": uid, "nextReviewAt": {"$lte": now()}}
    cur = db.cards().find(q).sort([("status", 1), ("nextReviewAt", 1)]).limit(limit)
    items = [serialize(d) async for d in cur]
    total_due = await db.cards().count_documents(q)
    return {"items": items, "totalDue": total_due}


class ReviewBody(BaseModel):
    grade: str = Field(pattern="^(again|hard|good|easy)$")


@router.post("/cards/{card_id}/review")
async def review_card(card_id: str, body: ReviewBody, uid: str = Depends(current_user_id)):
    if not is_oid(card_id):
        raise HTTPException(404, "Not found")
    card = await db.cards().find_one({"_id": oid(card_id), "userId": uid})
    if not card:
        raise HTTPException(404, "Not found")
    try:
        update = sm2.review(card, body.grade)
    except ValueError:
        raise HTTPException(400, "Invalid grade") from None
    await db.cards().update_one({"_id": oid(card_id)}, {"$set": {**update, "updatedAt": now()}})
    await db.reviews().insert_one({
        "userId": uid, "cardId": card_id, "type": card.get("type"), "grade": body.grade,
        "correct": body.grade in ("good", "easy"), "reviewedAt": now(),
    })
    if update["status"] == "mastered":
        col = _TYPE_COL.get(card["type"])
        if col and is_oid(card.get("refId", "")):
            await col().update_one({"_id": oid(card["refId"])}, {"$set": {"status": "mastered"}})
    return {"ok": True, **{k: serialize(v) for k, v in update.items()}}


# ---- Daily plan ------------------------------------------------------------
@router.get("/daily-plan")
async def daily_plan(user: dict = Depends(get_current_user)):
    uid = user["id"]
    prefs = user.get("settings") or {}
    sizes = plan_sizes(int(prefs.get("dailyTarget") or 30))
    focus = focus_query(focus_skill_tokens(prefs.get("focusModules") or []))

    async def top(col, n):
        q = {"userId": uid, "hidden": {"$ne": True}, "status": {"$in": ["new", "learning"]}}
        if focus:
            q.update(focus)
        cur = col.find(q).sort("priorityScore", -1).limit(n)
        return [serialize(d) async for d in cur]

    words = await top(db.vocab(), sizes["words"])
    phrases = await top(db.phrases(), sizes["phrases"])
    patterns = await top(db.patterns(), sizes["patterns"])
    due = await db.cards().count_documents({"userId": uid, "nextReviewAt": {"$lte": now()}})
    est_minutes = round(len(words) * 0.5 + len(phrases) * 0.6 + len(patterns) * 0.8 + due * 0.4)
    return {
        "date": now().date().isoformat(),
        "words": words,
        "phrases": phrases,
        "patterns": patterns,
        "dueCards": due,
        "estimatedMinutes": est_minutes,
        "dailyTarget": sizes["words"],
        "focusModules": prefs.get("focusModules") or [],
        "targetBand": prefs.get("targetBand"),
        "examDate": prefs.get("examDate"),
    }


# ---- Quiz ------------------------------------------------------------------
@router.get("/quiz")
async def quiz(
    uid: str = Depends(current_user_id),
    mode: str = "meaning",
    count: int = Query(10, ge=1, le=20),
):
    """Generate quiz questions from enriched vocabulary/phrases."""
    pool = [d async for d in db.vocab().find(
        {"userId": uid, "hidden": {"$ne": True}, "simpleEnglishMeaning": {"$ne": ""}}
    ).sort("priorityScore", -1).limit(120)]
    if len(pool) < 4:
        return {"questions": [], "message": "Not enough enriched vocabulary to build a quiz yet."}

    random.shuffle(pool)
    selected = pool[:count]
    questions = []
    for item in selected:
        distractors = random.sample([p for p in pool if p["_id"] != item["_id"]], k=min(3, len(pool) - 1))
        if mode == "fill_blank" and item.get("examples"):
            sentence = item["examples"][0]
            blanked = sentence.replace(item["word"], "_____", 1)
            options = [item["word"]] + [d["word"] for d in distractors]
            correct = item["word"]
            prompt = blanked
        elif mode == "collocation" and item.get("collocations"):
            prompt = f"Which collocation is correct for '{item['word']}'?"
            options = [item["collocations"][0]] + [
                (d.get("collocations") or [d["word"]])[0] for d in distractors
            ]
            correct = item["collocations"][0]
        else:  # meaning
            prompt = f"What does '{item['word']}' mean?"
            options = [item.get("simpleEnglishMeaning") or item["word"]] + [
                d.get("simpleEnglishMeaning") or d["word"] for d in distractors
            ]
            correct = item.get("simpleEnglishMeaning") or item["word"]
        opts = list(dict.fromkeys(options))
        random.shuffle(opts)
        questions.append({
            "id": str(item["_id"]),
            "prompt": prompt,
            "options": opts,
            "correct": correct,
            "word": item["word"],
        })
    return {"mode": mode, "questions": questions}
