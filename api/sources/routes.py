"""Source management: upload file, add URL, paste text, list, detail, delete, reprocess."""
from __future__ import annotations
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import database as db
from auth.dependencies import current_user_id
from config import settings
from http_util import clamp_limit, clamp_page, content_disposition, read_bool
from quotas import allow, quota_block
from url_guard import UrlRejected, validate_url_syntax
from utils.serialization import now, oid, is_oid, serialize
from jobs.processor import cancel_jobs_for_source, create_job, schedule_job
from storage import s3_service

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger("ielts.sources")

ALLOWED_FILE_KINDS = {"pdf", "docx", "txt", "csv", "json"}
MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
}


class TextSource(BaseModel):
    title: str = Field(default="Pasted text", max_length=200)
    text: str = Field(min_length=1, max_length=2_000_000)


class UrlSource(BaseModel):
    url: str
    title: str | None = None


async def _enqueue(user_id: str, source_id: str) -> str:
    """Create the job in Mongo and schedule it on the server (not in the browser)."""
    job_id = await create_job(user_id, source_id, "process")
    schedule_job(job_id)
    return job_id


async def _limit_imports(uid: str) -> None:
    if not await allow(f"import:{uid}", settings.rate_import_per_hour, 3600):
        raise HTTPException(429, "Too many imports. Try again later.")


async def _enforce_quota(uid: str, extra_bytes: int) -> None:
    sources = await db.sources().count_documents({"userId": uid})
    rows = await db.sources().aggregate([
        {"$match": {"userId": uid}},
        {"$group": {"_id": None, "bytes": {"$sum": {"$ifNull": ["$sizeBytes", 0]}}}},
    ]).to_list(1)
    used = int(rows[0]["bytes"]) if rows else 0
    active = await db.jobs().count_documents(
        {"userId": uid, "status": {"$in": ["pending", "processing"]}},
    )
    reason = quota_block(
        sources=sources,
        max_sources=settings.max_sources_per_user,
        used_bytes=used,
        extra_bytes=extra_bytes,
        max_bytes=settings.max_storage_bytes_per_user,
        active_jobs=active,
        max_jobs=settings.max_active_jobs_per_user,
    )
    if reason:
        raise HTTPException(429, reason)


def present_source(doc: dict, *, preview: bool) -> dict:
    """Drop storage secrets and oversized text from API responses."""
    has_file = bool(doc.get("s3Key"))
    data = serialize(doc)
    if preview:
        data["rawText"] = (data.get("rawText") or "")[:5000]
        data["cleanedText"] = (data.get("cleanedText") or "")[:5000]
    else:
        data.pop("rawText", None)
        data.pop("cleanedText", None)
    for key in ("s3Key", "s3Bucket", "s3Url"):
        data.pop(key, None)
    data["hasFile"] = has_file
    return data


async def _read_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        block = await file.read(1024 * 1024)
        if not block:
            break
        size += len(block)
        if size > settings.max_upload_bytes:
            raise HTTPException(413, "File is too large")
        chunks.append(block)
    return b"".join(chunks)


