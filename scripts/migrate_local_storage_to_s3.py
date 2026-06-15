"""Migrate any legacy local uploads into S3 and update MongoDB source records.

Older versions stored uploaded files under api/storage/uploads and recorded a
`filePath` on the source document. This one-off script:

  1. finds source docs that still have a local `filePath`
  2. uploads the file to S3 under the canonical key layout
  3. sets s3Bucket / s3Key / s3Url / storage on the source (and clears filePath)
  4. optionally deletes the local file after a successful upload

It is safe to run repeatedly and exits cleanly when there is nothing to do.

Usage:
    cd api && source .venv/bin/activate && cd ..
    python scripts/migrate_local_storage_to_s3.py [--delete-local]
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT, "api")
sys.path.insert(0, API_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(API_DIR, ".env"))


async def migrate(delete_local: bool) -> None:
    import database as db
    from config import settings
    from storage import s3_service
    from utils.serialization import now

    if not settings.s3_enabled:
        print("S3 is not configured (set AWS_* in api/.env). Nothing migrated.")
        return
    if not await db.ping():
        print("ERROR: cannot connect to MongoDB. Check MONGODB_URI in api/.env")
        sys.exit(1)

    cur = db.sources().find({"filePath": {"$exists": True, "$ne": None}})
    migrated = missing = 0
    async for src in cur:
        sid = str(src["_id"])
        path = src.get("filePath")
        if src.get("s3Key"):
            continue  # already migrated
        if not path or not os.path.exists(path):
            print(f"  [skip] source {sid}: local file missing ({path})")
            missing += 1
            continue
        ext = (src.get("fileKind") or os.path.splitext(path)[1].lstrip(".") or "txt").lower()
        name = src.get("originalFileName") or src.get("originalName") or os.path.basename(path)
        key = s3_service.build_user_source_key(src["userId"], sid, name)
        meta = s3_service.upload_file_path(key, path)
        await db.sources().update_one(
            {"_id": src["_id"]},
            {"$set": {
                "storage": "s3", "s3Bucket": meta["bucket"], "s3Key": meta["key"],
                "s3Url": meta.get("url", ""), "fileKind": ext, "updatedAt": now(),
            }, "$unset": {"filePath": ""}},
        )
        print(f"  [ok]   source {sid} -> s3://{meta['bucket']}/{meta['key']}")
        migrated += 1
        if delete_local:
            try:
                os.remove(path)
            except OSError:
                pass

    print(f"Done. Migrated {migrated}, skipped {missing}.")
    if migrated == 0 and missing == 0:
        print("No legacy local files found — nothing to do.")


def main():
    p = argparse.ArgumentParser(description="Migrate local uploads to S3")
    p.add_argument("--delete-local", action="store_true", help="delete local files after upload")
    args = p.parse_args()
    asyncio.run(migrate(args.delete_local))


if __name__ == "__main__":
    main()
