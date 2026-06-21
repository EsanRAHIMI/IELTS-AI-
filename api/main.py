"""IELTS AI Mastery Engine - FastAPI application entrypoint."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from pymongo.errors import ServerSelectionTimeoutError

from config import settings
import database as db
from ai import service as ai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ielts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IELTS AI Mastery Engine API")
    ok = await db.ping()
    if ok:
        await db.init_indexes()
        logger.info("Connected to MongoDB '%s'", settings.mongodb_db)
    else:
        logger.warning("MongoDB not reachable at startup - check MONGODB_URI")
    logger.info("AI provider '%s' configured: %s", settings.ai_provider, ai.ai_available())
    yield
    logger.info("Shutting down")


app = FastAPI(title="IELTS AI Mastery Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cors_headers(request: Request) -> dict[str, str]:
    """Ensure error responses include CORS headers (browser blocks them otherwise)."""
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@app.exception_handler(ServerSelectionTimeoutError)
async def mongo_unavailable_handler(request: Request, exc: ServerSelectionTimeoutError):
    logger.error("MongoDB unavailable on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database unavailable. Check MONGODB_URI and MongoDB Atlas "
                "Network Access (add your IP or 0.0.0.0/0 for local dev)."
            )
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers(request),
    )


# Routers --------------------------------------------------------------------
from auth.routes import router as auth_router  # noqa: E402
from sources.routes import router as sources_router  # noqa: E402
from jobs.routes import router as jobs_router  # noqa: E402
from content.routes import router as content_router  # noqa: E402
from study.routes import router as study_router  # noqa: E402
from progress.routes import router as progress_router  # noqa: E402

app.include_router(auth_router)
app.include_router(sources_router)
app.include_router(jobs_router)
app.include_router(content_router)
app.include_router(study_router)
app.include_router(progress_router)


@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "db": await db.ping(),
        "aiProvider": settings.ai_provider,
        "aiConfigured": ai.ai_available(),
    }


@app.get("/", tags=["meta"])
async def root():
    return {"name": "IELTS AI Mastery Engine API", "version": "1.0.0", "docs": "/docs"}
