"""End-to-end source processing pipeline.

A job references a source. Processing:
  1. parse the source into raw text (if not already present)
  2. run deterministic extraction (words / phrases / patterns)
  3. merge results into the user's collections (dedup + frequency accumulation)
  4. optionally AI-enrich the top items
  5. update job + source status with logs

Runs inside the API process via asyncio tasks (not tied to the browser session).
"""
from __future__ import annotations
import asyncio
import logging

from pymongo.errors import DuplicateKeyError

import database as db
from config import settings
from utils.serialization import now, oid, is_oid
from ingestion.parsers import parse_url, parse_pdf_document, parse_bytes, ParsedDocument
from extraction.extractor import extract, clean_text
from extraction.ielts_markers import classify_sentence_section
from jobs.merge_stats import apply_source_stats
from jobs.schemas import JOB_PENDING, JOB_PROCESSING, JOB_DONE, JOB_FAILED, JOB_CANCELLED_MSG, JOB_INTERRUPTED_MSG
from storage import s3_service
from ai import service as ai
from quotas import consume_ai_call
from security_policy import public_job_error

logger = logging.getLogger("ielts.jobs")

_running_tasks: dict[str, asyncio.Task] = {}
_job_slots = asyncio.Semaphore(max(1, settings.max_concurrent_jobs))

AI_ENRICH_TOP_WORDS = 15
AI_ENRICH_TOP_PHRASES = 8
AI_ENRICH_TOP_PATTERNS = 5

# Chunking: target ~850 words per chunk with ~100-word overlap so context
# straddling a boundary is not lost. A 400-page book yields dozens-hundreds.
CHUNK_WORDS = 850
CHUNK_OVERLAP = 100

# Stored text caps (Mongo 16MB doc limit safety). Page-level text in
# source_pages is NOT capped here so the full corpus survives.
MAX_STORED_TEXT = 2_000_000


async def _log(job_id, message: str):
    logger.info("[job %s] %s", job_id, message)
    await db.jobs().update_one(
        {"_id": oid(job_id)},
        {"$push": {"logs": {"t": now(), "msg": message}}, "$set": {"updatedAt": now()}},
    )


class ResolvedSource:
    """Outcome of turning a source into raw text. ``doc`` is set for PDFs and
    carries page-level provenance (embedded text vs OCR)."""

    def __init__(self, text: str, title_override: str | None = None,
                 doc: ParsedDocument | None = None):
        self.text = text
        self.title_override = title_override
        self.doc = doc


async def _resolve_text(source: dict) -> ResolvedSource:
    """Resolve a source to raw text. Pulls binaries from S3; never reads
    permanent local project storage. PDFs get the rich page-level parse."""
    stype = source.get("type")
    file_kind = (source.get("fileKind") or stype or "").lower()
    # File-backed sources: download bytes from S3 and parse in memory.
    if source.get("kind") == "file" or source.get("s3Key"):
        data = await asyncio.to_thread(s3_service.download_bytes, source["s3Key"])
        if file_kind == "pdf":
            doc = await asyncio.to_thread(parse_pdf_document, data)
            return ResolvedSource(doc.text, None, doc)
        return ResolvedSource(await asyncio.to_thread(parse_bytes, data, file_kind), None)
    if stype == "url":
        title, text = await parse_url(source["url"])
        return ResolvedSource(text, title)
    # Pasted text: rawText is the original input.
    return ResolvedSource(source.get("rawText", ""))


def _build_chunks(cleaned: str) -> list[dict]:
    """Split cleaned text into overlapping word-bounded chunks.

    ~CHUNK_WORDS per chunk with CHUNK_OVERLAP words of overlap so phrases and
    sentences spanning a boundary are still captured by the extractor.
    """
    words = cleaned.split()
    chunks: list[dict] = []
    if not words:
        return chunks
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    for i in range(0, len(words), step):
        piece = " ".join(words[i : i + CHUNK_WORDS])
        if not piece.strip():
            continue
        chunks.append({
            "index": len(chunks),
            "text": piece,
            "section": classify_sentence_section(piece[:600]),
            "tokenCount": len(piece.split()),
        })
        if i + CHUNK_WORDS >= len(words):
            break
    return chunks


