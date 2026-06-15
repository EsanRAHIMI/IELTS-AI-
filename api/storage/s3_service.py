"""S3 storage service for original/binary files (boto3).

MongoDB stores only metadata + the S3 object key; binaries live in S3.

If AWS credentials are not configured, the service transparently falls back to
a local temp directory so the app still runs in development. In production,
configure the AWS_* env vars and S3 becomes the source of truth for binaries.
"""
from __future__ import annotations
import logging
import os
import uuid

from config import settings

logger = logging.getLogger("ielts.s3")

_client = None


def _get_client():
    """Lazily create a boto3 S3 client."""
    global _client
    if _client is None:
        import boto3

        _client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return _client


def enabled() -> bool:
    return settings.s3_enabled


# --- Key helpers ------------------------------------------------------------
def build_user_source_key(user_id: str, source_id: str, filename: str, prefix: str = "original") -> str:
    """Deterministic, collision-safe object key for a user's source file."""
    safe = "".join(c for c in (filename or "file") if c.isalnum() or c in "._- ").strip().replace(" ", "_")
    safe = safe or "file"
    return f"users/{user_id}/sources/{source_id}/{prefix}/{safe}"


# --- Core operations --------------------------------------------------------
def upload_file_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload raw bytes to S3 (or local fallback). Returns storage metadata."""
    if enabled():
        _get_client().put_object(
            Bucket=settings.aws_s3_bucket, Key=key, Body=data, ContentType=content_type
        )
        logger.info("Uploaded %d bytes to s3://%s/%s", len(data), settings.aws_s3_bucket, key)
        return {
            "storage": "s3",
            "bucket": settings.aws_s3_bucket,
            "key": key,
            "url": public_url(key),
            "sizeBytes": len(data),
            "mimeType": content_type,
        }
    # Local fallback (dev only)
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    logger.warning("S3 not configured; stored locally at %s", path)
    return {"storage": "local", "bucket": "", "key": key, "url": "", "sizeBytes": len(data), "mimeType": content_type}


def upload_file_path(key: str, path: str, content_type: str = "application/octet-stream") -> dict:
    """Upload a local file to S3 by path (used by the migration script)."""
    with open(path, "rb") as f:
        return upload_file_bytes(key, f.read(), content_type)


def download_bytes(key: str) -> bytes:
    """Fetch an object's bytes from S3 (or local fallback)."""
    if enabled():
        resp = _get_client().get_object(Bucket=settings.aws_s3_bucket, Key=key)
        return resp["Body"].read()
    path = _local_path(key)
    with open(path, "rb") as f:
        return f.read()


def object_exists(key: str) -> bool:
    if enabled():
        from botocore.exceptions import ClientError

        try:
            _get_client().head_object(Bucket=settings.aws_s3_bucket, Key=key)
            return True
        except ClientError:
            return False
    return os.path.exists(_local_path(key))


def delete_object(key: str) -> bool:
    if not key:
        return False
    if enabled():
        try:
            _get_client().delete_object(Bucket=settings.aws_s3_bucket, Key=key)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("S3 delete failed for %s: %s", key, exc)
            return False
    path = _local_path(key)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False


def get_presigned_url(key: str, expires: int | None = None, download_name: str | None = None) -> str | None:
    """Return a time-limited URL to fetch the object directly."""
    if not key:
        return None
    if enabled():
        params = {"Bucket": settings.aws_s3_bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        try:
            return _get_client().generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expires or settings.s3_presign_expiry
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Presign failed for %s: %s", key, exc)
            return None
    return None  # no public URL for local fallback


def public_url(key: str) -> str:
    base = settings.aws_s3_public_base_url.rstrip("/")
    if base:
        return f"{base}/{key}"
    if enabled():
        return f"https://{settings.aws_s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"
    return ""


def _local_path(key: str) -> str:
    # Mirror the S3 key layout under the temp dir for the dev fallback.
    return os.path.join(settings.upload_dir, "s3-fallback", key)


def random_suffix() -> str:
    return uuid.uuid4().hex[:8]
