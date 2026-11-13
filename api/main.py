"""IELTS AI Mastery Engine - FastAPI application entrypoint."""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from pymongo.errors import ServerSelectionTimeoutError

from config import settings
import database as db
from ai import service as ai
from security_policy import enforce_startup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ielts")

API_PREFIX = settings.api_prefix


@asynccontextmanager
async def lifespan(app: FastAPI):
    enforce_startup(settings)
    logger.info("Starting IELTS AI Mastery Engine API")
    ok = await db.ping()
    if ok:
        await db.init_indexes()
        logger.info("Connected to MongoDB '%s'", settings.mongodb_db)
    else:
        logger.warning("MongoDB not reachable at startup - check MONGODB_URI")
    logger.info("AI provider '%s' configured: %s", settings.ai_provider, ai.ai_available())
    if API_PREFIX:
        logger.info("API routes mounted under prefix '%s'", API_PREFIX)
    from jobs.processor import recover_orphaned_jobs

    asyncio.create_task(recover_orphaned_jobs())
    yield
    logger.info("Shutting down")


_docs = settings.local_dev
app = FastAPI(
    title="IELTS AI Mastery Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=(f"{API_PREFIX}/docs" if API_PREFIX else "/docs") if _docs else None,
    openapi_url=(f"{API_PREFIX}/openapi.json" if API_PREFIX else "/openapi.json") if _docs else None,
    redoc_url=(f"{API_PREFIX}/redoc" if API_PREFIX else "/redoc") if _docs else None,
)

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
        content={"detail": "Database unavailable"},
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

api_router = APIRouter(prefix=API_PREFIX)

api_router.include_router(auth_router)
api_router.include_router(sources_router)
api_router.include_router(jobs_router)
api_router.include_router(content_router)
api_router.include_router(study_router)
api_router.include_router(progress_router)


@api_router.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "db": await db.ping()}


@api_router.get("/", tags=["meta"])
async def root():
    docs_path = f"{API_PREFIX}/docs" if API_PREFIX else "/docs"
    return {"name": "IELTS AI Mastery Engine API", "version": "1.0.0", "docs": docs_path}


app.include_router(api_router)
