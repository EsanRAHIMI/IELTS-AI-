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
class StorageUnavailable(RuntimeError):
    """Raised when production has no object store. The message is not client-facing."""


def upload_file_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """Upload raw bytes to S3 (or a local dev fallback). Never returns a public URL."""
    if enabled():
        _get_client().put_object(
            Bucket=settings.aws_s3_bucket, Key=key, Body=data, ContentType=content_type
        )
        logger.info("Uploaded %d bytes to object storage", len(data))
        return {
            "storage": "s3",
            "bucket": settings.aws_s3_bucket,
            "key": key,
            "sizeBytes": len(data),
            "mimeType": content_type,
        }
    if not settings.allow_local_storage:
        raise StorageUnavailable("Object storage is not configured")
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    logger.warning("S3 not configured; stored locally for development")
    return {"storage": "local", "bucket": "", "key": key, "sizeBytes": len(data), "mimeType": content_type}


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
    """Return a time-limited URL. There is no unsigned fallback."""
    if not key or not enabled():
        return None
    from http_util import content_disposition

    params = {"Bucket": settings.aws_s3_bucket, "Key": key}
    if download_name:
        params["ResponseContentDisposition"] = content_disposition(download_name)
    try:
        return _get_client().generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires or settings.s3_presign_expiry
        )
    except Exception:
        logger.warning("Presign failed")
        return None


def public_url(key: str) -> str:
    """Stable object URLs are not published. Downloads use a presigned URL."""
    return ""


def _local_path(key: str) -> str:
    """Mirror the object key under the temp dir. Reject paths that escape it."""
    root = os.path.abspath(os.path.join(settings.upload_dir, "s3-fallback"))
    path = os.path.abspath(os.path.join(root, key))
    if os.path.commonpath([root, path]) != root:
        raise ValueError("invalid storage key")
    return path


def random_suffix() -> str:
    return uuid.uuid4().hex[:8]
