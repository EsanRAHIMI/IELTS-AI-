"""Password hashing and JWT helpers."""
from datetime import timedelta
from typing import Any

import bcrypt
from jose import jwt, JWTError

from config import settings
from utils.serialization import now

# bcrypt only considers the first 72 bytes of the password. We call bcrypt
# directly (instead of passlib, which is unmaintained and breaks with
# bcrypt >= 5 on newer Python) and truncate defensively to 72 bytes.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pw = plain.encode("utf-8")[:_MAX_BCRYPT_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, *, token_version: int = 0, extra: dict[str, Any] | None = None) -> str:
    expire = now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now(),
        "tv": int(token_version),
    }
    if extra:
        payload.update(extra)
    if settings.jwt_algorithm.upper() != "HS256":
        raise RuntimeError("Only HS256 JWT tokens are supported")
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return None
