"""Object storage for an uploaded coursebook."""
import pytest
from botocore.exceptions import ClientError

from config import Settings, settings
from storage import s3_service
from storage.s3_service import StorageUnavailable, build_user_source_key, upload_file_bytes


PDF_NAME = "Oxford Word Skills Elementary 2nd Edition.pdf"


def test_s3_client_does_not_use_the_60s_chunked_default():
    cfg = s3_service._client_config()
    assert cfg.read_timeout == 900
    assert cfg.connect_timeout == 10
    assert cfg.retries["max_attempts"] == 2
    assert cfg.request_checksum_calculation == "when_required"
    assert cfg.response_checksum_validation == "when_required"


def test_coursebook_pdf_uses_the_same_put_object_as_a_text_file(monkeypatch):
    captured = {}

    class FakeClient:
        def put_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(s3_service, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(settings, "aws_access_key_id", "key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "secret")
    monkeypatch.setattr(settings, "aws_s3_bucket", "coursebooks")

    key = build_user_source_key("user", "source", PDF_NAME)
    data = b"%PDF-1.7" + (b"x" * (9 * 1024 * 1024))
    meta = upload_file_bytes(key, data, "application/pdf")

    assert meta["storage"] == "s3"
    assert meta["bucket"] == "coursebooks"
    assert meta["sizeBytes"] == len(data)
    assert captured["Body"] == data
    assert captured["ContentLength"] == len(data)
    assert captured["ContentType"] == "application/pdf"
    assert captured["Bucket"] == "coursebooks"
    assert captured["Key"].endswith("Oxford_Word_Skills_Elementary_2nd_Edition.pdf")


def test_storage_failure_keeps_the_s3_error_code():
    exc = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "hidden"}},
        "PutObject",
    )
    assert s3_service.public_failure_detail(exc) == "File storage failed (AccessDenied)"
    assert "hidden" not in s3_service.public_failure_detail(exc)


def test_production_without_aws_does_not_keep_the_file_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(settings, "aws_s3_bucket", "")
    monkeypatch.setattr(Settings, "allow_local_storage", property(lambda self: False))

    with pytest.raises(StorageUnavailable):
        upload_file_bytes("users/u/sources/s/original/note.txt", b"hello", "text/plain")

    assert list(tmp_path.rglob("*")) == []
