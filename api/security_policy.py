"""Startup checks and client-safe error text.

Local development is the only place the insecure default JWT secret is
accepted. A public CORS origin, an API prefix, or an explicit production
environment all count as deployed.
"""
from __future__ import annotations

from urllib.parse import urlsplit

INSECURE_JWT_SECRETS = {
    "dev-insecure-secret-change-me",
    "change-me-to-a-long-random-string",
    "secret",
    "changeme",
    "change-me",
}
MIN_JWT_LENGTH = 32


def is_local_origin(origin: str) -> bool:
    host = (urlsplit(origin).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def is_local_context(*, app_env: str, api_prefix: str, cors_origins: list[str]) -> bool:
    if (app_env or "").strip().lower() in {"production", "prod"}:
        return False
    if (api_prefix or "").strip():
        return False
    return all(is_local_origin(origin) for origin in cors_origins)


def jwt_startup_error(*, secret: str, algorithm: str, local: bool) -> str | None:
    if (algorithm or "").upper() != "HS256":
        return "Only HS256 JWT tokens are supported"
    value = (secret or "").strip()
    insecure = value in INSECURE_JWT_SECRETS or len(value) < MIN_JWT_LENGTH
    if insecure and not local:
        return "Refusing to start with the default JWT secret outside local development"
    return None


def enforce_startup(settings) -> None:
    local = is_local_context(
        app_env=settings.app_env,
        api_prefix=settings.api_prefix,
        cors_origins=settings.cors_origins_list,
    )
    error = jwt_startup_error(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        local=local,
    )
    if error:
        raise RuntimeError(error)


def public_job_error(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    if code == "size":
        return "The page or file is too large to import"
    if code in {"scheme", "host", "auth", "port", "redirect", "dns", "socket"}:
        return "That URL is not allowed"
    if code in {"status", "fetch"}:
        return "The page could not be fetched"
    if isinstance(exc, TimeoutError):
        return "Processing timed out"
    return "Processing failed"