async def _store_pages(user_id: str, source_id: str, doc: ParsedDocument) -> None:
    """Persist page-level extraction in source_pages (replacing any prior run)."""
    await db.source_pages().delete_many({"sourceId": source_id})
    if not doc.pages:
        return
    ts = now()
    docs = [{
        "userId": user_id, "sourceId": source_id, "pageNumber": p.pageNumber,
        "text": (p.text or "")[: settings.max_page_chars], "method": p.method,
        "charCount": p.charCount,
        "warning": p.warning, "createdAt": ts, "updatedAt": ts,
    } for p in doc.pages]
    # Insert in batches to stay well under Mongo's per-batch limits.
    for i in range(0, len(docs), 200):
        await db.source_pages().insert_many(docs[i : i + 200])


async def _store_text_and_chunks(user_id: str, source_id: str, raw: str, cleaned: str) -> int:
    """Persist raw + cleaned text on the source and chunks in source_chunks."""
    chunks = _build_chunks(cleaned)
    await db.sources().update_one(
        {"_id": oid(source_id)},
        {"$set": {
            "rawText": raw[:MAX_STORED_TEXT], "cleanedText": cleaned[:MAX_STORED_TEXT],
            "charCount": len(raw), "chunkCount": len(chunks), "updatedAt": now(),
        }},
    )
    # Replace any previous chunks (idempotent on reprocess).
    await db.source_chunks().delete_many({"sourceId": source_id})
    if chunks:
        for i in range(0, len(chunks), 200):
            batch = chunks[i : i + 200]
            await db.source_chunks().insert_many(
                [{**c, "sourceId": source_id, "userId": user_id, "createdAt": now()} for c in batch]
            )
    return len(chunks)


def _quality_status(page_count: int, cleaned_chars: int, chunk_count: int,
                    patterns_extracted: int, doc: ParsedDocument | None) -> tuple[str, list[str]]:
    """Heuristics flagging likely-incomplete extraction (e.g. scanned PDF)."""
    warnings: list[str] = list(doc.warnings) if doc else []
    failed = False
    warned = False

    if cleaned_chars == 0:
        failed = True
        warnings.append("No text could be extracted from this source.")
    if page_count > 30 and cleaned_chars < 100_000:
        warned = True
        warnings.append("Extraction may be incomplete. This PDF may be scanned or OCR failed.")
    if chunk_count < 10 and page_count > 30:
        warned = True
        warnings.append(f"Only {chunk_count} chunks for {page_count} pages — text density is very low.")
    if patterns_extracted == 0 and cleaned_chars > 50_000:
        warned = True
        warnings.append("No sentence patterns found despite a large corpus — extraction may be degraded.")

    status = "failed" if failed else ("warning" if warned else "ok")

    # de-dupe while preserving order
    seen: set[str] = set()
    deduped = [w for w in warnings if not (w in seen or seen.add(w))]
    return status, deduped


async def claim_job(job_id: str) -> dict | None:
    """Atomically move a pending job to processing. Returns the job if claimed.

    Atomic claiming keeps processing idempotent even if the same job were ever
    triggered twice (e.g. a quick double reprocess).
    """
    return await db.jobs().find_one_and_update(
        {"_id": oid(job_id), "status": JOB_PENDING},
        {"$set": {"status": JOB_PROCESSING, "startedAt": now(), "updatedAt": now()}},
        return_document=True,
    )


async def _still_processing(job_id: str) -> bool:
    doc = await db.jobs().find_one({"_id": oid(job_id)}, {"status": 1})
    return bool(doc and doc.get("status") == JOB_PROCESSING)


async def _source_alive(source_id: str, user_id: str) -> bool:
    if not is_oid(source_id):
        return False
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": user_id}, {"_id": 1})
    return doc is not None


async def _gate(job_id: str, source_id: str, user_id: str) -> bool:
    """Stop writing when another replica cancelled the job or the source was deleted."""
    return await _still_processing(job_id) and await _source_alive(source_id, user_id)


async def run_job_by_id(job_id: str) -> None:
    """Claim (if still pending) and process a job by id, off the request path."""
    async with _job_slots:
        try:
            job = await claim_job(job_id)
            if job is None:
                return
            try:
                await asyncio.wait_for(process_job(job), timeout=settings.job_timeout_seconds)
            except asyncio.TimeoutError:
                if await _still_processing(job_id):
                    await _fail_job(job_id, job.get("sourceId"), "Processing timed out")
        except asyncio.CancelledError:
            doc = await db.jobs().find_one({"_id": oid(job_id)})
            if doc and doc.get("status") == JOB_PROCESSING:
                await _fail_job(job_id, doc.get("sourceId"), JOB_CANCELLED_MSG)
            raise


