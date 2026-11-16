"""Study system: flashcards, review queue, daily plan, quiz."""
from __future__ import annotations
import random
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import database as db
from auth.dependencies import current_user_id, get_current_user
from http_util import clamp_limit
from utils.serialization import now, oid, is_oid, serialize
from ai import service as ai
from config import settings
from quotas import consume_ai_call
from study import sm2
from study.day_progress import (
    ensure_session,
    grades_for_session,
    hidden_source,
    mark_reviewed,
    place_after_removal,
    remaining_ids,
    session_for_reload,
    session_frontier,
    session_index,
    session_without_card,
    today_key,
)
from study.quiz_session import MODES, clean_questions, quiz_progress, resumable
from study.plan import focus_query, focus_skill_tokens, plan_sizes
from study.translate import LANGUAGES, card_source_text, normalize_language, normalize_translation, stored_translation

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
    if not item or item.get("hidden"):
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


async def _hidden_refs(uid: str, cards: list[dict]) -> set[tuple[str, str]]:
    grouped: dict[str, list] = {}
    for card in cards:
        ref = str(card.get("refId") or "")
        if card.get("type") in _TYPE_COL and is_oid(ref):
            grouped.setdefault(card["type"], []).append(oid(ref))
    hidden: set[tuple[str, str]] = set()
    for item_type, ids in grouped.items():
        cursor = _TYPE_COL[item_type]().find(
            {"_id": {"$in": ids}, "userId": uid, "hidden": True},
            {"_id": 1},
        )
        async for doc in cursor:
            hidden.add((item_type, str(doc["_id"])))
    return hidden


async def _due_card_ids(uid: str, limit: int) -> list[str]:
    q = {"userId": uid, "nextReviewAt": {"$lte": now()}}
    cur = db.cards().find(q, {"_id": 1}).sort([("status", 1), ("nextReviewAt", 1)]).limit(limit)
    return [str(doc["_id"]) async for doc in cur]


@router.get("/queue")
async def review_queue(
    uid: str = Depends(current_user_id),
    limit: int = Query(40, ge=1, le=100),
    restart: bool = Query(False),
):
    """Today's remaining cards, in the order the session started.

    ``restart`` is the Reload queue button: the same cards come back from the
    start. A normal refresh does not pass it, so finished cards stay finished.
    """
    capped = clamp_limit(limit, default=40, maximum=100)
    session = await db.study_progress().find_one({"_id": f"{uid}:{now().date().isoformat()}"})
    if restart and session and session.get("cardIds"):
        card_ids, reviewed_ids = session_for_reload(session.get("cardIds"))
        await db.study_progress().update_one(
            {"_id": session["_id"]},
            {"$set": {
                "cardIds": card_ids,
                "reviewedIds": reviewed_ids,
                "currentCardId": None,
                "atEnd": False,
            }},
        )
        session["cardIds"] = card_ids
        session["reviewedIds"] = reviewed_ids
        session["currentCardId"] = None
        session["atEnd"] = False
    elif not session or not session.get("cardIds"):
        session = await ensure_session(uid, await _due_card_ids(uid, capped))
    order: list[str] = []
    for card_id in session.get("cardIds") or []:
        sid = str(card_id)
        if sid and sid not in order:
            order.append(sid)
    found: dict = {}
    ids = [oid(card_id) for card_id in order if is_oid(card_id)]
    if ids:
        async for doc in db.cards().find({"_id": {"$in": ids}, "userId": uid}):
            found[str(doc["_id"])] = doc
    loaded = [found[card_id] for card_id in order if card_id in found]
    hidden = await _hidden_refs(uid, loaded)
    visible = [card for card in loaded if not hidden_source(card, hidden)]
    visible_ids = [str(card["_id"]) for card in visible]
    index = session_index(
        visible_ids,
        session.get("reviewedIds"),
        session.get("currentCardId"),
        bool(session.get("atEnd")),
    )
    frontier = session_frontier(visible_ids, session.get("reviewedIds"))
    grades = grades_for_session(
        await _today_reviews(uid, visible_ids),
        session.get("reviewedIds"),
    )
    items = [serialize(card) for card in visible]
    return {
        "items": items,
        "totalDue": len(remaining_ids(visible_ids, session.get("reviewedIds"))),
        "reviewedToday": len(session.get("reviewedIds") or []),
        "index": index,
        "reached": max(index, frontier),
        "grades": grades,
    }


class SessionPlace(BaseModel):
    cardId: str | None = None
    atEnd: bool = False


@router.post("/session/place")
async def save_place(body: SessionPlace, uid: str = Depends(current_user_id)):
    """Remember the card on screen. A reload must not jump back to the start."""
    session = await db.study_progress().find_one({"_id": today_key(uid)})
    if not session:
        return {"ok": True}
    ids = {str(card_id) for card_id in (session.get("cardIds") or [])}
    if body.atEnd:
        update = {"currentCardId": None, "atEnd": True}
    elif body.cardId and str(body.cardId) in ids:
        update = {"currentCardId": str(body.cardId), "atEnd": False}
    else:
        return {"ok": True}
    await db.study_progress().update_one({"_id": session["_id"]}, {"$set": update})
    return {"ok": True}


async def _today_reviews(uid: str, card_ids: list[str]) -> list[dict]:
    if not card_ids:
        return []
    start = datetime.combine(now().date(), time.min, tzinfo=timezone.utc)
    cursor = db.reviews().find(
        {"userId": uid, "cardId": {"$in": card_ids}, "reviewedAt": {"$gte": start}},
    ).sort("reviewedAt", 1)
    return [doc async for doc in cursor]


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
    await mark_reviewed(uid, card_id)
    await db.reviews().insert_one({
        "userId": uid, "cardId": card_id, "type": card.get("type"), "grade": body.grade,
        "correct": body.grade in ("good", "easy"), "reviewedAt": now(),
    })
    if update["status"] == "mastered":
        col = _TYPE_COL.get(card["type"])
        if col and is_oid(card.get("refId", "")):
            await col().update_one({"_id": oid(card["refId"])}, {"$set": {"status": "mastered"}})
    return {"ok": True, **{k: serialize(v) for k, v in update.items()}}


