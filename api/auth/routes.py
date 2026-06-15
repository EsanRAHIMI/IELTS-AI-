"""Auth + user endpoints: register, login, me, settings."""
from fastapi import APIRouter, Depends, HTTPException, status

import database as db
from auth.schemas import RegisterRequest, LoginRequest, TokenResponse, UserSettings
from auth.security import hash_password, verify_password, create_access_token
from auth.dependencies import get_current_user
from utils.serialization import now, serialize, oid

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


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    existing = await db.users().find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    doc = {
        "email": body.email.lower(),
        "name": body.name or body.email.split("@")[0],
        "passwordHash": hash_password(body.password),
        "settings": DEFAULT_SETTINGS.copy(),
        "createdAt": now(),
        "updatedAt": now(),
    }
    res = await db.users().insert_one(doc)
    doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id))
    return {"accessToken": token, "tokenType": "bearer", "user": _public(doc)}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await db.users().find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user["_id"]))
    return {"accessToken": token, "tokenType": "bearer", "user": _public(user)}


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