def schedule_job(job_id: str) -> None:
    """Start a job task in the background (survives HTTP response; cancellable)."""
    if job_id in _running_tasks and not _running_tasks[job_id].done():
        return
    task = asyncio.create_task(run_job_by_id(job_id))
    _running_tasks[job_id] = task

    def _done(t: asyncio.Task) -> None:
        _running_tasks.pop(job_id, None)
        if not t.cancelled() and t.exception():
            logger.error("Job task %s exited with error", job_id)

    task.add_done_callback(_done)


async def cancel_job(job_id: str, user_id: str) -> bool:
    """Stop a running job and mark it failed/cancelled."""
    if not is_oid(job_id):
        return False
    job = await db.jobs().find_one({"_id": oid(job_id), "userId": user_id})
    if not job or job["status"] in (JOB_DONE, JOB_FAILED):
        return False

    source_id = job.get("sourceId")
    await _fail_job(job_id, source_id, JOB_CANCELLED_MSG)

    task = _running_tasks.pop(job_id, None)
    if task and not task.done():
        task.cancel()
    return True


async def cancel_jobs_for_source(user_id: str, source_id: str) -> None:
    """Stop every active job for a source before it is deleted or reprocessed."""
    cur = db.jobs().find({
        "userId": user_id,
        "sourceId": source_id,
        "status": {"$in": [JOB_PENDING, JOB_PROCESSING]},
    })
    async for doc in cur:
        await cancel_job(str(doc["_id"]), user_id)


async def _fail_job(job_id: str, source_id: str | None, message: str) -> None:
    await db.jobs().update_one(
        {"_id": oid(job_id)},
        {"$set": {"status": JOB_FAILED, "error": message, "finishedAt": now(), "updatedAt": now()}},
    )
    await _log(job_id, f"ERROR: {message}")
    if source_id and is_oid(source_id):
        await db.sources().update_one(
            {"_id": oid(source_id)},
            {"$set": {"status": "error", "updatedAt": now(),
                      "stats.warnings": [message]}},
        )


async def process_job(job: dict) -> None:
    """Process an already-claimed (running) job."""
    job_id = str(job["_id"])
    user_id = job["userId"]
    source_id = job["sourceId"]
    await _log(job_id, "Started processing")

    source = await db.sources().find_one({"_id": oid(source_id), "userId": user_id})
    if not source:
        if await _still_processing(job_id):
            await _fail_job(job_id, source_id, "Processing failed")
        return

    try:
        await db.sources().update_one(
            {"_id": oid(source_id), "userId": user_id},
            {"$set": {"status": "processing"}},
        )
        resolved = await _resolve_text(source)
        if not await _gate(job_id, source_id, user_id):
            return
        text = resolved.text
        doc = resolved.doc
        if resolved.title_override and not source.get("title"):
            await db.sources().update_one(
                {"_id": oid(source_id), "userId": user_id},
                {"$set": {"title": resolved.title_override}},
            )

        # Page-level provenance (PDFs only).
        if doc is not None:
            await _store_pages(user_id, source_id, doc)
            await _log(job_id, f"PDF pages detected: {doc.pageCount}")
            await _log(job_id, f"Embedded text pages: {doc.extractedPages}")
            await _log(job_id, f"OCR pages: {doc.ocrPages}")
            await _log(job_id, f"Empty pages: {doc.emptyPages}")
            for w in doc.warnings:
                await _log(job_id, f"WARNING: {w}")

        # Clean once and reuse for storage, chunking AND extraction.
        cleaned = clean_text(text)
        n_chunks = await _store_text_and_chunks(user_id, source_id, text, cleaned)
        await _log(job_id, f"Raw text chars: {len(text)}")
        await _log(job_id, f"Cleaned text chars: {len(cleaned)}")
        await _log(job_id, f"Chunks created: {n_chunks}")

        # Extract on the full cleaned corpus, off the event loop.
        result = await asyncio.to_thread(extract, cleaned)
        if not await _gate(job_id, source_id, user_id):
            return
        await _log(job_id, f"Words extracted: {len(result.words)}")
        await _log(job_id, f"Phrases extracted: {len(result.phrases)}")
        await _log(job_id, f"Patterns extracted: {len(result.patterns)}")

        await _log(job_id, "Saving extracted items to database…")
        n_words = await _merge_words(user_id, source_id, result.words)
        n_phrases = await _merge_phrases(user_id, source_id, result.phrases)
        n_patterns = await _merge_patterns(user_id, source_id, result.patterns)
        await _log(job_id, f"Merged into DB: +{n_words} words, +{n_phrases} phrases, +{n_patterns} patterns")

        provider_name = await _user_provider(user_id)
        if ai.get_provider(provider_name):
            await _log(job_id, f"AI provider '{provider_name}' - enriching top items")
            await _enrich_top(user_id, source_id, job_id, provider_name)
        else:
            await _log(job_id, f"AI provider '{provider_name}' is not configured - skipping enrichment")

        # Build the rich source.stats payload + quality assessment.
        page_count = doc.pageCount if doc else 0
        quality, warnings = _quality_status(
            page_count, len(cleaned), n_chunks, len(result.patterns), doc)
        stats = {
            **result.stats,
            "pageCount": page_count,
            "extractedPages": doc.extractedPages if doc else 0,
            "ocrPages": doc.ocrPages if doc else 0,
            "emptyPages": doc.emptyPages if doc else 0,
            "rawTextChars": len(text),
            "cleanedTextChars": len(cleaned),
            "chunkCount": n_chunks,
            "wordsExtracted": len(result.words),
            "phrasesExtracted": len(result.phrases),
            "patternsExtracted": len(result.patterns),
            "extractionMethod": doc.extractionMethod if doc else "text",
            "qualityStatus": quality,
            "warnings": warnings,
        }
        await _log(job_id, f"Quality status: {quality}")

        if not await _gate(job_id, source_id, user_id):
            return
        # Only the worker that still owns the processing row may mark it done.
        finished = await db.jobs().update_one(
            {"_id": oid(job_id), "status": JOB_PROCESSING},
            {"$set": {"status": JOB_DONE, "finishedAt": now(),
                      "result": {"words": n_words, "phrases": n_phrases, "patterns": n_patterns}}},
        )
        if finished.modified_count:
            await db.sources().update_one(
                {"_id": oid(source_id), "userId": user_id},
                {"$set": {"status": "done", "stats": stats, "processedAt": now()}},
            )
            await _log(job_id, "Done")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        if await _still_processing(job_id):
            await _fail_job(job_id, source_id, public_job_error(exc))


