"""Job status endpoints."""
from fastapi import APIRouter, Depends, HTTPException

import database as db
from auth.dependencies import current_user_id
from jobs.schemas import JOB_PENDING, JOB_PROCESSING
from utils.serialization import oid, is_oid, serialize

router = APIRouter(prefix="/jobs", tags=["jobs"])

_ACTIVE = {JOB_PENDING, JOB_PROCESSING}


@router.get("")
async def list_jobs(uid: str = Depends(current_user_id), limit: int = 25):
    cur = db.jobs().find({"userId": uid}).sort("createdAt", -1).limit(limit)
    return {"items": [serialize(d) async for d in cur]}


@router.get("/active")
async def active_jobs(uid: str = Depends(current_user_id)):
    """Jobs still running — used by the Import page after refresh/return."""
    cur = db.jobs().find({"userId": uid, "status": {"$in": list(_ACTIVE)}}).sort("updatedAt", -1)
    items = []
    async for doc in cur:
        row = serialize(doc)
        logs = doc.get("logs") or []
        row["lastLog"] = logs[-1]["msg"] if logs else None
        items.append(row)
    return {"items": items}


@router.get("/by-source/{source_id}")
async def job_for_source(source_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(source_id):
        raise HTTPException(404, "Not found")
    doc = await db.jobs().find_one(
        {"userId": uid, "sourceId": source_id},
        sort=[("createdAt", -1)],
    )
    if not doc:
        raise HTTPException(404, "No job for this source")
    row = serialize(doc)
    logs = doc.get("logs") or []
    row["lastLog"] = logs[-1]["msg"] if logs else None
    return row


@router.get("/{job_id}")
async def get_job(job_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(job_id):
        raise HTTPException(404, "Not found")
    doc = await db.jobs().find_one({"_id": oid(job_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    return serialize(doc)
