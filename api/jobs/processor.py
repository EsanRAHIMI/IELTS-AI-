"""End-to-end source processing pipeline.

A job references a source. Processing:
  1. parse the source into raw text (if not already present)
  2. run deterministic extraction (words / phrases / patterns)
  3. merge results into the user's collections (dedup + frequency accumulation)
  4. optionally AI-enrich the top items
  5. update job + source status with logs

Runs inside the API process via a FastAPI BackgroundTask.
"""
from __future__ import annotations
import logging

import database as db
from utils.serialization import now, oid
from ingestion.parsers import parse_url, parse_pdf_document, parse_bytes, ParsedDocument
from extraction.extractor import extract, clean_text
from extraction.ielts_markers import classify_sentence_section
from jobs.schemas import JOB_PENDING, JOB_PROCESSING, JOB_DONE, JOB_FAILED
from storage import s3_service
from ai import service as ai

logger = logging.getLogger("ielts.jobs")

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
        data = s3_service.download_bytes(source["s3Key"])
        if file_kind == "pdf":
            doc = parse_pdf_document(data)
            return ResolvedSource(doc.text, None, doc)
        return ResolvedSource(parse_bytes(data, file_kind), None)
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
        "text": p.text, "method": p.method, "charCount": p.charCount,
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


async def run_job_by_id(job_id: str) -> None:
    """Claim (if still pending) and process a job by id. Called from the API's
    FastAPI BackgroundTask."""
    job = await claim_job(job_id)
    if job is None:
        return  # already claimed/processed
    await process_job(job)


async def process_job(job: dict) -> None:
    """Process an already-claimed (running) job."""
    job_id = str(job["_id"])
    user_id = job["userId"]
    source_id = job["sourceId"]
    await _log(job_id, "Started processing")

    source = await db.sources().find_one({"_id": oid(source_id)})
    if not source:
        await db.jobs().update_one({"_id": oid(job_id)}, {"$set": {"status": JOB_FAILED, "error": "source not found"}})
        return

    try:
        await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"status": "processing"}})
        resolved = await _resolve_text(source)
        text = resolved.text
        doc = resolved.doc
        if resolved.title_override and not source.get("title"):
            await db.sources().update_one(
                {"_id": oid(source_id)}, {"$set": {"title": resolved.title_override}})

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

        # Extract on the FULL cleaned corpus (not a preview slice).
        result = extract(cleaned)
        await _log(job_id, f"Words extracted: {len(result.words)}")
        await _log(job_id, f"Phrases extracted: {len(result.phrases)}")
        await _log(job_id, f"Patterns extracted: {len(result.patterns)}")

        await _log(job_id, "Saving extracted items to database…")
        n_words = await _merge_words(user_id, source_id, result.words)
        n_phrases = await _merge_phrases(user_id, source_id, result.phrases)
        n_patterns = await _merge_patterns(user_id, source_id, result.patterns)
        await _log(job_id, f"Merged into DB: +{n_words} words, +{n_phrases} phrases, +{n_patterns} patterns")

        if ai.ai_available():
            await _log(job_id, "AI provider available - enriching top items")
            await _enrich_top(user_id, source_id, job_id)
        else:
            await _log(job_id, "No AI provider configured - skipping enrichment")

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

        await db.sources().update_one(
            {"_id": oid(source_id)},
            {"$set": {"status": "done", "stats": stats, "processedAt": now()}},
        )
        await db.jobs().update_one(
            {"_id": oid(job_id)},
            {"$set": {"status": JOB_DONE, "finishedAt": now(),
                      "result": {"words": n_words, "phrases": n_phrases, "patterns": n_patterns}}},
        )
        await _log(job_id, "Done")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        await db.sources().update_one(
            {"_id": oid(source_id)},
            {"$set": {"status": "error",
                      "stats.qualityStatus": "failed",
                      "stats.warnings": [f"Processing failed: {exc}"]}},
        )
        await db.jobs().update_one(
            {"_id": oid(job_id)}, {"$set": {"status": JOB_FAILED, "error": str(exc), "finishedAt": now()}}
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


async def recover_orphaned_jobs() -> int:
    """Re-queue jobs that were pending/processing when the API stopped.

    Processing runs in the API process (not in the browser). After a crash or
    ``uvicorn --reload``, in-flight jobs must be picked up again on startup.
    """
    import asyncio

    resumed = 0
    cur = db.jobs().find({"status": {"$in": [JOB_PENDING, JOB_PROCESSING]}})
    async for job in cur:
        jid = str(job["_id"])
        sid = job.get("sourceId")
        if job["status"] == JOB_PROCESSING:
            await db.jobs().update_one(
                {"_id": job["_id"]},
                {
                    "$set": {"status": JOB_PENDING, "updatedAt": now()},
                    "$push": {"logs": {"t": now(), "msg": "Resumed after server restart"}},
                },
            )
            if sid:
                await db.sources().update_one(
                    {"_id": oid(sid), "status": "processing"},
                    {"$set": {"status": "pending", "updatedAt": now()}},
                )
        asyncio.create_task(run_job_by_id(jid))
        resumed += 1
    if resumed:
        logger.info("Recovered %d orphaned job(s)", resumed)
    return resumed