# Merge helpers --------------------------------------------------------------
def _joined(existing: dict | None, key: str, extra: list, limit: int) -> list:
    base = (existing or {}).get(key) or []
    return list(dict.fromkeys(list(base) + list(extra or [])))[:limit]


async def _merge_words(user_id: str, source_id: str, words: list[dict]) -> int:
    from extraction import scoring

    added = 0
    for w in words:
        existing = await db.vocab().find_one({"userId": user_id, "lemma": w["lemma"]})
        stats = apply_source_stats(existing, source_id, w.get("frequency") or 0)
        collocs = _joined(existing, "collocations", w.get("collocations") or [], 8)
        examples = _joined(existing, "examples", w.get("examples") or [], 5)
        use_cases = (existing or w).get("ieltsUseCases") or w.get("ieltsUseCases") or []
        difficulty = (existing or w).get("difficulty") or w.get("difficulty") or ""
        ps = scoring.score_word(
            frequency=stats["frequency"], difficulty=difficulty, lemma=w["lemma"],
            n_collocations=len(collocs), ielts_use_cases=use_cases, source_count=len(stats["sourceIds"]),
        )
        fields = {
            "frequency": stats["frequency"], "sourceFrequency": stats["sourceFrequency"],
            "sourceIds": stats["sourceIds"], "priorityScore": ps,
            "collocations": collocs, "examples": examples, "updatedAt": now(),
        }
        if existing:
            await db.vocab().update_one({"_id": existing["_id"], "userId": user_id}, {"$set": fields})
            continue
        doc = {**w, **fields, "userId": user_id, "status": "new", "important": False, "hidden": False, "createdAt": now()}
        try:
            await db.vocab().insert_one(doc)
            added += 1
        except DuplicateKeyError:
            existing = await db.vocab().find_one({"userId": user_id, "lemma": w["lemma"]})
            if not existing:
                continue
            stats = apply_source_stats(existing, source_id, w.get("frequency") or 0)
            fields["frequency"] = stats["frequency"]
            fields["sourceFrequency"] = stats["sourceFrequency"]
            fields["sourceIds"] = stats["sourceIds"]
            await db.vocab().update_one({"_id": existing["_id"], "userId": user_id}, {"$set": fields})
    return added


