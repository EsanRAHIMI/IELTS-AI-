"""End-to-end source processing pipeline.

A job references a source. Processing:
  1. parse the source into raw text (if not already present)
  2. run deterministic extraction (words / phrases / patterns)
  3. merge results into the user's collections (dedup + frequency accumulation)
  4. optionally AI-enrich the top items
  5. update job + source status with logs

Shared by the API (manual trigger) and the worker (polling loop).
"""
from __future__ import annotations
import logging

import database as db
from utils.serialization import now, oid
from ingestion.parsers import parse_file, parse_url
from extraction.extractor import extract
from jobs.schemas import JOB_PENDING, JOB_RUNNING, JOB_DONE, JOB_ERROR
from ai import service as ai

logger = logging.getLogger("ielts.jobs")

AI_ENRICH_TOP_WORDS = 15
AI_ENRICH_TOP_PHRASES = 8
AI_ENRICH_TOP_PATTERNS = 5


async def _log(job_id, message: str):
    logger.info("[job %s] %s", job_id, message)
    await db.jobs().update_one(
        {"_id": oid(job_id)},
        {"$push": {"logs": {"t": now(), "msg": message}}, "$set": {"updatedAt": now()}},
    )


async def _resolve_text(source: dict) -> tuple[str, str | None]:
    """Return (text, title_override)."""
    stype = source.get("type")
    if source.get("rawText"):
        return source["rawText"], None
    if stype == "url":
        title, text = await parse_url(source["url"])
        return text, title
    if stype == "file":
        return parse_file(source["filePath"], source.get("fileKind")), None
    return source.get("rawText", ""), None


async def claim_job(job_id: str) -> dict | None:
    """Atomically move a pending job to running. Returns the job if claimed."""
    return await db.jobs().find_one_and_update(
        {"_id": oid(job_id), "status": JOB_PENDING},
        {"$set": {"status": JOB_RUNNING, "startedAt": now(), "updatedAt": now()}},
        return_document=True,
    )


async def claim_next() -> dict | None:
    """Atomically claim the oldest pending job (used by the worker poll loop)."""
    return await db.jobs().find_one_and_update(
        {"status": JOB_PENDING},
        {"$set": {"status": JOB_RUNNING, "startedAt": now(), "updatedAt": now()}},
        sort=[("createdAt", 1)],
        return_document=True,
    )


async def run_job_by_id(job_id: str) -> None:
    """Claim (if still pending) and process a job by id. Safe to call from API."""
    job = await claim_job(job_id)
    if job is None:
        return  # already claimed/processed by the worker
    await process_job(job)


async def process_job(job: dict) -> None:
    """Process an already-claimed (running) job."""
    job_id = str(job["_id"])
    user_id = job["userId"]
    source_id = job["sourceId"]
    await _log(job_id, "Started processing")

    source = await db.sources().find_one({"_id": oid(source_id)})
    if not source:
        await db.jobs().update_one({"_id": oid(job_id)}, {"$set": {"status": JOB_ERROR, "error": "source not found"}})
        return

    try:
        await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"status": "processing"}})
        text, title_override = await _resolve_text(source)
        if title_override and not source.get("title"):
            await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"title": title_override}})
        await db.sources().update_one(
            {"_id": oid(source_id)},
            {"$set": {"rawText": text[:500000], "charCount": len(text)}},
        )
        await _log(job_id, f"Extracted {len(text)} characters of text")

        result = extract(text)
        await _log(
            job_id,
            f"Found {len(result.words)} words, {len(result.phrases)} phrases, "
            f"{len(result.patterns)} patterns",
        )

        n_words = await _merge_words(user_id, source_id, result.words)
        n_phrases = await _merge_phrases(user_id, source_id, result.phrases)
        n_patterns = await _merge_patterns(user_id, source_id, result.patterns)
        await _log(job_id, f"Merged into DB: +{n_words} words, +{n_phrases} phrases, +{n_patterns} patterns")

        if ai.ai_available():
            await _log(job_id, "AI provider available - enriching top items")
            await _enrich_top(user_id, source_id, job_id)
        else:
            await _log(job_id, "No AI provider configured - skipping enrichment")

        await db.sources().update_one(
            {"_id": oid(source_id)},
            {"$set": {"status": "done", "stats": result.stats, "processedAt": now()}},
        )
        await db.jobs().update_one(
            {"_id": oid(job_id)},
            {"$set": {"status": JOB_DONE, "finishedAt": now(),
                      "result": {"words": n_words, "phrases": n_phrases, "patterns": n_patterns}}},
        )
        await _log(job_id, "Done")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"status": "error"}})
        await db.jobs().update_one(
            {"_id": oid(job_id)}, {"$set": {"status": JOB_ERROR, "error": str(exc), "finishedAt": now()}}
        )
        await _log(job_id, f"ERROR: {exc}")


