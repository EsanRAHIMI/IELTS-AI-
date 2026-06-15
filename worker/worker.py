"""Standalone background worker.

Polls MongoDB for pending jobs and processes them using the same pipeline as
the API. Run it as a separate process:

    cd api && source .venv/bin/activate
    cd ../worker && python worker.py

It shares the api/ code (added to sys.path below), so run it from the repo
with the api virtualenv activated.
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys

# Make the api/ package importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
logger = logging.getLogger("ielts.worker")

POLL_INTERVAL = float(os.environ.get("WORKER_POLL_INTERVAL", "3"))


async def main() -> None:
    import database as db
    from jobs.processor import claim_next, process_job

    if not await db.ping():
        logger.error("Cannot reach MongoDB. Check MONGODB_URI in api/.env")
    await db.init_indexes()
    logger.info("Worker started. Polling every %.1fs", POLL_INTERVAL)

    while True:
        try:
            job = await claim_next()
            if job:
                logger.info("Claimed job %s (source %s)", job["_id"], job.get("sourceId"))
                await process_job(job)
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:  # noqa: BLE001
            logger.exception("Worker loop error")
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