@router.post("/text", status_code=201)
async def add_text(body: TextSource, uid: str = Depends(current_user_id)):
    await _limit_imports(uid)
    if len(body.text) > settings.max_paste_chars:
        raise HTTPException(413, "Text is too large")
    if len(body.text.strip()) < 10:
        raise HTTPException(400, "Text too short")
    await _enforce_quota(uid, len(body.text.encode("utf-8")))
    doc = {
        "userId": uid, "type": "text", "title": body.title.strip() or "Pasted text",
        "rawText": body.text, "status": "pending", "charCount": len(body.text),
        "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.post("/url", status_code=201)
async def add_url(body: UrlSource, uid: str = Depends(current_user_id)):
    await _limit_imports(uid)
    try:
        validate_url_syntax(body.url)
    except UrlRejected:
        raise HTTPException(400, "That URL is not allowed") from None
    await _enforce_quota(uid, 0)
    doc = {
        "userId": uid, "type": "url", "url": body.url, "title": body.title or body.url,
        "status": "pending", "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(""),
    uid: str = Depends(current_user_id),
):
    await _limit_imports(uid)
    ext = (os.path.splitext(file.filename or "")[1].lstrip(".") or "txt").lower()
    if ext not in ALLOWED_FILE_KINDS:
        raise HTTPException(400, f"Unsupported file type .{ext}")
    content = await _read_limited(file)
    await _enforce_quota(uid, len(content))
    mime = MIME_TYPES.get(ext, "application/octet-stream")

    # 1) create the source doc first so we have a stable sourceId for the S3 key
    res = await db.sources().insert_one({
        "userId": uid, "type": ext, "kind": "file",
        "title": title or file.filename or f"Upload.{ext}",
        "originalFileName": file.filename, "fileKind": ext, "mimeType": mime,
        "sizeBytes": len(content), "status": "pending",
        "createdAt": now(), "updatedAt": now(),
    })
    sid = str(res.inserted_id)

    # 2) upload the original binary to S3 (or local fallback in dev)
    key = s3_service.build_user_source_key(uid, sid, file.filename or f"file.{ext}")
    try:
        import asyncio
        meta = await asyncio.to_thread(s3_service.upload_file_bytes, key, content, mime)
    except Exception:
        await db.sources().delete_one({"_id": oid(sid)})
        logger.exception("Object storage upload failed")
        raise HTTPException(502, "File storage failed") from None

    # 3) persist object metadata (NOT the binary, and NOT a public URL) on the source
    await db.sources().update_one({"_id": oid(sid)}, {"$set": {
        "storage": meta["storage"], "s3Bucket": meta.get("bucket", ""),
        "s3Key": meta["key"], "updatedAt": now(),
    }, "$unset": {"s3Url": ""}})

    # 4) enqueue extraction (processor pulls bytes from S3 → text in Mongo)
    job_id = await _enqueue(uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.get("")
async def list_sources(uid: str = Depends(current_user_id), page: int = 1, limit: int = 50):
    page = clamp_page(page)
    limit = clamp_limit(limit, default=50, maximum=100)
    skip = (page - 1) * limit
    cur = db.sources().find({"userId": uid}).sort("createdAt", -1).skip(skip).limit(limit)
    items = [present_source(d, preview=False) async for d in cur]
    total = await db.sources().count_documents({"userId": uid})
    return {"items": items, "total": total, "page": page, "limit": limit}


async def _extracted_counts(uid: str, source_id: str) -> dict[str, int]:
    """How many vocab/phrases/patterns are linked to this source."""
    counts: dict[str, int] = {}
    for key, col in (("words", db.vocab()), ("phrases", db.phrases()), ("patterns", db.patterns())):
        counts[key] = await col.count_documents({"userId": uid, "sourceIds": source_id})
    counts["exclusiveWords"] = await db.vocab().count_documents(
        {"userId": uid, "sourceIds": [source_id]}
    )
    counts["exclusivePhrases"] = await db.phrases().count_documents(
        {"userId": uid, "sourceIds": [source_id]}
    )
    counts["exclusivePatterns"] = await db.patterns().count_documents(
        {"userId": uid, "sourceIds": [source_id]}
    )
    return counts


_CARD_TYPE = {"words": "word", "phrases": "phrase", "patterns": "sentence_pattern"}


async def _detach_or_delete_extracted(uid: str, source_id: str, *, keep_data: bool) -> dict[str, int]:
    """Unlink or delete vocabulary/phrases/patterns tied to a source."""
    removed = {"words": 0, "phrases": 0, "patterns": 0}
    for key, col in (("words", db.vocab()), ("phrases", db.phrases()), ("patterns", db.patterns())):
        card_type = _CARD_TYPE[key]
        async for doc in col.find({"userId": uid, "sourceIds": source_id}):
            sids = doc.get("sourceIds") or []
            ref_id = str(doc["_id"])
            if keep_data or len(sids) > 1:
                await col.update_one(
                    {"_id": doc["_id"]},
                    {"$pull": {"sourceIds": source_id}, "$set": {"updatedAt": now()}},
                )
            else:
                await col.delete_one({"_id": doc["_id"]})
                card_ids = [
                    str(card["_id"])
                    async for card in db.cards().find(
                        {"userId": uid, "type": card_type, "refId": ref_id}, {"_id": 1},
                    )
                ]
                await db.cards().delete_many({"userId": uid, "type": card_type, "refId": ref_id})
                if card_ids:
                    await db.reviews().delete_many({"userId": uid, "cardId": {"$in": card_ids}})
                removed[key] += 1
    return removed


async def _get_owned_source(source_id: str, uid: str) -> dict:
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.get("/{source_id}/delete-impact")
async def delete_impact(source_id: str, uid: str = Depends(current_user_id)):
    """Preview how many extracted items are linked before deleting a source."""
    await _get_owned_source(source_id, uid)
    counts = await _extracted_counts(uid, source_id)
    return {
        "linked": {
            "words": counts["words"],
            "phrases": counts["phrases"],
            "patterns": counts["patterns"],
        },
        "exclusive": {
            "words": counts["exclusiveWords"],
            "phrases": counts["exclusivePhrases"],
            "patterns": counts["exclusivePatterns"],
        },
    }


@router.get("/{source_id}")
async def get_source(source_id: str, uid: str = Depends(current_user_id)):
    doc = await _get_owned_source(source_id, uid)
    return present_source(doc, preview=True)


@router.get("/{source_id}/download-url")
async def download_url(source_id: str, uid: str = Depends(current_user_id)):
    """Return a time-limited presigned URL for the original S3 file."""
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    key = doc.get("s3Key")
    if not key:
        raise HTTPException(404, "This source has no stored file")
    import asyncio
    url = await asyncio.to_thread(
        s3_service.get_presigned_url, key, None, doc.get("originalFileName"),
    )
    if url:
        return {"url": url, "expiresIn": settings.s3_presign_expiry}
    if doc.get("storage") == "local" and settings.allow_local_storage:
        return {
            "url": f"{settings.api_prefix}/sources/{source_id}/file",
            "expiresIn": settings.s3_presign_expiry,
            "authenticated": True,
        }
    raise HTTPException(409, "File download is unavailable")


@router.get("/{source_id}/file")
async def download_local_file(source_id: str, uid: str = Depends(current_user_id)):
    """Authenticated download for the development storage fallback. Not a public URL."""
    if not settings.allow_local_storage:
        raise HTTPException(404, "Not found")
    doc = await _get_owned_source(source_id, uid)
    if doc.get("storage") != "local" or not doc.get("s3Key"):
        raise HTTPException(404, "Not found")
    try:
        path = s3_service._local_path(doc["s3Key"])
    except ValueError:
        raise HTTPException(404, "Not found") from None
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    filename = content_disposition(doc.get("originalFileName")).split('filename="', 1)[-1].rstrip('"')
    return FileResponse(path, filename=filename)


@router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    request: Request,
    uid: str = Depends(current_user_id),
):
    keep_extracted_data = read_bool(
        request.query_params, ("keepExtractedData", "keep_extracted_data"), True,
    )
    doc = await _get_owned_source(source_id, uid)
    await cancel_jobs_for_source(uid, source_id)
    if doc.get("s3Key"):
        import asyncio
        await asyncio.to_thread(s3_service.delete_object, doc["s3Key"])
    await db.sources().delete_one({"_id": oid(source_id), "userId": uid})
    await db.source_chunks().delete_many({"sourceId": source_id})
    await db.source_pages().delete_many({"sourceId": source_id})
    removed = await _detach_or_delete_extracted(uid, source_id, keep_data=keep_extracted_data)
    return {"ok": True, "keepExtractedData": keep_extracted_data, "removed": removed}


@router.post("/{source_id}/reprocess")
async def reprocess(
    source_id: str,
    request: Request,
    uid: str = Depends(current_user_id),
):
    reset_extracted_data = read_bool(
        request.query_params, ("resetExtractedData", "reset_extracted_data"), False,
    )
    await _get_owned_source(source_id, uid)
    await _limit_imports(uid)
    await cancel_jobs_for_source(uid, source_id)
    await db.source_chunks().delete_many({"sourceId": source_id})
    await db.source_pages().delete_many({"sourceId": source_id})
    if reset_extracted_data:
        await _detach_or_delete_extracted(uid, source_id, keep_data=False)
    # Leave sourceIds in place when not resetting. Merge replaces this source's
    # frequency bucket instead of adding it on top of the previous total.
    # Keep rawText so a pasted source can be reprocessed.
    await db.sources().update_one(
        {"_id": oid(source_id), "userId": uid},
        {"$set": {"status": "pending", "stats": {}, "cleanedText": "",
                  "chunkCount": 0, "updatedAt": now()}},
    )
    job_id = await _enqueue(uid, source_id)
    return {"jobId": job_id, "status": "pending", "resetExtractedData": reset_extracted_data}
