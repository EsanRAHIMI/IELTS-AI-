"""Auth + user endpoints: register, login, me, settings."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

import database as db
from auth.schemas import PasswordChange, RegisterRequest, LoginRequest, TokenResponse, UserSettings
from auth.security import hash_password, verify_password, create_access_token
from auth.dependencies import get_current_user
from config import settings
from http_util import client_ip
from quotas import allow
from utils.serialization import now, oid

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_SETTINGS = {
    "aiProvider": "openai",
    "dailyTarget": 30,
    "targetBand": 7.5,
    "examDate": None,
    "focusModules": ["Academic", "Writing", "Speaking"],
}


def _public(user: dict) -> dict:
    return {
        "id": str(user["_id"]) if "_id" in user else user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "settings": user.get("settings", DEFAULT_SETTINGS),
    }


def _token_version(user: dict) -> int:
    return int(user.get("tokenVersion") or 0)


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("timing-safe-dummy-password")
    return _DUMMY_HASH


async def _too_many(key: str, limit: int) -> None:
    if not await allow(key, limit, 3600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request):
    await _too_many(f"register:{client_ip(request, trust_proxy=settings.trust_proxy)}", settings.rate_register_per_hour)
    email = body.email.lower()
    existing = await db.users().find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Try signing in instead.",
        )
    doc = {
        "email": email,
        "name": body.name or email.split("@")[0],
        "passwordHash": hash_password(body.password),
        "tokenVersion": 0,
        "settings": DEFAULT_SETTINGS.copy(),
        "createdAt": now(),
        "updatedAt": now(),
    }
    try:
        res = await db.users().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Try signing in instead.",
        ) from None
    doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id), token_version=0)
    return {"accessToken": token, "tokenType": "bearer", "user": _public(doc)}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    ip = client_ip(request, trust_proxy=settings.trust_proxy)
    await _too_many(f"login:ip:{ip}", settings.rate_login_per_hour)
    email = body.email.lower()
    await _too_many(f"login:email:{email}", settings.rate_login_per_hour)
    user = await db.users().find_one({"email": email})
    # Always run bcrypt so a missing account is not obvious from response time.
    stored = user["passwordHash"] if user else _dummy_hash()
    valid = verify_password(body.password, stored)
    if not user or not valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password. Please check your credentials and try again.",
        )
    token = create_access_token(str(user["_id"]), token_version=_token_version(user))
    return {"accessToken": token, "tokenType": "bearer", "user": _public(user)}


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Bump tokenVersion so the presented bearer token stops working."""
    await db.users().update_one({"_id": oid(user["id"])}, {"$inc": {"tokenVersion": 1}, "$set": {"updatedAt": now()}})
    return {"ok": True}


@router.post("/change-password", response_model=TokenResponse)
async def change_password(body: PasswordChange, user: dict = Depends(get_current_user)):
    raw = await db.users().find_one({"_id": oid(user["id"])})
    if not raw or not verify_password(body.currentPassword, raw.get("passwordHash") or ""):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users().update_one(
        {"_id": raw["_id"]},
        {"$set": {"passwordHash": hash_password(body.newPassword), "updatedAt": now()}, "$inc": {"tokenVersion": 1}},
    )
    updated = await db.users().find_one({"_id": raw["_id"]})
    token = create_access_token(str(updated["_id"]), token_version=_token_version(updated))
    return {"accessToken": token, "tokenType": "bearer", "user": _public(updated)}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public(user)


@router.put("/me/settings")
async def update_settings(body: UserSettings, user: dict = Depends(get_current_user)):
    await db.users().update_one(
        {"_id": oid(user["id"])},
        {"$set": {"settings": body.model_dump(), "updatedAt": now()}},
    )
    updated = await db.users().find_one({"_id": oid(user["id"])})
    return _public(updated)


@router.get("/session")
async def session(user: dict = Depends(get_current_user)):
    """Authenticated view of which AI providers the server can actually call."""
    from ai import service as ai

    choice = (user.get("settings") or {}).get("aiProvider") or settings.ai_provider
    return {
        "db": await db.ping(),
        "aiProvider": choice,
        "aiConfigured": ai.get_provider(choice) is not None,
        "serverProvider": settings.ai_provider,
    }
