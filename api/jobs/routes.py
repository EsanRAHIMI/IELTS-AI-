"""Job status endpoints."""
from fastapi import APIRouter, Depends, HTTPException

import database as db
from auth.dependencies import current_user_id
from utils.serialization import oid, is_oid, serialize

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(uid: str = Depends(current_user_id), limit: int = 25):
    cur = db.jobs().find({"userId": uid}).sort("createdAt", -1).limit(limit)
    return {"items": [serialize(d) async for d in cur]}


@router.get("/{job_id}")
async def get_job(job_id: str, uid: str = Depends(current_user_id)):
    if not is_oid(job_id):
        raise HTTPException(404, "Not found")
    doc = await db.jobs().find_one({"_id": oid(job_id), "userId": uid})
    if not doc:
        raise HTTPException(404, "Not found")
    return serialize(doc)