async def _merge_phrases(user_id: str, source_id: str, phrases: list[dict]) -> int:
    from extraction import scoring

    added = 0
    for p in phrases:
        existing = await db.phrases().find_one({"userId": user_id, "phrase": p["phrase"]})
        stats = apply_source_stats(existing, source_id, p.get("frequency") or 0)
        section = (existing or p).get("section") or ""
        confidence = (existing or p).get("confidence") or p.get("confidence") or 0
        length = (existing or p).get("length") or p.get("length") or len(str(p.get("phrase") or "").split())
        ps = scoring.score_phrase(
            frequency=stats["frequency"], confidence=confidence, length=length, category=section,
        )
        fields = {
            "frequency": stats["frequency"], "sourceFrequency": stats["sourceFrequency"],
            "sourceIds": stats["sourceIds"], "priorityScore": ps, "updatedAt": now(),
        }
        if existing:
            await db.phrases().update_one({"_id": existing["_id"], "userId": user_id}, {"$set": fields})
            continue
        doc = {**p, **fields, "userId": user_id, "status": "new", "important": False, "hidden": False, "createdAt": now()}
        try:
            await db.phrases().insert_one(doc)
            added += 1
        except DuplicateKeyError:
            existing = await db.phrases().find_one({"userId": user_id, "phrase": p["phrase"]})
            if existing:
                stats = apply_source_stats(existing, source_id, p.get("frequency") or 0)
                fields["frequency"] = stats["frequency"]
                fields["sourceFrequency"] = stats["sourceFrequency"]
                fields["sourceIds"] = stats["sourceIds"]
                await db.phrases().update_one({"_id": existing["_id"], "userId": user_id}, {"$set": fields})
    return added


async def _merge_patterns(user_id: str, source_id: str, patterns: list[dict]) -> int:
    added = 0
    for p in patterns:
        existing = await db.patterns().find_one({"userId": user_id, "sentence": p["sentence"]})
        if existing:
            await db.patterns().update_one(
                {"_id": existing["_id"], "userId": user_id},
                {"$addToSet": {"sourceIds": source_id}, "$set": {"updatedAt": now()}},
            )
            continue
        doc = {**p, "userId": user_id, "sourceIds": [source_id], "status": "new",
               "important": False, "hidden": False, "createdAt": now(), "updatedAt": now()}
        try:
            await db.patterns().insert_one(doc)
            added += 1
        except DuplicateKeyError:
            await db.patterns().update_one(
                {"userId": user_id, "sentence": p["sentence"]},
                {"$addToSet": {"sourceIds": source_id}, "$set": {"updatedAt": now()}},
            )
    return added


async def _user_provider(user_id: str) -> str:
    if not is_oid(user_id):
        return settings.ai_provider
    user = await db.users().find_one({"_id": oid(user_id)}, {"settings.aiProvider": 1})
    choice = ((user or {}).get("settings") or {}).get("aiProvider")
    return choice or settings.ai_provider


async def _enrich_top(user_id: str, source_id: str, job_id: str, provider_name: str) -> None:
    cur = db.vocab().find(
        {"userId": user_id, "sourceIds": source_id, "aiEnriched": False}
    ).sort("priorityScore", -1).limit(AI_ENRICH_TOP_WORDS)
    async for w in cur:
        if not await consume_ai_call(user_id, settings.max_ai_calls_per_day):
            await _log(job_id, "Daily AI quota reached")
            return
        data = await ai.explain_word(
            w["word"], w.get("partOfSpeech", ""), (w.get("examples") or [""])[0], provider_name,
        )
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
        if not await consume_ai_call(user_id, settings.max_ai_calls_per_day):
            await _log(job_id, "Daily AI quota reached")
            return
        data = await ai.explain_phrase(p["phrase"], (p.get("examples") or [""])[0], provider_name)
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
        if not await consume_ai_call(user_id, settings.max_ai_calls_per_day):
            await _log(job_id, "Daily AI quota reached")
            return
        data = await ai.classify_pattern(pat["sentence"], provider_name)
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


async def recover_orphaned_jobs() -> int:
    """On API startup: fail interrupted jobs; re-queue only never-started pending ones."""
    failed = 0
    async for job in db.jobs().find({"status": JOB_PROCESSING}):
        jid = str(job["_id"])
        await _fail_job(jid, job.get("sourceId"), JOB_INTERRUPTED_MSG)
        failed += 1

    resumed = 0
    async for job in db.jobs().find({"status": JOB_PENDING}):
        schedule_job(str(job["_id"]))
        resumed += 1

    if failed or resumed:
        logger.info("Startup job recovery: %d interrupted (failed), %d pending (resumed)", failed, resumed)
    return resumed
