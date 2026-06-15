"""Source management: upload file, add URL, paste text, list, detail, delete, reprocess."""
from __future__ import annotations
import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

import database as db
from config import settings
from auth.dependencies import current_user_id
from utils.serialization import now, oid, is_oid, serialize
from jobs.processor import create_job, run_job_by_id

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger("ielts.sources")

ALLOWED_FILE_KINDS = {"pdf", "docx", "txt", "csv", "json"}


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
        logger.exception("In-process job %s failed", job_id)


async def _enqueue(user_id: str, source_id: str) -> str:
    job_id = await create_job(user_id, source_id, "process")
    # Process in-process so the app works even without the standalone worker.
    # The worker also polls; atomic claiming prevents double processing.
    asyncio.create_task(_run_safe(job_id))
    return job_id


@router.post("/text", status_code=201)
async def add_text(body: TextSource, uid: str = Depends(current_user_id)):
    if len(body.text.strip()) < 10:
        raise HTTPException(400, "Text too short")
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
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    doc = {
        "userId": uid, "type": "url", "url": body.url, "title": body.title or body.url,
        "status": "pending", "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(uid, sid)
    return {"id": sid, "jobId": job_id, "status": "pending"}


@router.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...), title: str = Form(""), uid: str = Depends(current_user_id)):
    ext = (os.path.splitext(file.filename or "")[1].lstrip(".") or "txt").lower()
    if ext not in ALLOWED_FILE_KINDS:
        raise HTTPException(400, f"Unsupported file type .{ext}")
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(settings.upload_dir, stored_name)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    doc = {
        "userId": uid, "type": "file", "title": title or file.filename or stored_name,
        "filePath": path, "fileKind": ext, "originalName": file.filename,
        "fileSize": len(content), "status": "pending", "createdAt": now(), "updatedAt": now(),
    }
    res = await db.sources().insert_one(doc)
    sid = str(res.inserted_id)
    job_id = await _enqueue(uid, sid)
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


@router.delete("/{source_id}")
async def delete_source(source_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    if doc.get("filePath") and os.path.exists(doc["filePath"]):
        try:
            os.remove(doc["filePath"])
        except OSError:
            pass
    await db.sources().delete_one({"_id": oid(source_id)})
    # detach from extracted items (keep items, just remove source ref)
    for c in (db.vocab(), db.phrases(), db.patterns()):
        await c.update_many({"userId": uid}, {"$pull": {"sourceIds": source_id}})
    return {"ok": True}


@router.post("/{source_id}/reprocess")
async def reprocess(source_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.sources().find_one({"_id": oid(source_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    await db.sources().update_one({"_id": oid(source_id)}, {"$set": {"status": "pending"}})
    job_id = await _enqueue(uid, source_id)
    return {"jobId": job_id, "status": "pending"}
