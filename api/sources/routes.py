"""Source management: upload file, add URL, paste text, list, detail, delete, reprocess."""
from __future__ import annotations
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

import database as db
from auth.dependencies import current_user_id
from utils.serialization import now, oid, is_oid, serialize
from jobs.processor import create_job, run_job_by_id
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
    title: str = "Pasted text"
    text: str


class UrlSource(BaseModel):
    url: str
    title: str | None = None


async def _run_safe(job_id: str) -> None:
    try:
        await run_job_by_id(job_id)
    except Exception:  # noqa: BLE001
        logger.exception("Background job %s failed", job_id)


async def _enqueue(background: BackgroundTasks, user_id: str, source_id: str) -> str:
    """Create the job in Mongo and run it via a FastAPI BackgroundTask.

    No standalone worker is needed: the task runs in-process after the response
    is returned. Atomic job claiming means the optional worker (if ever run)
    won't double-process.
    """
    job_id = await create_job(user_id, source_id, "process")
    background.add_task(_run_safe, job_id)
    return job_id


@router.post("/text", status_code=201)
async def add_text(body: TextSource, background: BackgroundTasks, uid: str = Depends(current_user_id)):
    if len(body.text.strip()) < 10:
        raise HTTPException(400, "Text too short")
    doc = {
        "userId": uid, "type": "text", "title": body.title.strip() or "Pasted text",
        "rawText": body.text, "status": "pending", "charCount": len(body.text),
        "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(background, uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.post("/url", status_code=201)
async def add_url(body: UrlSource, background: BackgroundTasks, uid: str = Depends(current_user_id)):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    doc = {
        "userId": uid, "type": "url", "url": body.url, "title": body.title or body.url,
        "status": "pending", "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(background, uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.post("/upload", status_code=201)
async def upload_file(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    uid: str = Depends(current_user_id),
):
    ext = (os.path.splitext(file.filename or "")[1].lstrip(".") or "txt").lower()
    if ext not in ALLOWED_FILE_KINDS:
        raise HTTPException(400, f"Unsupported file type .{ext}")
    content = await file.read()
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
        meta = s3_service.upload_file_bytes(key, content, mime)
    except Exception as exc:  # noqa: BLE001
        await db.sources().delete_one({"_id": oid(sid)})
        logger.exception("S3 upload failed")
        raise HTTPException(502, f"File storage failed: {exc}")

    # 3) persist S3 metadata (NOT the binary) on the source
    await db.sources().update_one({"_id": oid(sid)}, {"$set": {
        "storage": meta["storage"], "s3Bucket": meta.get("bucket", ""),
        "s3Key": meta["key"], "s3Url": meta.get("url", ""), "updatedAt": now(),
    }})

    # 4) enqueue extraction (processor pulls bytes from S3 → text in Mongo)
    job_id = await _enqueue(background, uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.get("")
async def list_sources(uid: str = Depends(current_user_id), page: int = 1, limit: int = 50):
    skip = (max(1, page) - 1) * limit
    cur = db.sources().find({"userId": uid}, {"rawText": 0}).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize(d) async for d in cur]
    total = await db.sources().count_documents({"userId": uid})
    return {"items": items, "total": total, "page": page}


@router.get("/{source_id}")
async def get_source(source_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    doc["rawText"] = (doc.get("rawText") or "")[:5000]
    return serialize(doc)


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
    url = s3_service.get_presigned_url(key, download_name=doc.get("originalFileName"))
    if not url:
        # local-fallback dev mode (or S3 disabled): expose stored public url if any
        url = doc.get("s3Url") or None
    if not url:
        raise HTTPException(409, "File download is only available when S3 is configured")
    return {"url": url, "expiresIn": 3600}


@router.delete("/{source_id}")
async def delete_source(source_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    # remove the original binary from S3 (or local fallback)
    if doc.get("s3Key"):
        s3_service.delete_object(doc["s3Key"])
    # remove the source + its chunks from Mongo
    await db.sources().delete_one({"_id": oid(source_id)})
    await db.source_chunks().delete_many({"sourceId": source_id})
    # detach from extracted items (keep items, just remove source ref)
    for c in (db.vocab(), db.phrases(), db.patterns()):
        await c.update_many({"userId": uid}, {"$pull": {"sourceIds": source_id}})
    return {"ok": True}


@router.post("/{source_id}/reprocess")
async def reprocess(source_id: str, background: BackgroundTasks, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"status": "pending"}})
    job_id = await _enqueue(background, uid, source_id)
    return {"jobId": job_id, "status": "pending"}