# Merge helpers --------------------------------------------------------------
async def _merge_words(user_id: str, source_id: str, words: list[dict]) -> int:
    added = 0
    for w in words:
        existing = await db.vocab().find_one({"userId": user_id, "lemma": w["lemma"]})
        if existing:
            new_freq = existing.get("frequency", 0) + w["frequency"]
            src_ids = list(set(existing.get("sourceIds", []) + [source_id]))
            from extraction import scoring
            ps = scoring.score_word(
                frequency=new_freq, difficulty=existing.get("difficulty", w["difficulty"]),
                lemma=w["lemma"], n_collocations=len(set(existing.get("collocations", []) + w["collocations"])),
                ielts_use_cases=existing.get("ieltsUseCases", w["ieltsUseCases"]), source_count=len(src_ids),
            )
            await db.vocab().update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "frequency": new_freq, "priorityScore": ps, "sourceIds": src_ids,
                    "collocations": list(dict.fromkeys(existing.get("collocations", []) + w["collocations"]))[:8],
                    "examples": list(dict.fromkeys(existing.get("examples", []) + w["examples"]))[:5],
                    "updatedAt": now(),
                }},
            )
        else:
            doc = {**w, "userId": user_id, "sourceIds": [source_id], "status": "new",
                   "important": False, "hidden": False, "createdAt": now(), "updatedAt": now()}
            await db.vocab().insert_one(doc)
            added += 1
    return added


async def _merge_phrases(user_id: str, source_id: str, phrases: list[dict]) -> int:
    added = 0
    for p in phrases:
        existing = await db.phrases().find_one({"userId": user_id, "phrase": p["phrase"]})
        if existing:
            new_freq = existing.get("frequency", 0) + p["frequency"]
            src_ids = list(set(existing.get("sourceIds", []) + [source_id]))
            await db.phrases().update_one(
                {"_id": existing["_id"]},
                {"$set": {"frequency": new_freq, "sourceIds": src_ids, "updatedAt": now()}},
            )
        else:
            doc = {**p, "userId": user_id, "sourceIds": [source_id], "status": "new",
                   "important": False, "hidden": False, "createdAt": now(), "updatedAt": now()}
            await db.phrases().insert_one(doc)
            added += 1
    return added


async def _merge_patterns(user_id: str, source_id: str, patterns: list[dict]) -> int:
    added = 0
    for p in patterns:
        existing = await db.patterns().find_one({"userId": user_id, "sentence": p["sentence"]})
        if existing:
            await db.patterns().update_one(
                {"_id": existing["_id"]},
                {"$addToSet": {"sourceIds": source_id}, "$set": {"updatedAt": now()}},
            )
        else:
            doc = {**p, "userId": user_id, "sourceIds": [source_id], "status": "new",
                   "important": False, "hidden": False, "createdAt": now(), "updatedAt": now()}
            await db.patterns().insert_one(doc)
            added += 1
    return added


async def _enrich_top(user_id: str, source_id: str, job_id: str) -> None:
    cur = db.vocab().find(
        {"userId": user_id, "sourceIds": source_id, "aiEnriched": False}
    ).sort("priorityScore", -1).limit(AI_ENRICH_TOP_WORDS)
    async for w in cur:
        data = await ai.explain_word(w["word"], w.get("partOfSpeech", ""),
                                     (w.get("examples") or [""])[0])
        update = {"aiEnriched": True, "updatedAt": now()}
        for key in ("persianMeaning", "simpleEnglishMeaning", "difficulty",
                    "ieltsUseCases", "commonMistakes"):
            if data.get(key):
                update[key] = data[key]
        if data.get("collocations"):
            update["collocations"] = list(dict.fromkeys(w.get("collocations", []) + data["collocations"]))[:8]
        if data.get("examples"):
            update["examples"] = list(dict.fromkeys(w.get("examples", []) + data["examples"]))[:5]
        if data.get("notes"):
            update["notes"] = data["notes"]
        await db.vocab().update_one({"_id": w["_id"]}, {"$set": update})
    await _log(job_id, "Enriched top words")

    cur = db.phrases().find(
        {"userId": user_id, "sourceIds": source_id, "aiEnriched": False}
    ).sort("priorityScore", -1).limit(AI_ENRICH_TOP_PHRASES)
    async for p in cur:
        data = await ai.explain_phrase(p["phrase"], (p.get("examples") or [""])[0])
        update = {"aiEnriched": True, "updatedAt": now()}
        for key in ("persianMeaning", "simpleEnglishMeaning", "notes"):
            if data.get(key):
                update[key] = data[key]
        if data.get("examples"):
            update["examples"] = list(dict.fromkeys(p.get("examples", []) + data["examples"]))[:4]
        await db.phrases().update_one({"_id": p["_id"]}, {"$set": update})

    cur = db.patterns().find(
        {"userId": user_id, "sourceIds": source_id, "aiEnriched": False}
    ).sort("priorityScore", -1).limit(AI_ENRICH_TOP_PATTERNS)
    async for pat in cur:
        data = await ai.classify_pattern(pat["sentence"])
        update = {"aiEnriched": True, "updatedAt": now()}
        for key in ("category", "template", "notes"):
            if data.get(key):
                update[key] = data[key]
        await db.patterns().update_one({"_id": pat["_id"]}, {"$set": update})
    await _log(job_id, "Enriched top phrases and patterns")


async def create_job(user_id: str, source_id: str, kind: str = "process") -> str:
    doc = {
        "userId": user_id, "sourceId": source_id, "kind": kind,
        "status": "pending", "logs": [], "createdAt": now(), "updatedAt": now(),
    }
    res = await db.jobs().insert_one(doc)
    return str(res.inserted_id)