@router.post("/cards/{card_id}/report")
async def report_card(card_id: str, uid: str = Depends(current_user_id)):
    """Remove a bad card from this user and keep it out of every later list."""
    if not is_oid(card_id):
        raise HTTPException(404, "Not found")
    card = await db.cards().find_one({"_id": oid(card_id), "userId": uid})
    if not card:
        raise HTTPException(404, "Not found")
    source = _TYPE_COL.get(card.get("type"))
    ref = str(card.get("refId") or "")
    if source and is_oid(ref):
        await source().update_one(
            {"_id": oid(ref), "userId": uid},
            {"$set": {"hidden": True, "updatedAt": now()}},
        )
    await db.cards().delete_one({"_id": card["_id"], "userId": uid})
    session = await db.study_progress().find_one({"_id": today_key(uid)})
    if session:
        current_card_id, at_end = place_after_removal(
            session.get("cardIds"),
            session.get("currentCardId"),
            bool(session.get("atEnd")),
            card_id,
        )
        card_ids, reviewed_ids = session_without_card(
            session.get("cardIds"), session.get("reviewedIds"), card_id,
        )
        await db.study_progress().update_one(
            {"_id": session["_id"]},
            {"$set": {
                "cardIds": card_ids,
                "reviewedIds": reviewed_ids,
                "currentCardId": current_card_id,
                "atEnd": at_end,
            }},
        )
    return {"ok": True}


@router.post("/cards/{card_id}/translate")
async def translate_study_card(card_id: str, user: dict = Depends(get_current_user)):
    """Translate the revealed card into the user's Settings language, once per card."""
    if not is_oid(card_id):
        raise HTTPException(404, "Not found")
    uid = user["id"]
    card = await db.cards().find_one({"_id": oid(card_id), "userId": uid})
    if not card:
        raise HTTPException(404, "Not found")
    language = normalize_language((user.get("settings") or {}).get("translationLanguage"))
    cached = stored_translation(card, language)
    if cached:
        return cached

    provider_name = (user.get("settings") or {}).get("aiProvider") or settings.ai_provider
    if ai.get_provider(provider_name) is None:
        raise HTTPException(409, "The selected AI provider is not configured")
    if not await consume_ai_call(uid, settings.max_ai_calls_per_day):
        raise HTTPException(429, "Daily AI quota reached")

    raw = await ai.translate_card(card_source_text(card), LANGUAGES[language], provider_name)
    payload = normalize_translation(raw, language)
    if not payload:
        raise HTTPException(502, "Translation failed")
    await db.cards().update_one(
        {"_id": card["_id"], "userId": uid},
        {"$set": {f"translations.{language}": payload, "updatedAt": now()}},
    )
    return payload


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


class QuizAnswerIn(BaseModel):
    questionId: str
    choice: str


class QuizStartIn(BaseModel):
    mode: str
    questions: list[dict]


class QuizProgressIn(BaseModel):
    index: int = Field(ge=0, le=20)
    answers: list[QuizAnswerIn] = []


def _quiz_view(doc: dict | None) -> dict:
    saved = resumable(doc)
    if not saved:
        return {"mode": None, "questions": [], "index": 0, "answers": [], "score": 0}
    return saved


@router.get("/quiz/session")
async def read_quiz_session(uid: str = Depends(current_user_id)):
    doc = await db.quiz_progress().find_one({"_id": uid})
    return _quiz_view(doc)


@router.post("/quiz/session")
async def start_quiz_session(body: QuizStartIn, uid: str = Depends(current_user_id)):
    """Replace any unfinished quiz. Starting a new one is explicit."""
    if body.mode not in MODES:
        raise HTTPException(400, "Invalid quiz type")
    questions = clean_questions(body.questions)
    if not questions:
        raise HTTPException(400, "A quiz needs at least one question")
    doc = {
        "_id": uid,
        "userId": uid,
        "mode": body.mode,
        "questions": questions,
        "index": 0,
        "answers": [],
        "score": 0,
        "updatedAt": now(),
        "expiresAt": now() + timedelta(days=3),
    }
    await db.quiz_progress().replace_one({"_id": uid}, doc, upsert=True)
    return _quiz_view(doc)


@router.put("/quiz/session")
async def save_quiz_session(body: QuizProgressIn, uid: str = Depends(current_user_id)):
    doc = await db.quiz_progress().find_one({"_id": uid})
    if not doc:
        raise HTTPException(404, "No quiz in progress")
    questions = clean_questions(doc.get("questions"))
    progress = quiz_progress(
        questions,
        body.index,
        [answer.model_dump() for answer in body.answers],
    )
    if progress["index"] >= len(questions):
        await db.quiz_progress().delete_one({"_id": uid})
        return {"mode": None, "questions": [], "index": 0, "answers": [], "score": progress["score"]}
    await db.quiz_progress().update_one(
        {"_id": uid},
        {"$set": {
            **progress,
            "updatedAt": now(),
            "expiresAt": now() + timedelta(days=3),
        }},
    )
    doc.update(progress)
    return _quiz_view(doc)


@router.delete("/quiz/session")
async def clear_quiz_session(uid: str = Depends(current_user_id)):
    await db.quiz_progress().delete_one({"_id": uid})
    return {"ok": True}
